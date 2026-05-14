# -*- coding: utf-8 -*-
import os
import sys
import re
import random
import requests
import unicodedata

# ---------- الإعدادات ----------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

if not BOT_TOKEN or not CHANNEL_ID:
    print("❌ يجب تعيين BOT_TOKEN و CHANNEL_ID")
    sys.exit(1)

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ---------- قواميس الترجمة ----------
COLLECTION_NAMES_AR = {
    "sahih bukhari": "صحيح البخاري",
    "sahih muslim": "صحيح مسلم",
    "jami at-tirmidhi": "جامع الترمذي",
    "sunan abi dawud": "سنن أبي داود",
    "Sunan Abu Dawud":"سنن أبي داود",
    "sunan an-nasa'i": "سنن النسائي",
    "sunan ibn majah": "سنن ابن ماجه",
    "muwatta malik": "موطأ مالك",
    "musnad ahmad": "مسند أحمد",
    "riyad as-salihin": "رياض الصالحين",
    "al-adab al-mufrad": "الأدب المفرد",
    "bulugh al-maram": "بلوغ المرام",
    "shama'il muhammadiyyah": "الشمائل المحمدية",
    "forty hadith an-nawawi": "الأربعون النووية",
    "forty hadith nawawi": "الأربعون النووية",
    "sunan ad-darimi": "سنن الدارمي",
}

GRADE_AR = {
    "sahih": "صحيح",
    "hasan": "حسن",
    "daif": "ضعيف",
    "mauquf sahih": "صحيح موقوف",
    "hasan sahih": "حسن صحيح",
    "sahih hasan": "صحيح حسن",
    "maudhu": "موضوع",
    "munkar": "منكر",
}

ACCEPTED_GRADES = ["sahih", "hasan", "sahih hasan", "hasan sahih", "mauquf sahih"]

def translate_collection(name_en):
    if not name_en:
        return ""
    return COLLECTION_NAMES_AR.get(name_en.lower().strip(), name_en)

def translate_grade(grade_en):
    if not grade_en:
        return ""
    return GRADE_AR.get(grade_en.lower().strip(), grade_en)

def is_accepted_grade(grade_en):
    if not grade_en:
        return False
    return grade_en.lower().strip() in ACCEPTED_GRADES

# ---------- تنظيف النص العربي ----------
def clean_arabic(text):
    if not text:
        return ""
    text = re.sub(
        r'[\u200b\u200c\u200d\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2060\u2061\u2062\u2063\u2064\u2066\u2067\u2068\u2069\uFEFF]',
        '', text)
    text = unicodedata.normalize('NFC', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# ---------- هروب أحرف MarkdownV2 ----------
def escape_markdown_v2(text):
    if not text:
        return ""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

# ---------- جلب حديث صحيح ----------
def fetch_hadith():
    max_attempts = 10
    for attempt in range(1, max_attempts + 1):
        print(f"📜 محاولة {attempt} لجلب حديث صحيح...")
        try:
            resp = requests.get("https://ummahapi.com/api/hadith/random", timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"   ⚠️ فشل الاتصال: {e}")
            continue

        if not data.get("success"):
            print("   ⚠️ API لم يُرجع نجاحًا")
            continue

        hadith_data = data["data"]
        arabic_text = hadith_data.get("arabic", "").strip()
        collection = hadith_data.get("collection_name", "")
        number = hadith_data.get("hadithnumber", "")
        grade = hadith_data.get("grade", "")

        if not arabic_text:
            print("   ⚠️ نص فارغ")
            continue

        if not is_accepted_grade(grade):
            grade_ar = translate_grade(grade) or grade
            print(f"   ⚠️ الحديث {grade_ar} مرفوض")
            continue

        arabic_text = clean_arabic(arabic_text)
        collection_ar = translate_collection(collection)
        grade_ar = translate_grade(grade)
        print(f"   ✅ حديث مقبول: {grade_ar}")
        return arabic_text, collection_ar, number, grade_ar

    raise Exception("لم نعثر على حديث صحيح بعد عدة محاولات")

# ---------- تنسيق الرسالة (MarkdownV2 مع اقتباس) ----------
def format_hadith(arabic_text, collection, number, grade):
    text_escaped = escape_markdown_v2(arabic_text)
    collection_esc = escape_markdown_v2(collection) if collection else ""
    grade_esc = escape_markdown_v2(grade) if grade else ""
    number_esc = str(number) if number else ""

    msg = "📜 *حديث اليوم*\n\n"
    msg += f"> {text_escaped}\n\n"

    info = []
    if collection_esc:
        info.append(f"📖 *المصدر:* {collection_esc}")
    if number_esc:
        info.append(f"🔢 *رقم الحديث:* {number_esc}")
    if info:
        msg += " • ".join(info) + "\n"
    if grade_esc:
        msg += f"✅ *الحكم:* {grade_esc}"

    return msg

# ---------- إرسال الرسالة ----------
def send_message(text):
    url = f"{TELEGRAM_API}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": text,
        "parse_mode": "MarkdownV2",
        "disable_web_page_preview": True
    }
    r = requests.post(url, json=payload)
    if r.status_code != 200:
        print(f"❌ فشل الإرسال: {r.text}")
        raise Exception(f"فشل الإرسال: {r.text}")
    print("✅ تم إرسال الرسالة بنجاح")

# ---------- تشغيل ----------
def main():
    if len(sys.argv) < 2:
        print("❌ استخدم: python post_topic.py [hadith]")
        sys.exit(1)

    topic = sys.argv[1].lower()
    if topic != "hadith":
        print("❌ هذا السكريبت مخصص للحديث فقط")
        sys.exit(1)

    try:
        arabic, col, num, grade = fetch_hadith()
        msg = format_hadith(arabic, col, num, grade)

        print("\n" + "=" * 40)
        print(msg)
        print("=" * 40 + "\n")

        send_message(msg)
        print("✅ تم إرسال حديث واحد بنجاح")

    except Exception as e:
        print(f"❌ خطأ: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
