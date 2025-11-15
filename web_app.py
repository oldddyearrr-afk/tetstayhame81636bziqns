
#!/usr/bin/env python3
from flask import Flask, render_template, jsonify, request
import subprocess
import os
import json
from datetime import datetime
from pathlib import Path
import uuid

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = BASE_DIR / "scripts"
LOGS_DIR = BASE_DIR / "logs"
STREAMS_FILE = BASE_DIR / "streams.json"

def load_streams():
    """تحميل قائمة البثوث من الملف"""
    if STREAMS_FILE.exists():
        try:
            with open(STREAMS_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    return []
                return json.loads(content)
        except (json.JSONDecodeError, ValueError):
            # إذا كان الملف تالف، نرجع قائمة فارغة
            return []
    return []

def save_streams(streams):
    """حفظ قائمة البثوث"""
    try:
        with open(STREAMS_FILE, 'w', encoding='utf-8') as f:
            json.dump(streams if streams else [], f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"خطأ في حفظ البثوث: {e}")

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
def main_index():
    """الصفحة الرئيسية"""
    return render_template('index_main.html')

@app.route('/facebook')
def facebook_index():
    return render_template('index.html')

@app.route('/telegram')
def telegram_index():
    """صفحة تليجرام مباشرة"""
    from flask import render_template
    return render_template('telegram_index.html')

@app.route('/api/streams')
def api_streams():
    """الحصول على قائمة جميع البثوث"""
    streams = update_streams_status()
    return jsonify({'streams': streams})

@app.route('/api/stream/add', methods=['POST'])
def api_add_stream():
    """إضافة بث جديد"""
    try:
        data = request.get_json() or {}
        stream_key = data.get('stream_key', '').strip()
        stream_name = data.get('stream_name', '').strip()
        source_url = data.get('source_url', '').strip()
        
        if not stream_key:
            return jsonify({'success': False, 'error': 'يرجى إدخال مفتاح البث'}), 400
        
        if not stream_name:
            stream_name = f'بث {datetime.now().strftime("%H:%M:%S")}'
        
        # إنشاء معرف فريد للجلسة
        stream_id = str(uuid.uuid4())[:8]
        session_name = f'fbstream_{stream_id}'
        
        # تحميل البثوث الحالية
        streams = load_streams()
        
        # إضافة البث الجديد
        new_stream = {
            'id': stream_id,
            'session_name': session_name,
            'name': stream_name,
            'stream_key': stream_key[:10] + '...',  # إخفاء المفتاح
            'source_url': source_url or 'default',
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'starting'
        }
        streams.append(new_stream)
        save_streams(streams)
        
        # بدء البث
        env = os.environ.copy()
        env['FB_STREAM_KEY'] = stream_key
        if source_url:
            # تحديث config.sh مؤقتاً للمصدر
            update_config_source(source_url)
        
        subprocess.Popen(
            ['bash', str(SCRIPTS_DIR / 'main.sh')],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            cwd=str(SCRIPTS_DIR),
            env=env,
            preexec_fn=lambda: os.system(f'tmux rename-session -t fbstream {session_name}')
        )
        
        import time
        time.sleep(4)
        
        # تحديث الحالة
        if get_stream_status(session_name):
            for stream in streams:
                if stream['id'] == stream_id:
                    stream['status'] = 'running'
            save_streams(streams)
            return jsonify({'success': True, 'message': 'تم بدء البث بنجاح ✅', 'stream_id': stream_id})
        else:
            # حذف البث في حالة الفشل
            streams = [s for s in streams if s['id'] != stream_id]
            save_streams(streams)
            return jsonify({'success': False, 'error': 'فشل بدء البث'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/stream/stop/<stream_id>', methods=['POST'])
def api_stop_stream(stream_id):
    """إيقاف بث معين"""
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
        
        # تحديث الحالة
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
        
        # إيقاف البث إذا كان يعمل
        if stream['status'] == 'running':
            subprocess.run(['tmux', 'kill-session', '-t', stream['session_name']], check=False)
        
        # حذف من القائمة
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
        
        # محاولة قراءة السجلات من tmux
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

def update_config_source(source_url):
    """تحديث مصدر البث في config.sh"""
    config_file = SCRIPTS_DIR / 'config.sh'
    if config_file.exists():
        with open(config_file, 'r') as f:
            content = f.read()
        import re
        content = re.sub(r'SOURCE="[^"]*"', f'SOURCE="{source_url}"', content)
        with open(config_file, 'w') as f:
            f.write(content)

# ========== Telegram API Endpoints ==========
TELEGRAM_STREAMS_FILE = BASE_DIR / "telegram_streams.json"

def load_telegram_streams():
    """تحميل قائمة بثوث تليجرام من الملف"""
    if TELEGRAM_STREAMS_FILE.exists():
        try:
            with open(TELEGRAM_STREAMS_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    return []
                return json.loads(content)
        except (json.JSONDecodeError, ValueError):
            # إذا كان الملف تالف، نرجع قائمة فارغة ونعيد إنشاء الملف
            return []
    return []

def save_telegram_streams(streams):
    """حفظ قائمة بثوث تليجرام"""
    try:
        with open(TELEGRAM_STREAMS_FILE, 'w', encoding='utf-8') as f:
            json.dump(streams if streams else [], f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"خطأ في حفظ البثوث: {e}")

@app.route('/api/telegram/streams')
def api_telegram_streams():
    """الحصول على قائمة جميع بثوث تليجرام"""
    streams = load_telegram_streams()
    for stream in streams:
        stream['status'] = 'running' if get_stream_status(stream['session_name']) else 'stopped'
    save_telegram_streams(streams)
    return jsonify({'streams': streams})

@app.route('/api/telegram/stream/add', methods=['POST'])
def api_telegram_add_stream():
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
        
        stream_id = str(uuid.uuid4())[:8]
        session_name = f'tgstream_{stream_id}'
        
        streams = load_telegram_streams()
        
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
        save_telegram_streams(streams)
        
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
        
        if get_stream_status(session_name):
            for stream in streams:
                if stream['id'] == stream_id:
                    stream['status'] = 'running'
            save_telegram_streams(streams)
            return jsonify({'success': True, 'message': 'تم بدء البث إلى تليجرام بنجاح ✅', 'stream_id': stream_id})
        else:
            streams = [s for s in streams if s['id'] != stream_id]
            save_telegram_streams(streams)
            return jsonify({'success': False, 'error': 'فشل بدء البث'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/telegram/stream/stop/<stream_id>', methods=['POST'])
def api_telegram_stop_stream(stream_id):
    """إيقاف بث تليجرام معين"""
    try:
        streams = load_telegram_streams()
        stream = next((s for s in streams if s['id'] == stream_id), None)
        
        if not stream:
            return jsonify({'success': False, 'error': 'البث غير موجود'}), 404
        
        subprocess.run(['tmux', 'kill-session', '-t', stream['session_name']], check=False)
        
        import time
        time.sleep(1)
        
        stream['status'] = 'stopped'
        save_telegram_streams(streams)
        
        return jsonify({'success': True, 'message': 'تم إيقاف البث'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/telegram/stream/delete/<stream_id>', methods=['DELETE'])
def api_telegram_delete_stream(stream_id):
    """حذف بث من القائمة"""
    try:
        streams = load_telegram_streams()
        stream = next((s for s in streams if s['id'] == stream_id), None)
        
        if not stream:
            return jsonify({'success': False, 'error': 'البث غير موجود'}), 404
        
        if stream['status'] == 'running':
            subprocess.run(['tmux', 'kill-session', '-t', stream['session_name']], check=False)
        
        streams = [s for s in streams if s['id'] != stream_id]
        save_telegram_streams(streams)
        
        return jsonify({'success': True, 'message': 'تم حذف البث'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/telegram/stream/logs/<stream_id>')
def api_telegram_stream_logs(stream_id):
    """الحصول على سجلات بث معين"""
    try:
        streams = load_telegram_streams()
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

@app.route('/api/telegram/extract', methods=['POST'])
def api_telegram_extract():
    """استخراج رابط M3U8 من تليجرام باستخدام requests + parsing"""
    try:
        data = request.get_json() or {}
        tg_url = data.get('tg_url', '').strip()
        cookies_text = data.get('cookies', '').strip()
        
        if not tg_url:
            return jsonify({'success': False, 'error': 'يرجى إدخال رابط البث'}), 400
        
        if not cookies_text:
            return jsonify({'success': False, 'error': 'يرجى إدخال كوكيز تليجرام'}), 400
        
        # حفظ ملف الكوكيز
        cookies_file = BASE_DIR / 'temp_tg_cookies.txt'
        try:
            with open(cookies_file, 'w', encoding='utf-8') as f:
                f.write(cookies)
        except Exception as e:
            return jsonify({'success': False, 'error': f'خطأ في حفظ الكوكيز: {str(e)}'}), 500
        
        try:
            # التحقق من وجود yt-dlp
            check_ytdlp = subprocess.run(['which', 'yt-dlp'], capture_output=True)
            if check_ytdlp.returncode != 0:
                if cookies_file.exists():
                    cookies_file.unlink()
                return jsonify({
                    'success': False,
                    'error': 'yt-dlp غير مثبت. قم بتثبيته أولاً: pip install yt-dlp'
                }), 500
            
            # استخراج الرابط
            result = subprocess.run(
                ['yt-dlp', '--cookies', str(cookies_file), '--get-url', '-f', 'best', tg_url],
                capture_output=True,
                text=True,
                timeout=45,
                cwd=str(BASE_DIR)
            )
            
            # حذف ملف الكوكيز
            if cookies_file.exists():
                cookies_file.unlink()
            
            # معالجة النتيجة
            if result.returncode != 0:
                error_msg = result.stderr or 'فشل الاستخراج'
                return jsonify({
                    'success': False, 
                    'error': f'خطأ في yt-dlp: {error_msg[:200]}'
                }), 500
            
            # البحث عن الرابط
            stream_url = None
            output_lines = result.stdout.strip().split('\n')
            
            # البحث عن M3U8 أولاً
            for line in output_lines:
                if line.startswith('http') and '.m3u8' in line:
                    stream_url = line.strip()
                    break
            
            # إذا لم نجد M3U8، نأخذ أي رابط HTTP
            if not stream_url:
                for line in output_lines:
                    if line.startswith('http'):
                        stream_url = line.strip()
                        break
            
            if not stream_url:
                return jsonify({
                    'success': False,
                    'error': 'لم يتم العثور على رابط البث. تأكد أن البث مباشر الآن وملف الكوكيز صحيح'
                }), 500
            
            # تحديد نوع الرابط
            if '.m3u8' in stream_url:
                format_type = 'M3U8 (HLS)'
            elif '.mpd' in stream_url:
                format_type = 'DASH (MPD)'
            else:
                format_type = 'Direct Stream'
            
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # حفظ البيانات
            link_data = {
                'extracted_at': timestamp,
                'telegram_url': tg_url,
                'stream_url': stream_url,
                'format': format_type,
                'status': 'active'
            }
            
            link_file = BASE_DIR / 'telegram_link.json'
            with open(link_file, 'w', encoding='utf-8') as f:
                json.dump(link_data, f, ensure_ascii=False, indent=2)
            
            return jsonify({
                'success': True,
                'stream_url': stream_url,
                'format': format_type,
                'extracted_at': timestamp
            })
            
        except subprocess.TimeoutExpired:
            if 'cookies_file' in locals() and cookies_file.exists():
                cookies_file.unlink()
            return jsonify({
                'success': False,
                'error': 'انتهت مهلة الاستخراج (45 ثانية)'
            }), 500
        except FileNotFoundError:
            if 'cookies_file' in locals() and cookies_file.exists():
                cookies_file.unlink()
            return jsonify({
                'success': False,
                'error': 'yt-dlp غير موجود. ثبته بـ: pip install yt-dlp'
            }), 500
            
    except Exception as e:
        cookies_file = BASE_DIR / 'temp_tg_cookies.txt'
        if cookies_file.exists():
            cookies_file.unlink()
        return jsonify({'success': False, 'error': f'خطأ غير متوقع: {str(e)}'}), 500

@app.route('/api/extract', methods=['POST'])
def api_extract():
    try:
        data = request.get_json() or {}
        fb_url = data.get('fb_url', '').strip()
        cookies = data.get('cookies', '').strip()
        
        if not fb_url:
            return jsonify({'success': False, 'error': 'يرجى إدخال رابط البث'}), 400
        
        if not cookies:
            return jsonify({'success': False, 'error': 'يرجى إدخال محتوى ملف الكوكيز'}), 400
        
        cookies_file = BASE_DIR / 'temp_cookies.txt'
        with open(cookies_file, 'w') as f:
            f.write(cookies)
        
        try:
            result = subprocess.run(
                ['yt-dlp', '--cookies', str(cookies_file), '--get-url', fb_url],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if cookies_file.exists():
                cookies_file.unlink()
            
            if result.returncode != 0:
                return jsonify({
                    'success': False, 
                    'error': 'فشل الاستخراج - تأكد من أن البث مباشر الآن وملف الكوكيز صحيح'
                }), 500
            
            stream_url = None
            for line in result.stdout.split('\n'):
                if line.startswith('http'):
                    stream_url = line.strip()
                    break
            
            if not stream_url:
                return jsonify({
                    'success': False,
                    'error': 'لم يتم العثور على رابط البث'
                }), 500
            
            format_type = 'M3U8 (HLS)' if '.m3u8' in stream_url else 'DASH (MPD)'
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            link_data = {
                'extracted_at': timestamp,
                'facebook_url': fb_url,
                'stream_url': stream_url,
                'format': format_type,
                'status': 'active'
            }
            
            link_file = BASE_DIR / 'link.json'
            with open(link_file, 'w', encoding='utf-8') as f:
                json.dump(link_data, f, ensure_ascii=False, indent=2)
            
            return jsonify({
                'success': True,
                'stream_url': stream_url,
                'format': format_type,
                'extracted_at': timestamp
            })
            
        except subprocess.TimeoutExpired:
            if cookies_file.exists():
                cookies_file.unlink()
            return jsonify({
                'success': False,
                'error': 'انتهت مهلة الاستخراج'
            }), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    LOGS_DIR.mkdir(exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=False)
