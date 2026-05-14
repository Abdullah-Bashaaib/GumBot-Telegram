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
    "الجنة", "النار", "الذكر", "الدعاء", "الاستغفار", "التوبة"
]

# ---------- استخراج البيانات من صفحة الحديث العشوائية ----------
def get_random_hadith_link():
    """يبحث بكلمة عشوائية ويعيد رابط أول نتيجة"""
    term = random.choice(HADITH_TERMS)
    api_url = f"https://dorar.net/dorar_api.json?skey={term}"
    print(f"🔍 جاري البحث عن: {term}")
    resp = requests.get(api_url, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    ahadith = data.get("ahadith", {})
    if not ahadith or "result" not in ahadith:
        raise Exception("لم يتم العثور على نتائج")
    soup = BeautifulSoup(ahadith["result"], 'html.parser')
    canonical_link = soup.find('link', rel='canonical')
    if canonical_link and canonical_link.get('href'):
        return canonical_link['href']
    # إذا لم نجد رابطاً نأخذ أول حديث ونحاول استخراج رقم
    hadith_div = soup.find('div', class_='hadith')
    if hadith_div:
        onclick = hadith_div.get('onclick', '')
        match = re.search(r'/hadith/(\d+)', onclick)
        if match:
            return f"https://dorar.net/hadith/{match.group(1)}"
    raise Exception("لم نتمكن من العثور على رابط الحديث")

def extract_sharh_page(hadith_page_url):
    """يحول رابط الحديث إلى رابط الشرح ويجلب المحتوى"""
    # استخراج الرقم من رابط الحديث
    match = re.search(r'/hadith/(\d+)', hadith_page_url)
    if not match:
        raise Exception("رابط الحديث لا يحتوي على رقم")
    hadith_id = match.group(1)
    sharh_url = f"https://dorar.net/hadith/sharh/{hadith_id}"
    print(f"📖 جاري جلب الشرح من: {sharh_url}")
    resp = requests.get(sharh_url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    return resp.text

def parse_hadith_data(html_content):
    """يستخرج الحديث والمعلومات والشرح من صفحة الشرح"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # الحديث النبوي (غالباً في div بكلاس hadith-text أو داخل article)
    hadith_div = soup.find('div', class_='hadith-text') or soup.find('div', class_='hadith')
    if not hadith_div:
        # محاولة أخيرة: النص الطويل الأول
        hadith_div = soup.find('div', class_='text-justify')
    if not hadith_div:
        raise Exception("لم يتم العثور على نص الحديث")
    hadith_text = hadith_div.get_text(separator=' ', strip=True)
    hadith_text = re.sub(r'^\d+\s*-\s*', '', hadith_text).strip()
    hadith_text = clean_text(hadith_text)
    
    # استخراج خلاصة الحكم والراوي والمحدث (من الجدول أو div info)
    hukm = rawi = muhaddith = masdar = page = ""
    # البحث في عناصر تحمل هذه البيانات
    info_div = soup.find('div', class_='hadith-info')
    if info_div:
        spans = info_div.find_all('span')
        for span in spans:
            text = span.get_text(strip=True)
            if 'خلاصة' in text:
                hukm = span.find_next('span').get_text(strip=True) if span.find_next('span') else ""
            elif 'الراوي' in text:
                rawi = span.find_next('span').get_text(strip=True) if span.find_next('span') else ""
            elif 'المحدث' in text:
                muhaddith = span.find_next('span').get_text(strip=True) if span.find_next('span') else ""
            elif 'المصدر' in text:
                masdar = span.find_next('span').get_text(strip=True) if span.find_next('span') else ""
            elif 'الصفحة' in text:
                page = span.find_next('span').get_text(strip=True) if span.find_next('span') else ""
    
    # الشرح: عادة بعد الحديث مباشرة، في div يلي الحديث أو بكلاس sharh
    sharh_div = soup.find('div', class_='sharh') or soup.find('div', id='sharh')
    if not sharh_div:
        # ربما الشرح هو الفقرات التالية للحديث
        sharh_div = soup.find('div', class_='content')
    sharh_text = ""
    if sharh_div:
        sharh_text = sharh_div.get_text(separator='\n', strip=True)
        sharh_text = clean_text(sharh_text)
    
    return hadith_text, hukm, rawi, muhaddith, masdar, page, sharh_text

# ---------- باقي الدوال (التنسيق والإرسال) ----------
def format_hadith_message(hadith_text, hukm, rawi, muhaddith, masdar, page, sharh_text):
    msg = "📜 <b>حديث شريف:</b>\n\n"
    msg += f"قال رسول الله صلى الله عليه وسلم: {html.escape(hadith_text)}\n\n"
    if hukm:
        msg += f"خلاصة حكم المحدث: [{html.escape(hukm)}]\n"
    info_parts = []
    if rawi:
        info_parts.append(f"الراوي: {html.escape(rawi)}")
    if muhaddith:
        info_parts.append(f"المحدث: {html.escape(muhaddith)}")
    if masdar:
        info_parts.append(f"المصدر: {html.escape(masdar)}")
    if page:
        info_parts.append(f"الصفحة أو الرقم: {html.escape(page)}")
    if info_parts:
        msg += " | ".join(info_parts) + "\n"
    if sharh_text:
        msg += f"\n<b>شرح الحديث:</b>\n{html.escape(sharh_text)}"
    return msg

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

def main():
    if len(sys.argv) < 2:
        print("❌ استخدم: python post_topic.py [hadith|fiqh|aqeeda]")
        sys.exit(1)
    topic_type = sys.argv[1].lower()
    try:
        if topic_type == "hadith":
            # 1. الحصول على رابط حديث عشوائي
            hadith_link = get_random_hadith_link()
            # 2. تحويله لصفحة الشرح وجلبها
            sharh_html = extract_sharh_page(hadith_link)
            # 3. تحليل البيانات
            hadith_text, hukm, rawi, muhaddith, masdar, page, sharh = parse_hadith_data(sharh_html)
            msg = format_hadith_message(hadith_text, hukm, rawi, muhaddith, masdar, page, sharh)
        else:
            # الفقه والعقيدة نستخدم طريقة مبسطة مؤقتاً
            print("⚠️ الفقه والعقيدة قيد التطوير بنفس الطريقة")
            sys.exit(0)
        print("\n" + "="*40)
        print(msg)
        print("="*40 + "\n")
        send_message(msg)
    except Exception as e:
        print(f"❌ خطأ: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
