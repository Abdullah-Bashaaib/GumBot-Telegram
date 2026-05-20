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

# 🎯 معرف الملصق الثابت
STICKER_FILE_ID = "CAACAgQAAxkBAAFJ0dFqCNqgqqCjECNmTxnrb4BkgfqbQgACOQ4AAmzbwVJxfz2bNDpn8TsE"

if not BOT_TOKEN or not CHANNEL_IDS_RAW:
    print("❌ يجب تعيين BOT_TOKEN و CHANNEL_IDS")
    sys.exit(1)

CHANNEL_LIST = [ch.strip() for ch in CHANNEL_IDS_RAW.split(',') if ch.strip()]
print(f"📡 القنوات المستهدفة: {CHANNEL_LIST}")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ========== المصدر الاحتياطي العام ==========
FALLBACK_SOURCE = "https://www.alukah.net/rss/articles/"

# ========== المصادر الأساسية حسب اليوم ==========
RSS_SCHEDULE = {
    0: "https://www.alukah.net/rss/articles/",       # الاثنين - الألوكة
    2: "https://www.alukah.net/rss/articles/",       # الأربعاء - الألوكة
    4: "https://www.alukah.net/rss/articles/",       # الجمعة - الألوكة
    5: "https://munajjid.com/feed",                  # السبت - المنجد
}

# ========== أسماء المصادر ==========
SOURCE_NAMES = {
    "alukah.net": "شبكة الألوكة",
    "munajjid.com": "موقع الشيخ المنجد",
}

def get_source_name(url):
    for key, name in SOURCE_NAMES.items():
        if key in url:
            return name
    return url

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
    """جلب مقال من مصدر واحد - ترجع دائماً 4 قيم"""
    source_name = get_source_name(url)
    print(f"📡 محاولة: {source_name} ({url})")
    try:
        feed = feedparser.parse(url)
        if not feed.entries:
            print(f"   ⚠️ لا توجد مقالات")
            return None, None, None, None  # ← 4 قيم

        entry = feed.entries[0]
        title = entry.get("title", "").strip()
        link = entry.get("link", "")
        summary = entry.get("summary", "") or entry.get("description", "")
        summary = clean_summary(summary)

        # تاريخ النشر
        pub_date = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            pub_date = datetime.datetime(*entry.published_parsed[:6])

        if not title:
            print(f"   ⚠️ عنوان فارغ")
            return None, None, None, None  # ← 4 قيم

        print(f"   ✅ وجدنا: {title[:50]}...")
        return title, link, summary, pub_date

    except Exception as e:
        print(f"   ⚠️ فشل: {e}")
        return None, None, None, None  # ← 4 قيم

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

    # ======== 🔧 وضع التجربة ========
    TEST_MODE = True
    # ================================

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

    # تحديد المصادر
    primary_source = RSS_SCHEDULE.get(today)
    
    if not primary_source:
        msg = f"اليوم ({day_name}) لا توجد له مصادر RSS مخصصة.\nلم يتم نشر أي مقال."
        print(f"ℹ️ {msg}")
        notify_admin(msg, is_error=False)
        sys.exit(0)

    try:
        # محاولة المصدر الأساسي
        title, link, summary, pub_date = fetch_single_feed(primary_source)
        source_name = get_source_name(primary_source)
        used_fallback = False

        # إذا فشل، نجرب الاحتياطي
        if not title:
            print(f"⚠️ فشل المصدر الأساسي، نجرب الاحتياطي...")
            title, link, summary, pub_date = fetch_single_feed(FALLBACK_SOURCE)
            source_name = get_source_name(FALLBACK_SOURCE)
            used_fallback = True

        if not title:
            raise Exception(f"فشل جلب المقال من المصدر الأساسي والاحتياطي")

        # إشعار الأدمن
        admin_info = format_admin_info(source_name, pub_date)
        if used_fallback:
            admin_info += "\n⚠️ تم استخدام المصدر الاحتياطي (الألوكة)."
        notify_admin(admin_info, is_error=False)

        # مقال القناة
        article_msg = format_article_message(title, link, summary, test_mode=TEST_MODE)

        if TEST_MODE:
            print("🧪 وضع التجربة: إرسال إلى الأدمن فقط")
            full_msg = f"{admin_info}\n\n{article_msg}"
            if send_to_admin_article(full_msg):
                print("✅ تم إرسال المقال + الملصق إلى الأدمن للتجربة")
            else:
                raise Exception("فشل إرسال المقال إلى الأدمن")
        else:
            sent = broadcast_article(article_msg)
            print(f"✅ أُرسل المقال + الملصق إلى {sent} قناة")
            if sent == 0:
                raise Exception("لم يتم الإرسال لأي قناة")

    except Exception as e:
        err = str(e)
        print(f"❌ خطأ: {err}")
        notify_admin(f"حدث خطأ أثناء معالجة مقال يوم {day_name}:\n{err}")
        sys.exit(1)

if __name__ == "__main__":
    main()