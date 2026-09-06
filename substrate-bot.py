import os
import html
from bs4 import BeautifulSoup
from datetime import datetime
import time
from curl_cffi import requests # استخدام المكتبة الجديدة المتنكرة

API_BASE_URL = 'https://revel77.substack.com/api/v1/posts'

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
    # إرسال الرسالة إلى تليجرام
    response = requests.post(url, json=payload)
    if response.status_code != 200:
        print(f"حدث خطأ أثناء النشر في تليجرام: {response.text}")

def main():
    print("بدء تشغيل السكربت بتخطي الحماية...")
    
    # 1. جلب قائمة المقالات
    url = f"{API_BASE_URL}?limit=1"
    print(f"جاري الاتصال بـ: {url}")
    
    # التنكر كمتصفح كروم لتخطي Cloudflare
    response = requests.get(url, impersonate="chrome")
    print(f"كود الاستجابة من Substack: {response.status_code}")
    
    if response.status_code != 200:
        print(f"فشل الاتصال! تفاصيل الخطأ: {response.text}")
        return

    posts = response.json()
    if not posts:
        print("نجح الاتصال، ولكن لم يتم العثور على أي مقالات!")
        return

    latest_post = posts[0]

    # 2. التحقق من تاريخ النشر
    post_date_str = latest_post.get("post_date", "")
    post_date = post_date_str[:10]
    today_date = datetime.utcnow().strftime("%Y-%m-%d")

    print(f"تاريخ أحدث مقال: {post_date}")
    print(f"تاريخ اليوم (حسب سيرفر GitHub): {today_date}")

    if post_date != today_date:
        print("المقال ليس من اليوم. لن يتم النشر.")
        return

    title = latest_post.get("title")
    slug = latest_post.get("slug")
    link = latest_post.get("canonical_url")
    print(f"تم العثور على مقال جديد: {title}")

    # 3. جلب محتوى المقال الكامل
    print("جاري جلب النص الكامل للمقال...")
    detailed_response = requests.get(f"{API_BASE_URL}/{slug}", impersonate="chrome")
    
    if detailed_response.status_code != 200:
        print(f"فشل في جلب النص الكامل. كود الخطأ: {detailed_response.status_code}")
        return

    detailed_post = detailed_response.json()
    body_html = detailed_post.get("body_html", "")

    # 4. تنظيف النص
    print("جاري تنظيف النص وتجهيز الرسالة...")
    soup = BeautifulSoup(body_html, "html.parser")
    raw_text = soup.get_text(separator='\n\n').strip()
    safe_text = html.escape(raw_text) 

    # 5. تجهيز الرسالة
    full_message = f"📰 <b>{html.escape(title)}</b>\n\n{safe_text}\n\n🔗 <a href='{link}'>الرابط الأصلي</a>"

    # 6. النشر مع التقسيم
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
