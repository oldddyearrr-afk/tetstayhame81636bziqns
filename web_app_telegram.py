
#!/usr/bin/env python3
from flask import Flask, render_template, jsonify, request
import subprocess
import os
import json
from datetime import datetime
from pathlib import Path
import uuid

app = Flask(__name__, template_folder='templates')

BASE_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = BASE_DIR / "scripts"
LOGS_DIR = BASE_DIR / "logs"
STREAMS_FILE = BASE_DIR / "telegram_streams.json"

def load_streams():
    """تحميل قائمة بثوث تليجرام من الملف"""
    if STREAMS_FILE.exists():
        with open(STREAMS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_streams(streams):
    """حفظ قائمة بثوث تليجرام"""
    with open(STREAMS_FILE, 'w', encoding='utf-8') as f:
        json.dump(streams, f, ensure_ascii=False, indent=2)

def get_stream_status(session_name):
    """التحقق من حالة بث معين"""
    try:
        result = subprocess.run(
            ['tmux', 'has-session', '-t', session_name],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except:
        return False

def update_streams_status():
    """تحديث حالة جميع البثوث"""
    streams = load_streams()
    for stream in streams:
        stream['status'] = 'running' if get_stream_status(stream['session_name']) else 'stopped'
    save_streams(streams)
    return streams

@app.route('/')
def index():
    return render_template('telegram_index.html')

@app.route('/api/streams')
def api_streams():
    """الحصول على قائمة جميع بثوث تليجرام"""
    streams = update_streams_status()
    return jsonify({'streams': streams})

@app.route('/api/stream/add', methods=['POST'])
def api_add_stream():
    """إضافة بث تليجرام جديد"""
    try:
        data = request.get_json() or {}
        stream_key = data.get('stream_key', '').strip()
        stream_name = data.get('stream_name', '').strip()
        source_url = data.get('source_url', '').strip()
        
        if not stream_key:
            return jsonify({'success': False, 'error': 'يرجى إدخال مفتاح البث (RTMP URL)'}), 400
        
        if not stream_name:
            stream_name = f'بث تليجرام {datetime.now().strftime("%H:%M:%S")}'
        
        # إنشاء معرف فريد للجلسة
        stream_id = str(uuid.uuid4())[:8]
        session_name = f'tgstream_{stream_id}'
        
        # تحميل البثوث الحالية
        streams = load_streams()
        
        # إضافة البث الجديد
        new_stream = {
            'id': stream_id,
            'session_name': session_name,
            'name': stream_name,
            'stream_key': stream_key[:30] + '...',
            'source_url': source_url or 'default',
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'starting'
        }
        streams.append(new_stream)
        save_streams(streams)
        
        # بدء البث
        env = os.environ.copy()
        env['TG_STREAM_URL'] = stream_key
        
        # إنشاء سكريبت مؤقت للبث
        temp_script = f"/tmp/tg_stream_{stream_id}.sh"
        with open(temp_script, 'w') as f:
            f.write(f"""#!/bin/bash
SOURCE="{source_url if source_url else 'http://soft24f.net/live/6872c3410e8cibopro/22bcpapc/237014.ts'}"
RTMP_URL="{stream_key}"

ffmpeg -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 10 \\
  -i "$SOURCE" \\
  -c:v libx264 -preset ultrafast -tune zerolatency \\
  -b:v 3000k -maxrate 3500k -bufsize 6000k \\
  -pix_fmt yuv420p -g 60 -keyint_min 60 \\
  -c:a aac -b:a 128k -ar 44100 -ac 2 \\
  -f flv "$RTMP_URL"
""")
        
        os.chmod(temp_script, 0o755)
        
        subprocess.Popen(
            ['tmux', 'new-session', '-d', '-s', session_name, temp_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        import time
        time.sleep(4)
        
        # تحديث الحالة
        if get_stream_status(session_name):
            for stream in streams:
                if stream['id'] == stream_id:
                    stream['status'] = 'running'
            save_streams(streams)
            return jsonify({'success': True, 'message': 'تم بدء البث إلى تليجرام بنجاح ✅', 'stream_id': stream_id})
        else:
            streams = [s for s in streams if s['id'] != stream_id]
            save_streams(streams)
            return jsonify({'success': False, 'error': 'فشل بدء البث'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/stream/stop/<stream_id>', methods=['POST'])
def api_stop_stream(stream_id):
    """إيقاف بث تليجرام معين"""
    try:
        streams = load_streams()
        stream = next((s for s in streams if s['id'] == stream_id), None)
        
        if not stream:
            return jsonify({'success': False, 'error': 'البث غير موجود'}), 404
        
        subprocess.run(
            ['tmux', 'kill-session', '-t', stream['session_name']],
            check=False
        )
        
        import time
        time.sleep(1)
        
        stream['status'] = 'stopped'
        save_streams(streams)
        
        return jsonify({'success': True, 'message': 'تم إيقاف البث'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/stream/delete/<stream_id>', methods=['DELETE'])
def api_delete_stream(stream_id):
    """حذف بث من القائمة"""
    try:
        streams = load_streams()
        stream = next((s for s in streams if s['id'] == stream_id), None)
        
        if not stream:
            return jsonify({'success': False, 'error': 'البث غير موجود'}), 404
        
        if stream['status'] == 'running':
            subprocess.run(['tmux', 'kill-session', '-t', stream['session_name']], check=False)
        
        streams = [s for s in streams if s['id'] != stream_id]
        save_streams(streams)
        
        return jsonify({'success': True, 'message': 'تم حذف البث'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/stream/logs/<stream_id>')
def api_stream_logs(stream_id):
    """الحصول على سجلات بث معين"""
    try:
        streams = load_streams()
        stream = next((s for s in streams if s['id'] == stream_id), None)
        
        if not stream:
            return jsonify({'error': 'البث غير موجود'}), 404
        
        try:
            result = subprocess.run(
                ['tmux', 'capture-pane', '-t', stream['session_name'], '-p', '-S', '-50'],
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode == 0:
                logs = result.stdout.split('\n')
                return jsonify({'logs': logs})
        except:
            pass
        
        return jsonify({'logs': ['لا توجد سجلات متاحة']})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    LOGS_DIR.mkdir(exist_ok=True)
    app.run(host='0.0.0.0', port=5001, debug=False)
