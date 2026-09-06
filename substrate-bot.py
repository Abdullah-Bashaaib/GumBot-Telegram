import os
import requests
import html
import time
from bs4 import BeautifulSoup
from datetime import datetime

# رابط التغذية الخاص بك
RSS_URL = 'https://revel77.substack.com/feed'
# رابط الخدمة الوسيطة التي ستجلب البيانات نيابة عنا لتخطي الحظر
PROXY_API_URL = f"https://api.rss2json.com/v1/api.json?rss_url={RSS_URL}"

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
    print("بدء تشغيل السكربت باستخدام خدمة الوسيط لتخطي حظر الـ IP...")
    
    # 1. جلب البيانات عبر الوسيط
    print("جاري الاتصال بالوسيط (rss2json)...")
    response = requests.get(PROXY_API_URL)
    
    if response.status_code != 200:
        print(f"فشل الاتصال بالوسيط! كود الخطأ: {response.status_code}")
        return

    data = response.json()
    
    if data.get('status') != 'ok':
        print("الوسيط لم يتمكن من جلب التغذية من Substack.")
        return
        
    items = data.get('items', [])
    if not items:
        print("الاتصال نجح، لكن لا توجد مقالات في التغذية!")
        return

    latest_post = items[0]

    # 2. التحقق من تاريخ النشر
    # الوسيط يعيد التاريخ بصيغة "YYYY-MM-DD HH:MM:SS"
    pub_date_str = latest_post.get('pubDate', '')
    post_date = pub_date_str[:10] # نأخذ أول 10 حروف (YYYY-MM-DD)
    today_date = datetime.utcnow().strftime("%Y-%m-%d")
    
    print(f"تاريخ أحدث مقال: {post_date}")
    print(f"تاريخ اليوم (حسب السيرفر): {today_date}")
    
    if post_date != today_date:
        print("المقال ليس من اليوم. لن يتم النشر.")
        return

    title = latest_post.get('title', '')
    link = latest_post.get('link', '')
    print(f"تم العثور على مقال جديد: {title}")

    # 3. استخراج النص الكامل للمقال
    print("جاري استخراج محتوى المقال...")
    html_content = latest_post.get('content', '')
    if not html_content:
        html_content = latest_post.get('description', '')

    if not html_content:
        print("لم يتم العثور على نص للمقال!")
        return

    # 4. تنظيف النص من أكواد HTML
    print("جاري تنظيف النص وتجهيز الرسالة...")
    soup = BeautifulSoup(html_content, "html.parser")
    raw_text = soup.get_text(separator='\n\n').strip()
    safe_text = html.escape(raw_text) 

    # 5. تجهيز الرسالة
    full_message = f"📰 <b>{html.escape(title)}</b>\n\n{safe_text}\n\n🔗 <a href='{link}'>الرابط الأصلي</a>"

    # 6. النشر مع التقسيم لـ 4000 حرف
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
