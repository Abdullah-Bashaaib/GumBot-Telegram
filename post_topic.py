import os
import sys
import re
import html
import requests
import random
from bs4 import BeautifulSoup

# ---------- الإعدادات ----------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

if not BOT_TOKEN or not CHANNEL_ID:
    print("❌ يجب تعيين BOT_TOKEN و CHANNEL_ID")
    sys.exit(1)

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ---------- دالة تنظيف النص ----------
def clean_text(text):
    if not text:
        return ""
    # إزالة وسوم HTML
    text = re.sub(r'<[^>]+>', '', text)
    # إزالة الروابط
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'www\.\S+', '', text)
    # إزالة إشارات المصدر
    text = re.sub(r'الدرر السنية', '', text, flags=re.IGNORECASE)
    text = re.sub(r'dorar\.net', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^(?:المصدر|الرابط|مصدر|رابط)\s*:?\s*.*$', '', text, flags=re.MULTILINE | re.IGNORECASE)
    # تنظيف الفراغات
    text = re.sub(r'\n\s*\n', '\n', text)
    text = re.sub(r' +', ' ', text).strip()
    return text

# ---------- كلمات البحث ----------
HADITH_TERMS = [
    "الصلاة", "الصيام", "الزكاة", "الحج", "الإيمان", "الإحسان",
    "بر الوالدين", "صلة الرحم", "الصدق", "الأمانة", "التقوى",
    "الجنة", "النار", "الذكر", "الدعاء", "الاستغفار", "التوبة",
    "العلم", "الرفق", "الحياء", "حسن الخلق"
]

FIQH_TERMS = [
    "حكم الصلاة", "حكم الصيام", "الطهارة", "الوضوء", "الزكاة",
    "الحج", "النكاح", "الطلاق", "البيع", "الميراث"
]

AQEEDA_TERMS = [
    "التوحيد", "أسماء الله", "صفات الله", "الإيمان بالله",
    "الملائكة", "الكتب", "الرسل", "اليوم الآخر", "القدر"
]

# ---------- دوال جلب المحتوى ----------
def extract_from_html(html_content):
    """استخراج الحديث من HTML"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # البحث عن div الحديث
    hadith_div = soup.find('div', class_='hadith')
    if not hadith_div:
        raise Exception("لم يتم العثور على حديث في HTML")
    
    # استخراج النص
    hadith_text = hadith_div.get_text(separator=' ', strip=True)
    # إزالة الترقيم في البداية مثل "1 -"
    hadith_text = re.sub(r'^\d+\s*-\s*', '', hadith_text).strip()
    
    # محاولة استخراج الشرح (قد لا يكون موجوداً)
    sharh = ""
    info_div = soup.find('div', class_='hadith-info')
    if info_div:
        sharh = info_div.get_text(separator=' ', strip=True)
        # تنظيف الشرح
        sharh = re.sub(r'(الراوي|المحدث|المصدر|الصفحة|الرقم|خلاصة الحكم)\s*:', '', sharh)
        sharh = sharh.strip()
    
    return hadith_text, sharh

def fetch_from_dorar(search_term):
    """جلب نتائج من API الدرر السنية"""
    url = f"https://dorar.net/dorar_api.json?skey={search_term}"
    
    print(f"🔍 جاري البحث عن: {search_term}")
    
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        
        ahadith = data.get("ahadith", {})
        
        # التعامل مع الحالات المختلفة
        if isinstance(ahadith, list):
            # قائمة أحاديث
            if len(ahadith) == 0:
                raise Exception("لا توجد نتائج")
            chosen = random.choice(ahadith)
            # إذا كان العنصر dict وليس HTML
            if isinstance(chosen, dict):
                text = chosen.get("hadith", "") or chosen.get("th", "")
                sharh = chosen.get("sharh", "") or chosen.get("sh", "")
                if not text:
                    raise Exception("الحديث لا يحتوي على نص")
                return clean_text(text), clean_text(sharh)
            else:
                # عنصر نصي ربما HTML
                return extract_from_html(str(chosen))
        elif isinstance(ahadith, dict):
            # حالة وجود result (HTML)
            result_html = ahadith.get("result", "")
            if not result_html:
                raise Exception("لا توجد نتائج")
            return extract_from_html(result_html)
        else:
            raise Exception("شكل بيانات غير معروف")
            
    except Exception as e:
        raise Exception(f"فشل جلب المحتوى: {e}")

def fetch_hadith():
    term = random.choice(HADITH_TERMS)
    return fetch_from_dorar(term)

def fetch_fiqh():
    term = random.choice(FIQH_TERMS)
    return fetch_from_dorar(term)

def fetch_aqeeda():
    term = random.choice(AQEEDA_TERMS)
    return fetch_from_dorar(term)

# ---------- تنسيق الرسائل ----------
def format_hadith_message(hadith_text, sharh):
    text = "📜 <b>حديث اليوم</b>\n\n"
    text += f"<b>الحديث:</b>\n{html.escape(hadith_text)}\n\n"
    if sharh:
        text += f"<b>الشرح:</b>\n{html.escape(sharh)}"
    return text

def format_fiqh_message(question, answer):
    text = "📚 <b>مسألة فقهية</b>\n\n"
    text += f"<b>السؤال:</b>\n{html.escape(question)}\n\n"
    if answer:
        text += f"<b>الجواب:</b>\n{html.escape(answer)}"
    return text

def format_aqeeda_message(title, content):
    text = "🕌 <b>في العقيدة</b>\n\n"
    text += f"<b>{html.escape(title)}</b>\n"
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
    print("✅ تم إرسال الرسالة بنجاح")

# ---------- الدالة الرئيسية ----------
def main():
    if len(sys.argv) < 2:
        print("❌ استخدم: python post_topic.py [hadith|fiqh|aqeeda]")
        sys.exit(1)

    topic_type = sys.argv[1].lower()

    try:
        if topic_type == "hadith":
            text, sharh = fetch_hadith()
            msg = format_hadith_message(text, sharh)
        elif topic_type == "fiqh":
            text, sharh = fetch_fiqh()
            msg = format_fiqh_message(text, sharh)
        elif topic_type == "aqeeda":
            text, sharh = fetch_aqeeda()
            msg = format_aqeeda_message(text, sharh)
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
