import os
import sys
import re
import html
import random
import requests
from bs4 import BeautifulSoup

# ---------- الإعدادات ----------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

if not BOT_TOKEN or not CHANNEL_ID:
    print("❌ يجب تعيين BOT_TOKEN و CHANNEL_ID")
    sys.exit(1)

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ---------- أدوات التنظيف ----------
def clean_text(text):
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'www\.\S+', '', text)
    text = re.sub(r'الدرر السنية', '', text, flags=re.IGNORECASE)
    text = re.sub(r'dorar\.net', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^(?:المصدر|الرابط|مصدر|رابط)\s*:?\s*.*$', '', text, flags=re.MULTILINE | re.IGNORECASE)
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

# ---------- جلب حديث من API واستخراج التفاصيل ----------
def fetch_hadith():
    # 1. استدعاء API بكلمة عشوائية
    term = random.choice(HADITH_TERMS)
    api_url = f"https://dorar.net/dorar_api.json?skey={term}"
    print(f"🔍 جاري البحث عن: {term}")
    resp = requests.get(api_url, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    ahadith = data.get("ahadith", {})
    if not ahadith or "result" not in ahadith:
        raise Exception("لم يتم العثور على نتائج")
    
    result_html = ahadith["result"]
    soup = BeautifulSoup(result_html, 'html.parser')
    
    # 2. استخراج الحديث
    hadith_div = soup.find('div', class_='hadith')
    if not hadith_div:
        raise Exception("لم يتم العثور على نص الحديث")
    hadith_text = hadith_div.get_text(separator=' ', strip=True)
    hadith_text = re.sub(r'^\d+\s*-\s*', '', hadith_text).strip()
    hadith_text = clean_text(hadith_text)
    
    # 3. استخراج معلومات الراوي والمحدث والمصدر والحكم
    info_div = soup.find('div', class_='hadith-info')
    rawi = muhaddith = masdar = page = hukm = ""
    if info_div:
        # استخراج من spans
        spans = info_div.find_all('span', class_='info-subtitle')
        for span in spans:
            label = span.get_text(strip=True)
            value_span = span.find_next('span')
            value = value_span.get_text(strip=True) if value_span else ""
            if 'الراوي' in label:
                rawi = value
            elif 'المحدث' in label:
                muhaddith = value
            elif 'المصدر' in label:
                masdar = value
            elif 'الصفحة' in label:
                page = value
            elif 'خلاصة' in label or 'الحكم' in label:
                hukm = value
    
    # 4. الحصول على رابط صفحة الحديث لجلب الشرح
    sharh_text = ""
    canonical_link = soup.find('link', rel='canonical')
    if canonical_link and canonical_link.get('href'):
        hadith_page_url = canonical_link['href']
        print(f"📖 جاري جلب الشرح من: {hadith_page_url}")
        try:
            page_resp = requests.get(hadith_page_url, timeout=20,
                                     headers={"User-Agent": "Mozilla/5.0"})
            if page_resp.status_code == 200:
                page_soup = BeautifulSoup(page_resp.text, 'html.parser')
                # البحث عن شرح الحديث (قد يكون في div بكلاس sharh أو id sharh)
                sharh_div = (page_soup.find('div', class_='sharh') or
                             page_soup.find('div', id='sharh') or
                             page_soup.find('div', class_='text-justify'))
                if sharh_div:
                    sharh_text = sharh_div.get_text(separator='\n', strip=True)
                    sharh_text = re.sub(r'\n\s*\n', '\n', sharh_text).strip()
                    sharh_text = clean_text(sharh_text)
                else:
                    # محاولة أخيرة: أي فقرة طويلة بعد الحديث
                    content_div = page_soup.find('div', class_='card-body')
                    if content_div:
                        paragraphs = content_div.find_all('p')
                        sharh_text = '\n'.join(p.get_text(strip=True) for p in paragraphs)
                        sharh_text = clean_text(sharh_text)
        except Exception as e:
            print(f"⚠️ لم نتمكن من جلب الشرح: {e}")
    
    return hadith_text, rawi, muhaddith, masdar, page, hukm, sharh_text

# ---------- دوال جلب الفقه والعقيدة (بنفس الأسلوب) ----------
def fetch_fiqh():
    term = random.choice(FIQH_TERMS)
    api_url = f"https://dorar.net/dorar_api.json?skey={term}"
    resp = requests.get(api_url, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    # الفقه قد يكون له شكل مختلف، نستخدم نفس منطق الاستخراج البسيط
    # إذا لم تكن النتائج مناسبة، يمكن الرجوع لاحقاً إلى صفحات الموقع
    ahadith = data.get("ahadith", {})
    if ahadith and "result" in ahadith:
        soup = BeautifulSoup(ahadith["result"], 'html.parser')
        hadith_div = soup.find('div', class_='hadith')
        question = hadith_div.get_text(strip=True) if hadith_div else "مسألة فقهية"
        # قد لا يكون هناك شرح، نتركه فارغاً
        return clean_text(question), ""
    else:
        # الرجوع إلى الموقع مباشرة
        html = requests.get(f"https://dorar.net/feqhia/random", timeout=20,
                            headers={"User-Agent": "Mozilla/5.0"}).text
        soup = BeautifulSoup(html, 'html.parser')
        title = soup.find('h1')
        question = title.get_text(strip=True) if title else "مسألة فقهية"
        answer_div = soup.find('div', class_='answer') or soup.find('div', class_='content')
        answer = answer_div.get_text(strip=True) if answer_div else ""
        return clean_text(question), clean_text(answer)

def fetch_aqeeda():
    term = random.choice(AQEEDA_TERMS)
    api_url = f"https://dorar.net/dorar_api.json?skey={term}"
    resp = requests.get(api_url, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    ahadith = data.get("ahadith", {})
    if ahadith and "result" in ahadith:
        soup = BeautifulSoup(ahadith["result"], 'html.parser')
        hadith_div = soup.find('div', class_='hadith')
        title = hadith_div.get_text(strip=True) if hadith_div else "موضوع في العقيدة"
        return clean_text(title), ""
    else:
        html = requests.get(f"https://dorar.net/aqadia/random", timeout=20,
                            headers={"User-Agent": "Mozilla/5.0"}).text
        soup = BeautifulSoup(html, 'html.parser')
        title = soup.find('h1')
        subject = title.get_text(strip=True) if title else "موضوع في العقيدة"
        content_div = soup.find('div', class_='content')
        content = content_div.get_text(strip=True) if content_div else ""
        return clean_text(subject), clean_text(content)

# ---------- تنسيق الرسائل ----------
def format_hadith_message(hadith_text, rawi, muhaddith, masdar, page, hukm, sharh_text):
    msg = "📜 <b>حديث شريف:</b>\n\n"
    msg += f"قال رسول الله صلى الله عليه وسلم: {html.escape(hadith_text)}\n\n"
    
    # سطر الحكم
    if hukm:
        msg += f"خلاصة حكم المحدث: [{html.escape(hukm)}]\n"
    # سطر الرواة والمصدر
    rawi_parts = []
    if rawi:
        rawi_parts.append(f"الراوي: {html.escape(rawi)}")
    if muhaddith:
        rawi_parts.append(f"المحدث: {html.escape(muhaddith)}")
    if masdar:
        rawi_parts.append(f"المصدر: {html.escape(masdar)}")
    if page:
        rawi_parts.append(f"الصفحة أو الرقم: {html.escape(page)}")
    if rawi_parts:
        msg += " | ".join(rawi_parts) + "\n"
    
    if sharh_text:
        msg += f"\n<b>شرح الحديث:</b>\n{html.escape(sharh_text)}"
    
    return msg

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

# ---------- الرئيسية ----------
def main():
    if len(sys.argv) < 2:
        print("❌ استخدم: python post_topic.py [hadith|fiqh|aqeeda]")
        sys.exit(1)

    topic_type = sys.argv[1].lower()

    try:
        if topic_type == "hadith":
            hadith_text, rawi, muhaddith, masdar, page, hukm, sharh = fetch_hadith()
            msg = format_hadith_message(hadith_text, rawi, muhaddith, masdar, page, hukm, sharh)
        elif topic_type == "fiqh":
            question, answer = fetch_fiqh()
            msg = format_fiqh_message(question, answer)
        elif topic_type == "aqeeda":
            title, content = fetch_aqeeda()
            msg = format_aqeeda_message(title, content)
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
