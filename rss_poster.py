# -*- coding: utf-8 -*-
import os
import sys
import html
import re
import datetime
import requests
import feedparser

# ========== الإعدادات ==========
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_IDS_RAW = os.environ.get("CHANNEL_IDS")
ADMIN_CHAT_ID = os.environ.get("ADMIN_ID")

if not BOT_TOKEN or not CHANNEL_IDS_RAW:
    print("❌ يجب تعيين BOT_TOKEN و CHANNEL_IDS")
    sys.exit(1)

CHANNEL_LIST = [ch.strip() for ch in CHANNEL_IDS_RAW.split(',') if ch.strip()]
print(f"📡 القنوات المستهدفة (للتجربة - التفعيل للأدمن فقط): {CHANNEL_LIST}")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ========== جدول المصادر حسب اليوم ==========
RSS_SCHEDULE = {
    0: ["https://www.alukah.net/rss/articles/"],      # الاثنين
    2: ["https://ar.islamway.net/rss/articles"],      # الأربعاء
    4: ["https://feeds.feedburner.com/saaid"],        # الجمعة
    5: ["https://munajjid.com/feed"],                 # السبت
}

# ========== أسماء أيام الأسبوع ==========
WEEKDAYS_AR = {
    0: "الاثنين", 1: "الثلاثاء", 2: "الأربعاء",
    3: "الخميس", 4: "الجمعة", 5: "السبت", 6: "الأحد",
}

# ========== دوال مساعدة ==========
def clean_summary(text, max_length=350):
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > max_length:
        text = text[:max_length] + "..."
    return text

def send_telegram_message(chat_id, text):
    """إرسال رسالة إلى محادثة واحدة"""
    url = f"{TELEGRAM_API}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False  # نسمح بمعاينة الرابط للتجربة
    }
    try:
        r = requests.post(url, json=payload)
        if r.status_code == 200:
            print(f"✅ تم الإرسال إلى {chat_id}")
            return True
        else:
            print(f"⚠️ فشل إرسال إلى {chat_id}: {r.text}")
            return False
    except Exception as e:
        print(f"⚠️ خطأ: {e}")
        return False

def broadcast(text):
    """إرسال إلى جميع القنوات"""
    success = 0
    for ch in CHANNEL_LIST:
        if send_telegram_message(ch, text):
            success += 1
    return success

def send_to_admin(text):
    """إرسال إلى الأدمن فقط"""
    if not ADMIN_CHAT_ID:
        print("❌ ADMIN_CHAT_ID غير معين")
        return False
    return send_telegram_message(ADMIN_CHAT_ID, text)

def notify_admin(msg):
    """إرسال إشعار خطأ للأدمن"""
    if ADMIN_CHAT_ID:
        full_msg = f"📡 <b>تنبيه RSS</b>\n\n{msg}"
        send_telegram_message(ADMIN_CHAT_ID, full_msg)

def fetch_article_from_sources(sources):
    for url in sources:
        print(f"📡 محاولة: {url}")
        try:
            feed = feedparser.parse(url)
            if not feed.entries:
                print(f"   ⚠️ لا توجد مقالات")
                continue
            entry = feed.entries[0]
            title = entry.get("title", "").strip()
            link = entry.get("link", "")
            summary = entry.get("summary", "") or entry.get("description", "")
            summary = clean_summary(summary)

            if not title:
                print(f"   ⚠️ عنوان فارغ")
                continue

            print(f"   ✅ وجدنا: {title[:50]}...")
            return title, link, summary
        except Exception as e:
            print(f"   ⚠️ فشل: {e}")
            continue
    return None, None, None

def get_today_sources():
    today = datetime.datetime.now().weekday()
    return RSS_SCHEDULE.get(today, [])

def format_article_message(title, link, summary, test_mode=False):
    """تنسيق المقال مع إشارة للتجربة إن وجدت"""
    msg = ""
    if test_mode:
        msg += "🧪 <b>[رسالة تجربة - للأدمن فقط]</b>\n\n"
    msg += f"📰 <b>{html.escape(title)}</b>\n\n"
    if summary:
        msg += f"{html.escape(summary)}\n\n"
    if link:
        msg += f"🔗 <a href='{link}'>رابط المقال</a>"
    return msg

# ========== الرئيسية ==========
def main():
    today = datetime.datetime.now().weekday()
    day_name = WEEKDAYS_AR.get(today, str(today))
    print(f"📅 اليوم: {day_name}")

    # ======== 🔧 وضع التجربة ========
    TEST_MODE = True  # ← اجعلها False عندما تريد النشر الفعلي للقنوات
    # ================================

    sources = get_today_sources()

    if not sources:
        msg = f"اليوم ({day_name}) لا توجد له مصادر RSS مخصصة.\nلم يتم نشر أي مقال."
        print(f"ℹ️ {msg}")
        notify_admin(msg)
        sys.exit(0)

    try:
        title, link, summary = fetch_article_from_sources(sources)
        if not title:
            raise Exception(f"فشل جلب المقال من مصادر يوم {day_name}")

        article_msg = format_article_message(title, link, summary, test_mode=TEST_MODE)

        if TEST_MODE:
            # إرسال للأدمن فقط
            print("🧪 وضع التجربة: إرسال إلى الأدمن فقط")
            if send_to_admin(article_msg):
                print("✅ تم إرسال المقال إلى الأدمن للتجربة")
            else:
                raise Exception("فشل إرسال المقال إلى الأدمن")
        else:
            # إرسال للقنوات (عند الإنتاج)
            sent = broadcast(article_msg)
            print(f"✅ أُرسل المقال إلى {sent} قناة")
            if sent == 0:
                raise Exception("لم يتم الإرسال لأي قناة")

    except Exception as e:
        err = str(e)
        print(f"❌ خطأ: {err}")
        notify_admin(f"حدث خطأ أثناء معالجة مقال يوم {day_name}:\n{err}")
        sys.exit(1)

if __name__ == "__main__":
    main()
