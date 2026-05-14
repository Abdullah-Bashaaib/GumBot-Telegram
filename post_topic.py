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
    """ينظف النص من الروابط وإشارات الموقع فقط"""
    if not text:
        return ""
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'الدرر السنية', '', text, flags=re.IGNORECASE)
    text = re.sub(r'dorar\.net', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^(?:المصدر|الرابط|مصدر|رابط)\s*:?\s*.*$', '', text, flags=re.MULTILINE | re.IGNORECASE)
    return text.strip()

def clean_whitespace(text):
    """يدمج المسافات والأسطر المتعددة"""
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# ---------- كلمات البحث ----------
HADITH_TERMS = [
    "الصلاة", "الصيام", "الزكاة", "الحج", "الإيمان", "الإحسان",
    "بر الوالدين", "صلة الرحم", "الصدق", "الأمانة", "التقوى",
    "الجنة", "النار", "الذكر", "الدعاء", "الاستغفار", "التوبة"
]

# ---------- الحصول على رقم حديث عشوائي ----------
def get_random_hadith_id():
    """يبحث بكلمة عشوائية ويعيد رقم حديث صحيح"""
    random.shuffle(HADITH_TERMS)
    for term in HADITH_TERMS:
        print(f"🔍 تجربة البحث عن: {term}")
        try:
            resp = requests.get(f"https://dorar.net/dorar_api.json?skey={term}", timeout=20)
            resp.raise_for_status()
            data = resp.json()
            ahadith = data.get("ahadith", {})
            if not ahadith or "result" not in ahadith:
                continue
            soup = BeautifulSoup(ahadith["result"], 'html.parser')
            # استخراج رقم الحديث من الرابط القانوني أو onclick
            link = soup.find('link', rel='canonical')
            if link and link.get('href'):
                match = re.search(r'/hadith/(\d+)', link['href'])
                if match:
                    return int(match.group(1))
            hadith_div = soup.find('div', class_='hadith')
            if hadith_div:
                onclick = hadith_div.get('onclick', '')
                match = re.search(r'/hadith/(\d+)', onclick)
                if match:
                    return int(match.group(1))
        except:
            continue
    raise Exception("لم نعثر على حديث مناسب")

# ---------- استخراج البيانات من صفحة الشرح ----------
def fetch_and_parse_sharh(hadith_id):
    """يجلب صفحة شرح الحديث ويعيد جميع البيانات"""
    sharh_url = f"https://dorar.net/hadith/sharh/{hadith_id}"
    print(f"📖 جلب صفحة الشرح: {sharh_url}")
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(sharh_url, timeout=20, headers=headers)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')

    # 1. الحديث (عادة في div بكلاس hadith-text أو hadith)
    hadith_div = soup.find('div', class_='hadith-text') or soup.find('div', class_='hadith')
    if not hadith_div:
        hadith_div = soup.find('div', class_='text-justify')
    if not hadith_div:
        raise Exception("لم يتم العثور على نص الحديث في صفحة الشرح")
    hadith_text = ' '.join(hadith_div.stripped_strings)
    hadith_text = clean_whitespace(hadith_text)
    # إزالة الترقيم الأولي إذا وجد (مثلاً "1 - ")
    hadith_text = re.sub(r'^\d+\s*[-–]\s*', '', hadith_text).strip()
    hadith_text = clean_text(hadith_text)

    # 2. المعلومات (خلاصة الحكم، الراوي، المحدث، المصدر، الصفحة)
    hukm = rawi = muhaddith = masdar = page = ""
    info_div = soup.find('div', class_='hadith-info')
    if info_div:
        # نبحث عن spans تحمل info-subtitle
        spans = info_div.find_all('span', class_='info-subtitle')
        for span in spans:
            label = span.get_text(strip=True)
            # القيمة تكون في span التالي مباشرة
            value_span = span.find_next('span')
            value = value_span.get_text(strip=True) if value_span else ""
            if 'خلاصة' in label:
                hukm = value
            elif 'الراوي' in label:
                rawi = value
            elif 'المحدث' in label:
                muhaddith = value
            elif 'المصدر' in label:
                masdar = value
            elif 'الصفحة' in label:
                page = value
    # إن لم نجد، نجرب استخراجها من النص العادي
    if not hukm:
        match = re.search(r'خلاصة حكم المحدث\s*:\s*\[?([^\]]+)\]?', soup.get_text())
        if match:
            hukm = match.group(1).strip()
    if not rawi:
        match = re.search(r'الراوي\s*:\s*([^|]+)', soup.get_text())
        if match:
            rawi = match.group(1).strip()
    if not muhaddith:
        match = re.search(r'المحدث\s*:\s*([^|]+)', soup.get_text())
        if match:
            muhaddith = match.group(1).strip()
    if not masdar:
        match = re.search(r'المصدر\s*:\s*([^|]+)', soup.get_text())
        if match:
            masdar = match.group(1).strip()
    if not page:
        match = re.search(r'الصفحة أو الرقم\s*:\s*([^|]+)', soup.get_text())
        if match:
            page = match.group(1).strip()

    # 3. الشرح (النص الطويل بعد المعلومات، عادة في div يلي info_div أو في article)
    sharh_text = ""
    # نبحث عن المحتوى الأكبر بعد الحديث والمعلومات
    main_content = soup.find('div', class_='content') or soup.find('article')
    if main_content:
        # نزيل الحديث والمعلومات من النص المستخرج إن أمكن
        # طريقة بسيطة: نأخذ كل النصوص بعد info_div
        if info_div:
            # كل العناصر بعد info_div
            elements = info_div.find_all_next(string=True)
            sharh_text = '\n'.join(e.strip() for e in elements if e.strip())
        else:
            sharh_text = '\n'.join(main_content.stripped_strings)
    else:
        # محاولة أخيرة
        sharh_text = '\n'.join(soup.stripped_strings)
    sharh_text = clean_text(sharh_text)
    # قد يكون الشرح طويلاً جداً، نأخذ أول 1500 حرف مثلاً للقناة (اختياري)
    # لكن سنتركه كاملاً
    return hadith_text, hukm, rawi, muhaddith, masdar, page, sharh_text

# ---------- تنسيق الرسالة ----------
def format_hadith_message(hadith_text, hukm, rawi, muhaddith, masdar, page, sharh):
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
    if sharh:
        # نأخذ جزءاً معقولاً من الشرح (مثلاً 2000 حرف) حتى لا يصبح طويلاً جداً
        short_sharh = sharh[:2000]
        if len(sharh) > 2000:
            short_sharh += " ..."
        msg += f"\n<b>شرح الحديث:</b>\n{html.escape(short_sharh)}"
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

# ---------- الرئيسية ----------
def main():
    if len(sys.argv) < 2:
        print("❌ استخدم: python post_topic.py [hadith|fiqh|aqeeda]")
        sys.exit(1)
    topic = sys.argv[1].lower()
    try:
        if topic == "hadith":
            hadith_id = get_random_hadith_id()
            print(f"🆔 رقم الحديث: {hadith_id}")
            hadith_text, hukm, rawi, muhaddith, masdar, page, sharh = fetch_and_parse_sharh(hadith_id)
            msg = format_hadith_message(hadith_text, hukm, rawi, muhaddith, masdar, page, sharh)
        else:
            print("⚠️ الفقه والعقيدة قيد التطوير")
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
