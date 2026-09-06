import os
import requests
import html
import time
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime

RSS_URL = 'https://revel77.substack.com/feed'

TELEGRAM_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHANNEL_IDS')

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    response = requests.post(url, json=payload)
    if response.status_code != 200:
        print(f"حدث خطأ أثناء النشر في تليجرام: {response.text}")

def main():
    print("بدء تشغيل السكربت عبر تقنية RSS لتجاوز الحماية...")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    # 1. تحميل التغذية يدوياً عبر requests للتمويه
    print("جاري تحميل ملف الـ RSS...")
    response = requests.get(RSS_URL, headers=headers)
    print(f"كود الاستجابة لملف التغذية: {response.status_code}")
    
    if response.status_code != 200:
        print(f"فشل الاتصال! تم رفض الطلب.")
        return

    # 2. تمرير النص المحمل إلى feedparser ليقوم بتحليله
    feed = feedparser.parse(response.text)
    
    if not feed.entries:
        print("الاتصال نجح، لكن لم يتم العثور على أي مقالات في التغذية!")
        print("أول 200 حرف من الرد للتشخيص:")
        print(response.text[:200])
        return

    latest_post = feed.entries[0]

    # 3. التحقق من تاريخ النشر
    if hasattr(latest_post, 'published_parsed'):
        post_date = datetime.fromtimestamp(time.mktime(latest_post.published_parsed)).date()
        today_date = datetime.utcnow().date()
        
        print(f"تاريخ أحدث مقال: {post_date}")
        print(f"تاريخ اليوم (حسب السيرفر): {today_date}")
        
        if post_date != today_date:
            print("المقال ليس من اليوم. لن يتم النشر.")
            return

    title = latest_post.title
    link = latest_post.link
    print(f"تم العثور على مقال جديد: {title}")

    # 4. جلب محتوى المقال الكامل
    print("جاري استخراج محتوى المقال...")
    html_content = ""
    if hasattr(latest_post, 'content'):
        html_content = latest_post.content[0].value
    else:
        html_content = latest_post.summary

    if not html_content:
        print("لم يتم العثور على نص للمقال!")
        return

    # 5. تنظيف النص من أكواد HTML
    print("جاري تنظيف النص وتجهيز الرسالة...")
    soup = BeautifulSoup(html_content, "html.parser")
    raw_text = soup.get_text(separator='\n\n').strip()
    safe_text = html.escape(raw_text) 

    # 6. تجهيز الرسالة
    full_message = f"📰 <b>{html.escape(title)}</b>\n\n{safe_text}\n\n🔗 <a href='{link}'>الرابط الأصلي</a>"

    # 7. النشر مع التقسيم لـ 4000 حرف
    max_length = 4000 

    if len(full_message) <= max_length:
        send_telegram_message(full_message)
        print("تم نشر المقال كاملاً في رسالة واحدة!")
    else:
        parts = [full_message[i:i+max_length] for i in range(0, len(full_message), max_length)]
        for index, part in enumerate(parts):
            if index == 0:
                send_telegram_message(part + "\n\n<i>[يتبع...]</i>")
            elif index == len(parts) - 1:
                send_telegram_message(part)
            else:
                send_telegram_message(part + "\n\n<i>[يتبع...]</i>")
            time.sleep(1) 

        print(f"تم نشر المقال كاملاً ومقسماً على {len(parts)} رسائل!")

if __name__ == '__main__':
    main()
