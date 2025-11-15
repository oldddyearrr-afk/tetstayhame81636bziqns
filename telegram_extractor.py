#!/usr/bin/env python3
"""
Telegram Live Stream Extractor using Browser Automation
استخراج روابط M3U8 من بثوث تليجرام
"""

import os
import re
import time
import json
from pathlib import Path

def extract_from_browser_network(instructions_only=True):
    """
    دليل استخراج رابط M3U8 من تليجرام باستخدام المتصفح
    """
    guide = """
╔════════════════════════════════════════════════════════════════╗
║  📺 كيف تستخرج رابط M3U8 من بث تليجرام مباشر               ║
╚════════════════════════════════════════════════════════════════╝

🔹 الطريقة 1: Chrome/Firefox Developer Tools (الأفضل)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. افتح web.telegram.org وسجل دخول
2. افتح البث المباشر
3. اضغط F12 (Developer Tools)
4. اختر Tab "Network"
5. في صندوق Filter اكتب: m3u8
6. ابدأ تشغيل الفيديو
7. ستظهر ملفات مثل:
   - master.m3u8
   - index.m3u8  
   - playlist.m3u8
8. انقر بزر الماوس الأيمن → Copy → Copy link address
9. الصق الرابط في حقل "مصدر البث"

✅ الرابط يبدو كالتالي:
https://...cdn.telegram.org/.../master.m3u8


🔹 الطريقة 2: Firefox Stream Detector (أسهل)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. ثبت إضافة "The Stream Detector" على Firefox
2. افتح web.telegram.org
3. شغل البث المباشر
4. الإضافة ستكشف الرابط تلقائياً
5. اضغط على الإضافة وانسخ الرابط


🔹 الطريقة 3: Chrome Video DownloadHelper
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. ثبت "Video DownloadHelper" على Chrome
2. افتح البث في web.telegram.org
3. شغل الفيديو
4. اضغط على أيقونة الإضافة
5. ستظهر قائمة بالروابط المتاحة
6. اختر M3U8 وانسخ الرابط


⚠️  ملاحظات مهمة:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• الرابط صالح لفترة محدودة (عدة ساعات)
• استخدم الرابط فوراً بعد الاستخراج
• إذا انتهت صلاحيته، كرر العملية
• البث يجب أن يكون مباشر (Live) أثناء الاستخراج


🎯 مثال على رابط صحيح:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

https://vk4.cdn.telegram.org/file/stream/1234567890/master.m3u8?token=abc123...

"""
    print(guide)
    return guide


def extract_with_requests(telegram_url, cookies_file=None):
    """
    محاولة استخراج الرابط باستخدام requests (قد لا يعمل دائماً)
    """
    import requests
    from bs4 import BeautifulSoup
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://web.telegram.org/',
        'Accept': '*/*'
    }
    
    # إذا كان هناك ملف كوكيز
    cookies = {}
    if cookies_file and os.path.exists(cookies_file):
        with open(cookies_file, 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    parts = line.strip().split('\t')
                    if len(parts) >= 7:
                        cookies[parts[5]] = parts[6]
    
    try:
        response = requests.get(telegram_url, headers=headers, cookies=cookies, timeout=30)
        
        # البحث عن روابط M3U8 في المحتوى
        m3u8_pattern = r'https?://[^\s<>"]+?\.m3u8[^\s<>"]*'
        m3u8_urls = re.findall(m3u8_pattern, response.text)
        
        if m3u8_urls:
            print("✅ تم العثور على روابط M3U8:")
            for i, url in enumerate(m3u8_urls, 1):
                print(f"{i}. {url}")
            return m3u8_urls[0]
        else:
            print("❌ لم يتم العثور على روابط M3U8")
            print("💡 جرب الطريقة اليدوية باستخدام Developer Tools")
            return None
            
    except Exception as e:
        print(f"❌ خطأ: {e}")
        return None


def save_extracted_link(stream_url, telegram_url):
    """حفظ الرابط المستخرج"""
    data = {
        'extracted_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'telegram_url': telegram_url,
        'stream_url': stream_url,
        'format': 'M3U8 (HLS)',
        'status': 'active',
        'method': 'manual_browser_extraction'
    }
    
    with open('telegram_extracted_link.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ تم حفظ الرابط في: telegram_extracted_link.json")


if __name__ == '__main__':
    import sys
    
    print("="*60)
    print("📺 Telegram Live Stream M3U8 Extractor")
    print("="*60)
    print()
    
    # عرض الدليل
    extract_from_browser_network()
    
    print()
    print("="*60)
    print("هل تريد محاولة الاستخراج التلقائي؟ (قد لا يعمل)")
    print("="*60)
    
    if len(sys.argv) > 1:
        telegram_url = sys.argv[1]
        cookies_file = sys.argv[2] if len(sys.argv) > 2 else None
        
        print(f"\n🔍 محاولة استخراج من: {telegram_url}")
        result = extract_with_requests(telegram_url, cookies_file)
        
        if result:
            save_extracted_link(result, telegram_url)
    else:
        print("\nللاستخراج التلقائي:")
        print("python telegram_extractor.py <رابط_البث> [ملف_الكوكيز]")
