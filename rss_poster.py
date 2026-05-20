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
ADMIN_ID = os.environ.get("ADMIN_ID")

STICKER_FILE_ID = "CAACAgQAAxkBAAFJ0dFqCNqgqqCjECNmTxnrb4BkgfqbQgACOQ4AAmzbwVJxfz2bNDpn8TsE"

if not BOT_TOKEN or not CHANNEL_IDS_RAW:
    print("❌ يجب تعيين BOT_TOKEN و CHANNEL_IDS")
    sys.exit(1)

CHANNEL_LIST = [ch.strip() for ch in CHANNEL_IDS_RAW.split(',') if ch.strip()]
print(f"📡 القنوات المستهدفة: {CHANNEL_LIST}")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ========== جميع المصادر المتاحة (تُجرب كلها) ==========
ALL_SOURCES = [
    "https://www.alukah.net/rss/articles/",        # شبكة الألوكة
    "https://munajjid.com/feed",                   # موقع الشيخ المنجد
    "https://feeds.feedburner.com/IslamwayAr",     # طريق الإسلام
    "https://www.islamweb.net/ar/rss/articles/",    # إسلام ويب
]

# ========== أسماء المصادر ==========
SOURCE_NAMES = {
    "alukah.net": "شبكة الألوكة",
    "munajjid.com": "موقع الشيخ المنجد",
    "Islamway": "طريق الإسلام",
    "islamweb": "إسلام ويب",
}

def get_source_name(url):
    for key, name in SOURCE_NAMES.items():
        if key in url:
            return name
    return url

# ========== المصادر الأساسية حسب اليوم (اختياري) ==========
RSS_SCHEDULE = {
    0: "https://www.alukah.net/rss/articles/",       # الاثنين
    2: "https://www.alukah.net/rss/articles/",       # الأربعاء
    4: "https://www.alukah.net/rss/articles/",       # الجمعة
    5: "https://munajjid.com/feed",                  # السبت
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
    url = f"{TELEGRAM_API}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    try:
        r = requests.post(url, json=payload)
        if r.status_code == 200:
            print(f"✅ تم الإرسال إلى {chat_id}")
            return True
        else:
            print(f"⚠️ فشل إرسال رسالة إلى {chat_id}: {r.text}")
            return False
    except Exception as e:
        print(f"⚠️ خطأ: {e}")
        return False

def send_telegram_sticker(chat_id):
    url = f"{TELEGRAM_API}/sendSticker"
    payload = {
        "chat_id": chat_id,
        "sticker": STICKER_FILE_ID
    }
    try:
        r = requests.post(url, json=payload)
        if r.status_code == 200:
            print(f"🎯 تم إرسال الملصق إلى {chat_id}")
            return True
        else:
            print(f"⚠️ فشل إرسال الملصق إلى {chat_id}: {r.text}")
            return False
    except Exception as e:
        print(f"⚠️ خطأ في إرسال الملصق إلى {chat_id}: {e}")
        return False

def broadcast_article(text):
    success = 0
    for ch in CHANNEL_LIST:
        if send_telegram_message(ch, text):
            send_telegram_sticker(ch)
            success += 1
    return success

def send_to_admin_article(text):
    if not ADMIN_ID:
        return False
    if send_telegram_message(ADMIN_ID, text):
        send_telegram_sticker(ADMIN_ID)
        return True
    return False

def notify_admin(msg, is_error=True):
    if ADMIN_ID:
        if is_error:
            full_msg = f"📡 <b>تنبيه RSS</b>\n\n{msg}"
        else:
            full_msg = f"ℹ️ <b>معلومة RSS</b>\n\n{msg}"
        send_telegram_message(ADMIN_ID, full_msg)

def fetch_single_feed(url):
    """جلب مقال من مصدر واحد"""
    source_name = get_source_name(url)
    print(f"📡 محاولة: {source_name} ({url})")
    try:
        feed = feedparser.parse(url)
        if not feed.entries:
            print(f"   ⚠️ لا توجد مقالات")
            return None, None, None, None
        entry = feed.entries[0]
        title = entry.get("title", "").strip()
        link = entry.get("link", "")
        summary = entry.get("summary", "") or entry.get("description", "")
        summary = clean_summary(summary)

        pub_date = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            pub_date = datetime.datetime(*entry.published_parsed[:6])

        if not title:
            print(f"   ⚠️ عنوان فارغ")
            return None, None, None, None

        print(f"   ✅ وجدنا: {title[:50]}...")
        return title, link, summary, pub_date
    except Exception as e:
        print(f"   ⚠️ فشل: {e}")
        return None, None, None, None

def format_article_message(title, link, summary, test_mode=False):
    msg = ""
    if test_mode:
        msg += "🧪 <b>[رسالة تجربة - للأدمن فقط]</b>\n\n"
    msg += f"📰 <b>{html.escape(title)}</b>\n\n"
    if summary:
        msg += f"{html.escape(summary)}\n\n"
    if link:
        msg += f"🔗 <a href='{link}'>رابط المقال</a>"
    return msg

def format_admin_info(source_name, pub_date):
    info = f"📡 <b>المصدر:</b> {html.escape(source_name)}"
    if pub_date:
        date_str = pub_date.strftime("%Y-%m-%d %H:%M")
        info += f"\n📅 <b>تاريخ النشر:</b> {date_str}"
    return info

# ========== الرئيسية ==========
def main():
    today = datetime.datetime.now().weekday()
    day_name = WEEKDAYS_AR.get(today, str(today))
    print(f"📅 اليوم: {day_name}")

    TEST_MODE = True

    # رسالة اختبار للأدمن
    if ADMIN_ID:
        print("🧪 اختبار: جاري إرسال رسالة اختبار للأدمن...")
        test_msg = "✅ <b>اختبار RSS</b>\n\nإذا وصلتك هذه الرسالة، فالإعدادات صحيحة."
        ok = send_telegram_message(ADMIN_ID, test_msg)
        if ok:
            send_telegram_sticker(ADMIN_ID)
            print("✅ وصلت رسالة الاختبار للأدمن.")
        else:
            print("❌ فشل إرسال رسالة الاختبار للأدمن.")
    else:
        print("⚠️ ADMIN_ID غير معين – لا يمكن إرسال الاختبار.")

    # --- بناء قائمة المصادر للتجربة ---
    sources_to_try = []

    # 1. المصدر الأساسي لليوم (إن وجد)
    primary = RSS_SCHEDULE.get(today)
    if primary:
        sources_to_try.append(primary)

    # 2. باقي المصادر (بدون تكرار)
    for src in ALL_SOURCES:
        if src not in sources_to_try:
            sources_to_try.append(src)

    # 3. نحاول كل المصادر حتى نجد مقالاً
    title = link = summary = pub_date = None
    final_source_name = ""

    for src in sources_to_try:
        t, l, s, p = fetch_single_feed(src)
        if t:
            title, link, summary, pub_date = t, l, s, p
            final_source_name = get_source_name(src)
            break

    if not title:
        # جميع المصادر فشلت
        msg = f"جميع المصادر فشلت في يوم {day_name}.\nلم يتم نشر أي مقال."
        print(f"❌ {msg}")
        notify_admin(msg)
        sys.exit(0)  # خروج بدون خطأ برمجي (حتى لا يفشل workflow)

    # إشعار الأدمن
    admin_info = format_admin_info(final_source_name, pub_date)
    if primary and final_source_name != get_source_name(primary):
        admin_info += "\n⚠️ تم استخدام مصدر احتياطي."
    notify_admin(admin_info, is_error=False)

    article_msg = format_article_message(title, link, summary, test_mode=TEST_MODE)

    if TEST_MODE:
        print("🧪 وضع التجربة: إرسال إلى الأدمن فقط")
        full_msg = f"{admin_info}\n\n{article_msg}"
        if send_to_admin_article(full_msg):
            print("✅ تم إرسال المقال + الملصق إلى الأدمن للتجربة")
        else:
            notify_admin("فشل إرسال المقال التجريبي للأدمن.")
    else:
        sent = broadcast_article(article_msg)
        print(f"✅ أُرسل المقال + الملصق إلى {sent} قناة")
        if sent == 0:
            notify_admin("لم يتم الإرسال لأي قناة.")

if __name__ == "__main__":
    main()