import os
import requests
import html
from bs4 import BeautifulSoup
from datetime import datetime
import time

PUBLICATION_NAME = 'lenny' # استبدل باسم النشرة
API_BASE_URL = f'https://{PUBLICATION_NAME}.substack.com/api/v1/posts'

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True # إيقاف المعاينة حتى لا تشتت الانتباه عن النص
    }
    response = requests.post(url, json=payload)
    if response.status_code != 200:
        print(f"حدث خطأ أثناء النشر: {response.text}")

def main():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    # 1. جلب قائمة المقالات لمعرفة أحدث مقال
    response = requests.get(f"{API_BASE_URL}?limit=1", headers=headers)
    if response.status_code != 200:
        return
        
    posts = response.json()
    if not posts:
        return

    latest_post = posts[0]
    
    # 2. التحقق من تاريخ النشر
    post_date_str = latest_post.get("post_date", "")
    post_date = post_date_str[:10]
    today_date = datetime.utcnow().strftime("%Y-%m-%d")
    
    if post_date != today_date:
        print("المقال ليس من اليوم.")
        return

    title = latest_post.get("title")
    slug = latest_post.get("slug")
    link = latest_post.get("canonical_url")

    # 3. جلب محتوى المقال الكامل باستخدام الـ Slug
    detailed_response = requests.get(f"{API_BASE_URL}/{slug}", headers=headers)
    if detailed_response.status_code != 200:
        print("فشل في جلب النص الكامل.")
        return
        
    detailed_post = detailed_response.json()
    body_html = detailed_post.get("body_html", "")

    # 4. تنظيف النص من أكواد HTML وتنسيقه
    soup = BeautifulSoup(body_html, "html.parser")
    # استخراج النص مع وضع مسافات بين الفقرات
    raw_text = soup.get_text(separator='\n\n').strip()
    
    # حماية علامات مثل < و > حتى لا تعطل تنسيق HTML في تليجرام
    safe_text = html.escape(raw_text) 

    # 5. تجهيز الرسالة
    full_message = f"📰 <b>{html.escape(title)}</b>\n\n{safe_text}\n\n🔗 <a href='{link}'>الرابط الأصلي</a>"

    # 6. تقسيم الرسالة إذا تجاوزت حد تليجرام (4096 حرفاً)
    max_length = 4000 
    
    if len(full_message) <= max_length:
        send_telegram_message(full_message)
        print("تم نشر المقال كاملاً في رسالة واحدة!")
    else:
        # تقسيم النص إلى أجزاء
        parts = [full_message[i:i+max_length] for i in range(0, len(full_message), max_length)]
        for index, part in enumerate(parts):
            # إضافة توضيح إذا كانت الرسالة مقسمة
            if index == 0:
                send_telegram_message(part + "\n\n<i>[يتبع...]</i>")
            elif index == len(parts) - 1:
                send_telegram_message(part)
            else:
                send_telegram_message(part + "\n\n<i>[يتبع...]</i>")
            
            # الانتظار لثانية لتجنب حظر تليجرام بسبب سرعة الإرسال (Flood Control)
            time.sleep(1) 
            
        print(f"تم نشر المقال كاملاً ومقسماً على {len(parts)} رسائل!")

if __name__ == '__main__':
    main()
