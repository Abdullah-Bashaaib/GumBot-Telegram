# -*- coding: utf-8 -*-
import os
import sys
import re
import html
import random
import json
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
    "sunan an-nasa'i": "سنن النسائي",
    "sunan ibn majah": "سنن ابن ماجه",
    "muwatta malik": "موطأ مالك",
    "musnad ahmad": "مسند أحمد",
    "riyad as-salihin": "رياض الصالحين",
    "al-adab al-mufrad": "الأدب المفرد",
    "sahih al-bukhari": "صحيح البخاري",
    "sahih muslims": "صحيح مسلم",
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

# الأحكام المقبولة (صحيحة أو حسنة)
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
    """يتحقق مما إذا كان الحكم من الأحكام المقبولة"""
    if not grade_en:
        return False
    return grade_en.lower().strip() in ACCEPTED_GRADES

# ---------- تنظيف النص العربي ----------
def clean_arabic(text):
    if not text:
        return ""
    text = re.sub(r'[\u200b\u200c\u200d\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2060\u2061\u2062\u2063\u2064\u2066\u2067\u2068\u2069\uFEFF]', '', text)
    text = unicodedata.normalize('NFC', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# ---------- 1. جلب حديث عشوائي صحيح أو حسن ----------
def fetch_hadith():
    """يحاول حتى يجد حديثًا صحيحًا أو حسنًا"""
    max_attempts = 10  # عدد المحاولات القصوى لتجنب التكرار اللانهائي
    for attempt in range(1, max_attempts + 1):
        print(f"📜 محاولة {attempt} لجلب حديث...")
        resp = requests.get("https://ummahapi.com/api/hadith/random", timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success"):
            print("   ⚠️ API لم يُرجع نجاحًا، إعادة المحاولة...")
            continue

        hadith_data = data["data"]
        arabic_text = hadith_data.get("arabic", "").strip()
        collection = hadith_data.get("collection_name", "")
        number = hadith_data.get("hadithnumber", "")
        grade = hadith_data.get("grade", "")

        if not arabic_text:
            print("   ⚠️ نص الحديث فارغ، إعادة المحاولة...")
            continue

        if not is_accepted_grade(grade):
            grade_ar = translate_grade(grade) or grade
            print(f"   ⚠️ الحديث {grade_ar} (غير مقبول)، إعادة المحاولة...")
            continue

        # حديث مقبول
        arabic_text = clean_arabic(arabic_text)
        collection_ar = translate_collection(collection)
        grade_ar = translate_grade(grade)
        print(f"   ✅ حديث مقبول: {grade_ar}")
        return arabic_text, collection_ar, number, grade_ar

    raise Exception("لم نعثر على حديث صحيح/حسن بعد عدة محاولات")

# ---------- 2. جلب مسألة فقهية ----------
FIQH_TERMS = [
    "حكم الصلاة", "حكم الصيام", "الطهارة", "الوضوء", "الزكاة",
    "الحج", "النكاح", "الطلاق", "البيع", "الميراث"
]

def fetch_fiqh():
    term = random.choice(FIQH_TERMS)
    print(f"📚 [فقه] البحث عن: {term}")
    try:
        url = f"https://dorar.net/dorar_api.json?skey={term}&callback=jsonp"
        resp = requests.get(url, timeout=20)
        match = re.search(r'jsonp\((.*)\)\s*$', resp.text, re.DOTALL)
        if not match:
            raise Exception("استجابة غير صالحة")
        data = json.loads(match.group(1))
        ahadith = data.get("ahadith", [])
        if not ahadith:
            raise Exception("لا توجد نتائج")
        chosen = random.choice(ahadith)
        text = chosen.get("th") or chosen.get("hadith", "")
        text = re.sub(r'https?://\S+', '', text)
        text = re.sub(r'الدرر السنية|dorar\.net', '', text, flags=re.IGNORECASE)
        text = clean_arabic(text)
        if not text:
            raise Exception("نص فارغ")
        q = re.search(r'السؤال\s*:?\s*(.*?)(?:الجواب|$)', text, re.DOTALL)
        a = re.search(r'الجواب\s*:?\s*(.*)', text, re.DOTALL)
        if q and a:
            return clean_arabic(q.group(1).strip()), clean_arabic(a.group(1).strip())
        return text, ""
    except Exception as e:
        print(f"⚠️ فشل جلب الفقه: {e}")
        return "مسألة فقهية", "لم نتمكن من جلب المحتوى حالياً"

# ---------- 3. جلب موضوع عقيدة ----------
AQEEDA_TERMS = [
    "التوحيد", "أسماء الله", "صفات الله", "الإيمان", "الملائكة",
    "الكتب", "الرسل", "اليوم الآخر", "القدر"
]

def fetch_aqeeda():
    term = random.choice(AQEEDA_TERMS)
    print(f"🕌 [عقيدة] البحث عن: {term}")
    try:
        url = f"https://dorar.net/dorar_api.json?skey={term}&callback=jsonp"
        resp = requests.get(url, timeout=20)
        match = re.search(r'jsonp\((.*)\)\s*$', resp.text, re.DOTALL)
        if not match:
            raise Exception("استجابة غير صالحة")
        data = json.loads(match.group(1))
        ahadith = data.get("ahadith", [])
        if not ahadith:
            raise Exception("لا توجد نتائج")
        chosen = random.choice(ahadith)
        text = chosen.get("th") or chosen.get("hadith", "")
        text = re.sub(r'https?://\S+', '', text)
        text = re.sub(r'الدرر السنية|dorar\.net', '', text, flags=re.IGNORECASE)
        text = clean_arabic(text)
        return text, ""
    except Exception as e:
        print(f"⚠️ فشل جلب العقيدة: {e}")
        return "موضوع في العقيدة", "لم نتمكن من جلب المحتوى حالياً"

# ---------- 4. تنسيق الرسائل ----------
def format_hadith(arabic_text, collection, number, grade):
    msg = "📜 <b>حديث اليوم</b>\n\n"
    msg += f"{html.escape(arabic_text)}\n\n"
    info = []
    if collection:
        info.append(f"📖 <b>المصدر:</b> {html.escape(collection)}")
    if number:
        info.append(f"🔢 <b>رقم الحديث:</b> {number}")
    if info:
        msg += " | ".join(info) + "\n"
    if grade:
        msg += f"✅ <b>الحكم:</b> {html.escape(grade)}"
    return msg

def format_fiqh(question, answer):
    msg = "📚 <b>مسألة فقهية</b>\n\n"
    msg += f"<b>السؤال:</b>\n{html.escape(question)}\n\n"
    if answer:
        short = answer[:1500]
        if len(answer) > 1500:
            short += " ..."
        msg += f"<b>الجواب:</b>\n{html.escape(short)}"
    return msg

def format_aqeeda(title, content):
    msg = "🕌 <b>في العقيدة</b>\n\n"
    msg += f"<b>{html.escape(title)}</b>\n"
    if content:
        short = content[:1500]
        if len(content) > 1500:
            short += " ..."
        msg += f"\n{html.escape(short)}"
    return msg

# ---------- 5. إرسال الرسالة ----------
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
    print("✅ تم إرسال الرسالة بنجاح")

# ---------- 6. الدالة الرئيسية ----------
def main():
    if len(sys.argv) < 2:
        print("❌ استخدم: python post_topic.py [hadith|fiqh|aqeeda]")
        sys.exit(1)

    topic = sys.argv[1].lower()

    try:
        if topic == "hadith":
            arabic, col, num, grade = fetch_hadith()
            msg = format_hadith(arabic, col, num, grade)
        elif topic == "fiqh":
            q, a = fetch_fiqh()
            msg = format_fiqh(q, a)
        elif topic == "aqeeda":
            t, c = fetch_aqeeda()
            msg = format_aqeeda(t, c)
        else:
            print("❌ نوع غير معروف")
            sys.exit(1)

        print("\n" + "="*40)
        print(msg)
        print("="*40 + "\n")
        send_message(msg)

    except Exception as e:
        print(f"❌ خطأ: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
