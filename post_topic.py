import os
import sys
import re
import html
import requests
from bs4 import BeautifulSoup

# ---------- الإعدادات ----------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

if not BOT_TOKEN or not CHANNEL_ID:
    print("❌ يجب تعيين BOT_TOKEN و CHANNEL_ID")
    sys.exit(1)

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ---------- دوال مساعدة ----------
def clean_text(text):
    """تنظيف النص من الروابط وبقايا HTML"""
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

def get_random_page(url):
    """جلب صفحة عشوائية واتباع التوجيهات"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=20, allow_redirects=True)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        raise Exception(f"فشل تحميل الصفحة: {e}")

# ---------- استخراج الحديث ----------
def extract_hadith_data(html_content):
    """استخراج الحديث والمعلومات والشرح من صفحة حديث"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # الحديث: غالباً داخل عنصر بكلاس 'hadith' أو 'hadith-text'
    hadith_div = soup.find('div', class_='hadith') or soup.find('div', class_='hadith-text')
    if not hadith_div:
        # محاولة بديلة
        hadith_div = soup.find('div', class_='text-center')  # بعض الصفحات
    if not hadith_div:
        raise Exception("لم يتم العثور على نص الحديث")
    
    hadith_text = hadith_div.get_text(separator=' ', strip=True)
    hadith_text = re.sub(r'^\d+\s*-\s*', '', hadith_text).strip()  # إزالة الترقيم
    hadith_text = clean_text(hadith_text)
    
    # معلومات الراوي والمحدث
    info_div = soup.find('div', class_='hadith-info')
    info_text = ""
    if info_div:
        info_text = info_div.get_text(separator=' ', strip=True)
    else:
        # محاولة من جداول أخرى
        rows = soup.select('table tr')
        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 2:
                key = cells[0].get_text(strip=True)
                value = cells[1].get_text(strip=True)
                if key in ['الراوي', 'المحدث', 'المصدر', 'الصفحة أو الرقم', 'خلاصة الحكم']:
                    info_text += f"{key}: {value} | "
        info_text = info_text.rstrip(' | ')
    info_text = clean_text(info_text)
    
    # استخراج الحكم والراوي والمحدث بشكل منفصل لتنسيق أفضل
    rawi = ""
    muhaddith = ""
    masdar = ""
    page = ""
    hukm = ""
    
    # محاولة استخراج كل معلومة على حدة
    if info_div:
        for span in info_div.find_all('span'):
            label = span.get('class', '')
            if 'info-subtitle' in span.get('class', []):
                label_text = span.get_text(strip=True)
                next_span = span.find_next('span')
                value = next_span.get_text(strip=True) if next_span else ""
                if 'الراوي' in label_text:
                    rawi = value
                elif 'المحدث' in label_text:
                    muhaddith = value
                elif 'المصدر' in label_text:
                    masdar = value
                elif 'الصفحة' in label_text:
                    page = value
                elif 'خلاصة' in label_text:
                    hukm = value
    
    # إذا لم نستطع استخراجها، نحاول من النص الكامل
    if not rawi and info_text:
        match = re.search(r'الراوي:\s*([^|]+)', info_text)
        if match: rawi = match.group(1).strip()
        match = re.search(r'المحدث:\s*([^|]+)', info_text)
        if match: muhaddith = match.group(1).strip()
        match = re.search(r'المصدر:\s*([^|]+)', info_text)
        if match: masdar = match.group(1).strip()
        match = re.search(r'الصفحة أو الرقم:\s*([^|]+)', info_text)
        if match: page = match.group(1).strip()
        match = re.search(r'خلاصة الحكم:\s*([^|]+)', info_text)
        if match: hukm = match.group(1).strip()
    
    # الشرح
    sharh_div = soup.find('div', class_='sharh') or soup.find('div', id='sharh')
    if not sharh_div:
        # قد يكون في قسم منفصل
        sharh_div = soup.find('div', class_='card-body') or soup.find('div', class_='content')
    sharh_text = ""
    if sharh_div:
        sharh_text = sharh_div.get_text(separator='\n', strip=True)
        # تنظيف إضافي
        sharh_text = re.sub(r'\n\s*\n', '\n', sharh_text).strip()
    sharh_text = clean_text(sharh_text)
    
    return hadith_text, rawi, muhaddith, masdar, page, hukm, sharh_text

# ---------- تنسيق الرسالة كما طلب المستخدم ----------
def format_hadith_message(hadith_text, rawi, muhaddith, masdar, page, hukm, sharh_text):
    msg = "📜 <b>حديث شريف:</b>\n\n"
    msg += f"قال رسول الله صلى الله عليه وسلم: {html.escape(hadith_text)}\n\n"
    
    # سطر المعلومات
    info_parts = []
    if hukm:
        info_parts.append(f"خلاصة حكم المحدث: [{html.escape(hukm)}]")
    rawi_line = []
    if rawi:
        rawi_line.append(f"الراوي: {html.escape(rawi)}")
    if muhaddith:
        rawi_line.append(f"المحدث: {html.escape(muhaddith)}")
    if masdar:
        rawi_line.append(f"المصدر: {html.escape(masdar)}")
    if page:
        rawi_line.append(f"الصفحة أو الرقم: {html.escape(page)}")
    if rawi_line:
        info_parts.append(" | ".join(rawi_line))
    if info_parts:
        msg += "\n".join(info_parts) + "\n"
    
    if sharh_text:
        msg += f"\n<b>شرح الحديث:</b>\n{html.escape(sharh_text)}"
    
    return msg

# ---------- دوال جلب المحتوى حسب النوع ----------
def fetch_hadith():
    html = get_random_page("https://dorar.net/hadith/random")
    return extract_hadith_data(html)

def fetch_fiqh():
    # بالنسبة للفقه والعقيدة، سنبقي على الطريقة القديمة أو نخصص صفحات مماثلة
    # يمكن لاحقاً توسيعها
    html = get_random_page("https://dorar.net/feqhia/random")
    # استخراج بسيط للمسألة (يعتمد على هيكل الموقع)
    soup = BeautifulSoup(html, 'html.parser')
    title = soup.find('h1')
    question = title.get_text(strip=True) if title else "مسألة فقهية"
    answer_div = soup.find('div', class_='content') or soup.find('div', class_='answer')
    answer = answer_div.get_text(separator='\n', strip=True) if answer_div else ""
    return clean_text(question), clean_text(answer)

def fetch_aqeeda():
    html = get_random_page("https://dorar.net/aqadia/random")
    soup = BeautifulSoup(html, 'html.parser')
    title = soup.find('h1')
    subject = title.get_text(strip=True) if title else "موضوع في العقيدة"
    content_div = soup.find('div', class_='content') or soup.find('div', class_='article')
    content = content_div.get_text(separator='\n', strip=True) if content_div else ""
    return clean_text(subject), clean_text(content)

# ---------- تنسيق باقي الأنواع ----------
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
