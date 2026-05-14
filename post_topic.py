import os
import sys
import re
import html
import random
import requests
import json

# ---------- الإعدادات ----------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

if not BOT_TOKEN or not CHANNEL_ID:
    print("❌ يجب تعيين BOT_TOKEN و CHANNEL_ID")
    sys.exit(1)

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ---------- 1. جلب حديث عشوائي من ummahapi.com ----------
def fetch_hadith():
    """جلب حديث عشوائي بالعربية من ummahapi"""
    print("📜 جلب حديث عشوائي من ummahapi...")
    resp = requests.get("https://ummahapi.com/api/hadith/random", timeout=15)
    resp.raise_for_status()
    data = resp.json()
    
    if not data.get("success"):
        raise Exception("API لم يُرجع نجاحاً")
    
    hadith_data = data["data"]
    arabic_text = hadith_data.get("arabic", "").strip()
    collection = hadith_data.get("collection_name", "")
    number = hadith_data.get("hadithnumber", "")
    grade = hadith_data.get("grade", "")
    
    if not arabic_text:
        raise Exception("نص الحديث فارغ")
    
    return arabic_text, collection, number, grade

# ---------- 2. جلب مسألة فقهية (ما زلنا نستخدم الدرر) ----------
FIQH_TERMS = [
    "حكم الصلاة", "حكم الصيام", "الطهارة", "الوضوء", "الزكاة",
    "الحج", "النكاح", "الطلاق", "البيع", "الميراث"
]

def fetch_fiqh():
    """جلب مسألة فقهية من موقع الدرر"""
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
        # تنظيف بسيط
        text = re.sub(r'https?://\S+', '', text)
        text = re.sub(r'الدرر السنية|dorar\.net', '', text, flags=re.IGNORECASE)
        text = text.strip()
        if not text:
            raise Exception("نص فارغ")
        # محاولة فصل سؤال وجواب
        q = re.search(r'السؤال\s*:?\s*(.*?)(?:الجواب|$)', text, re.DOTALL)
        a = re.search(r'الجواب\s*:?\s*(.*)', text, re.DOTALL)
        if q and a:
            return q.group(1).strip(), a.group(1).strip()
        return text, ""
    except Exception as e:
        print(f"⚠️ فشل جلب الفقه: {e}")
        return "مسألة فقهية", "لم نتمكن من جلب المحتوى حالياً"

# ---------- 3. جلب موضوع عقيدة (مؤقتاً بنفس الطريقة) ----------
AQEEDA_TERMS = [
    "التوحيد", "أسماء الله", "صفات الله", "الإيمان", "الملائكة",
    "الكتب", "الرسل", "اليوم الآخر", "القدر"
]

def fetch_aqeeda():
    """جلب موضوع عقيدة"""
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
        text = text.strip()
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
        info.append(f"📖 المصدر: {html.escape(collection)}")
    if number:
        info.append(f"🔢 رقم الحديث: {number}")
    if info:
        msg += " | ".join(info) + "\n"
    if grade:
        msg += f"✅ الحكم: {html.escape(grade)}"
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
