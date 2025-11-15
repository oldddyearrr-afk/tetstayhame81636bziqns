#!/usr/bin/env python3
"""
Telegram M3U8 Stream Extractor
استخراج روابط M3U8 من بثوث تليجرام بطريقة تلقائية
"""

import re
import json
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import m3u8


class TelegramM3U8Extractor:
    """مستخرج روابط M3U8 من تليجرام"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9,ar;q=0.8',
            'Referer': 'https://web.telegram.org/',
            'Origin': 'https://web.telegram.org'
        })
    
    def parse_cookies_text(self, cookies_text):
        """تحويل نص الكوكيز إلى dict"""
        cookies = {}
        
        for line in cookies_text.strip().split('\n'):
            line = line.strip()
            
            # تخطي التعليقات والأسطر الفارغة
            if not line or line.startswith('#'):
                continue
            
            # Netscape format: domain, flag, path, secure, expiration, name, value
            parts = line.split('\t')
            if len(parts) >= 7:
                cookies[parts[5]] = parts[6]
            # Simple format: name=value
            elif '=' in line:
                name, value = line.split('=', 1)
                cookies[name.strip()] = value.strip()
        
        return cookies
    
    def extract_m3u8_from_html(self, html_content, base_url):
        """استخراج روابط M3U8 من HTML"""
        m3u8_urls = []
        
        # البحث باستخدام regex
        patterns = [
            r'https?://[^\s<>"\']+?\.m3u8[^\s<>"\']*',
            r'"(https?://[^"]+\.m3u8[^"]*)"',
            r"'(https?://[^']+\.m3u8[^']*)'",
        ]
        
        for pattern in patterns:
            found = re.findall(pattern, html_content)
            m3u8_urls.extend(found)
        
        # البحث في script tags
        soup = BeautifulSoup(html_content, 'html.parser')
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string:
                found = re.findall(r'https?://[^\s<>"\']+?\.m3u8[^\s<>"\']*', script.string)
                m3u8_urls.extend(found)
        
        # إزالة المكررات
        unique_urls = list(set(m3u8_urls))
        
        # ترتيب حسب الأولوية (master.m3u8 أولاً)
        unique_urls.sort(key=lambda x: (
            'master.m3u8' not in x.lower(),
            'playlist.m3u8' not in x.lower(),
            'index.m3u8' not in x.lower()
        ))
        
        return unique_urls
    
    def try_common_cdn_patterns(self, telegram_url):
        """محاولة الأنماط الشائعة لـ CDN تليجرام"""
        # استخراج معرف القناة/المجموعة من الرابط
        match = re.search(r't\.me/([^/]+)', telegram_url)
        if not match:
            return []
        
        # أنماط CDN الشائعة لتليجرام
        cdn_patterns = [
            'https://vcdn{}.telegram.org/file/stream/{}/master.m3u8',
            'https://vcdn{}.telegram.org/live/{}/index.m3u8',
            'https://cdn{}.telegram.org/file/{}/playlist.m3u8',
        ]
        
        possible_urls = []
        for i in range(1, 10):
            for pattern in cdn_patterns:
                # جرب أرقام CDN مختلفة
                url = pattern.format(i, 'stream_id')
                possible_urls.append(url)
        
        return possible_urls
    
    def extract_from_telegram(self, telegram_url, cookies_text):
        """
        استخراج رابط M3U8 من تليجرام
        
        Args:
            telegram_url: رابط البث في تليجرام
            cookies_text: نص الكوكيز
        
        Returns:
            dict: معلومات الاستخراج
        """
        result = {
            'success': False,
            'stream_url': None,
            'method': None,
            'error': None,
            'tried_methods': []
        }
        
        # تحليل الكوكيز
        try:
            cookies = self.parse_cookies_text(cookies_text)
            if cookies:
                self.session.cookies.update(cookies)
                result['tried_methods'].append('Parsed cookies successfully')
        except Exception as e:
            result['error'] = f'فشل تحليل الكوكيز: {str(e)}'
            return result
        
        # الطريقة 1: محاولة فتح الصفحة مباشرة
        try:
            result['tried_methods'].append('Method 1: Direct page fetch')
            response = self.session.get(telegram_url, timeout=30)
            
            if response.status_code == 200:
                m3u8_urls = self.extract_m3u8_from_html(response.text, telegram_url)
                
                if m3u8_urls:
                    # التحقق من صلاحية أول رابط
                    test_url = m3u8_urls[0]
                    try:
                        test_response = self.session.head(test_url, timeout=10)
                        if test_response.status_code in [200, 302, 301]:
                            result['success'] = True
                            result['stream_url'] = test_url
                            result['method'] = 'Direct HTML parsing'
                            return result
                    except:
                        pass
        except Exception as e:
            result['tried_methods'].append(f'Method 1 failed: {str(e)}')
        
        # الطريقة 2: محاولة API calls مباشرة
        try:
            result['tried_methods'].append('Method 2: Telegram Web API')
            
            # محاولة استدعاء Telegram Web API
            api_url = 'https://web.telegram.org/k/'
            response = self.session.get(api_url, timeout=30)
            
            if response.status_code == 200:
                # البحث عن API endpoints في الكود
                api_matches = re.findall(r'/api/\w+', response.text)
                result['tried_methods'].append(f'Found {len(api_matches)} API endpoints')
        except Exception as e:
            result['tried_methods'].append(f'Method 2 failed: {str(e)}')
        
        # الطريقة 3: محاولة الأنماط الشائعة
        try:
            result['tried_methods'].append('Method 3: Common CDN patterns')
            possible_urls = self.try_common_cdn_patterns(telegram_url)
            
            for url in possible_urls[:5]:  # جرب أول 5 فقط
                try:
                    test_response = self.session.head(url, timeout=5)
                    if test_response.status_code == 200:
                        result['success'] = True
                        result['stream_url'] = url
                        result['method'] = 'CDN pattern matching'
                        return result
                except:
                    continue
        except Exception as e:
            result['tried_methods'].append(f'Method 3 failed: {str(e)}')
        
        # إذا فشلت جميع الطرق
        result['error'] = 'فشل استخراج الرابط. استخدم الطريقة اليدوية (F12 → Network → m3u8)'
        
        return result


def test_extractor():
    """اختبار المستخرج"""
    extractor = TelegramM3U8Extractor()
    
    print("="*60)
    print("📺 Telegram M3U8 Extractor - اختبار")
    print("="*60)
    
    # مثال
    telegram_url = "https://t.me/example_channel"
    cookies_text = """
# Netscape HTTP Cookie File
.t.me	TRUE	/	FALSE	1234567890	stel_ssid	abc123def456
"""
    
    result = extractor.extract_from_telegram(telegram_url, cookies_text)
    
    print("\n📊 النتيجة:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
    if result['success']:
        print(f"\n✅ تم الاستخراج: {result['stream_url']}")
    else:
        print(f"\n❌ فشل: {result['error']}")
        print(f"\n🔍 الطرق المجربة:")
        for method in result['tried_methods']:
            print(f"   - {method}")


if __name__ == '__main__':
    test_extractor()
