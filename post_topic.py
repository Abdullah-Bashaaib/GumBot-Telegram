import os
import sys
import re
import html
import requests
from datetime import datetime

# ---------- الإعدادات من متغيرات البيئة ----------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

if not BOT_TOKEN or not CHANNEL_ID:
    print("❌ يجب تعيين BOT_TOKEN و CHANNEL_ID كمتغيرات بيئة")
    sys.exit(1)

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
DORAR_BASE = "https://api.dorar.net"

# ---------- دالة تنظيف النص ----------
def clean_text(text):
    """إزالة أي روابط، إشارات للمصدر، أو كلمات مفتاحية من النص"""
    if not text:
        return ""
    # إزالة الروابط
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'www\.\S+', '', text)
    # إزالة إشارات موقع الدرر السنية
    text = re.sub(r'الدرر السنية', '', text, flags=re.IGNORECASE)
    text = re.sub(r'dorar\.net', '', text, flags=re.IGNORECASE)
    # إزالة أي سطر يبدأ بـ "المصدر:" أو "الرابط:" إلخ
    text = re.sub(r'^(?:المصدر|الرابط|مصدر|رابط)\s*:?\s*.*$', '', text,
                  flags=re.MULTILINE | re.IGNORECASE)
    # إزالة فراغات زائدة
    text = re.sub(r'\n\s*\n', '\n', text)
    text = re.sub(r' +', ' ', text).strip()
    return text

# ---------- دوال جلب المحتوى ----------
def fetch_hadith():
    resp = requests.get(f"{DORAR_BASE}/hadith/random")
    resp.raise_for_status()
    data = resp.json()
    hadith_text = data.get("hadith", "").strip()
    sharh = data.get("sharh", "").strip()
    if not hadith_text:
        raise Exception("الحديث فارغ")
    return clean_text(hadith_text), clean_text(sharh)

def fetch_fiqh():
    resp = requests.get(f"{DORAR_BASE}/feqhia/random")
    resp.raise_for_status()
    data = resp.json()
    question = data.get("question", "").strip()
    answer = data.get("answer", "").strip()
    if not question:
        raise Exception("السؤال الفقهي فارغ")
    return clean_text(question), clean_text(answer)

def fetch_aqeeda():
    resp = requests.get(f"{DORAR_BASE}/aqadia/random")
    resp.raise_for_status()
    data = resp.json()
    title = data.get("title", "").strip()
    content = data.get("content", "").strip()
    if not title:
        raise Exception("عنوان العقيدة فارغ")
    return clean_text(title), clean_text(content)

# ---------- تنسيق الرسائل (بدون روابط) ----------
def format_hadith_message(hadith_text, sharh):
    text = (
        "\ud83d\udcdc <b>حديث اليوم</b>\n\n"
        f"<b>الحديث:</b>\n{html.escape(hadith_text)}\n\n"
    )
    if sharh:
        text += f"<b>الشرح:</b>\n{html.escape(sharh)}"
    return text

def format_fiqh_message(question, answer):
    text = (
        "\ud83d\udcda <b>سؤال فقهي</b>\n\n"
        f"<b>السؤال:</b>\n{html.escape(question)}\n\n"
    )
    if answer:
        text += f"<b>الجواب:</b>\n{html.escape(answer)}"
    return text

def format_aqeeda_message(title, content):
    text = (
        "\ud83c\udfea <b>في العقيدة</b>\n\n"
        f"<b>{html.escape(title)}</b>\n"
    )
    if content:
        text += f"\n{html.escape(content)}"
    return text

# ---------- إرسال الرسالة ----------
def send_message(text):
    url = f"{TELEGRAM_API}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    r = requests.post(url, json=payload)
    if r.status_code != 200:
        raise Exception(f"فشل الإرسال: {r.text}")
    print("\u2705 تم إرسال الرسالة بنجاح")

# ---------- الدالة الرئيسية ----------
def main():
    if len(sys.argv) < 2:
        print("❌ استخدم: python post_topic.py [hadith|fiqh|aqeeda]")
        sys.exit(1)

    topic_type = sys.argv[1].lower()

    try:
        if topic_type == "hadith":
            hadith_text, sharh = fetch_hadith()
            msg = format_hadith_message(hadith_text, sharh)
        elif topic_type == "fiqh":
            question, answer = fetch_fiqh()
            msg = format_fiqh_message(question, answer)
        elif topic_type == "aqeeda":
            title, content = fetch_aqeeda()
            msg = format_aqeeda_message(title, content)
        else:
            print("❌ نوع غير معروف. استخدم hadith, fiqh أو aqeeda")
            sys.exit(1)

        # طباعة الرسالة لتسجيل الخروج (لأغراض المراقبة)
        print("--- رسالة سيتم إرسالها ---")
        print(msg)
        print("---------------------------")

        send_message(msg)

    except Exception as e:
        print(f"❌ خطأ: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
