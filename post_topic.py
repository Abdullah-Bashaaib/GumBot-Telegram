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

# ---------- جلب شرح حديث برقم معين ----------
def fetch_sharh_by_id(hadith_id):
    url = f"https://dorar.net/hadith/sharh/{hadith_id}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, timeout=15, headers=headers)
        if resp.status_code == 200 and "الموسوعة الحديثية" in resp.text:
            return resp.text
        else:
            return None
    except:
        return None

def extract_data_from_sharh(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # الحديث الشريف
    hadith_div = soup.find('div', class_='hadith-text') or soup.find('div', class_='hadith')
    if not hadith_div:
        hadith_div = soup.find('div', class_='text-justify')
    if not hadith_div:
        raise Exception("لم يتم العثور على نص الحديث")
    hadith_text = hadith_div.get_text(separator=' ', strip=True)
    hadith_text = re.sub(r'^\d+\s*-\s*', '', hadith_text).strip()
    hadith_text = clean_text(hadith_text)
    
    # استخراج المعلومات (الحكم، الراوي، المحدث، المصدر، الصفحة)
    hukm = rawi = muhaddith = masdar = page = ""
    info_div = soup.find('div', class_='hadith-info')
    if info_div:
        # التعامل مع النموذج الذي رأيناه في صفحة 14372
        spans = info_div.find_all('span', class_='info-subtitle')
        for span in spans:
            label = span.get_text(strip=True)
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
    
    # الشرح: النص الطويل بعد الحديث (غالباً الفقرات بعد المعلومات)
    sharh_text = ""
    # قد يكون الشرح في div يلي info_div مباشرة، أو في article
    content_div = soup.find('div', class_='content') or soup.find('article')
    if content_div:
        paragraphs = content_div.find_all('p')
        sharh_text = '\n'.join(p.get_text(strip=True) for p in paragraphs)
    else:
        # محاولة أخيرة: النص بعد info_div
        if info_div:
            next_sibling = info_div.find_next_sibling()
            if next_sibling:
                sharh_text = next_sibling.get_text(separator='\n', strip=True)
    sharh_text = clean_text(sharh_text)
    
    return hadith_text, hukm, rawi, muhaddith, masdar, page, sharh_text

def get_random_hadith():
    """يحاول العثور على حديث عشوائي بتجربة أرقام عشوائية"""
    # نطاق شائع للأحاديث في الموسوعة (يمكن توسيعه)
    tried = set()
    max_attempts = 20
    for _ in range(max_attempts):
        # أرقام شائعة بين 1 و 20000
        rid = random.randint(1, 20000)
        if rid in tried:
            continue
        tried.add(rid)
        print(f"🔄 تجربة الرقم: {rid}")
        html = fetch_sharh_by_id(rid)
        if html:
            print(f"✅ وجدنا شرحاً للحديث رقم: {rid}")
            return html
    raise Exception("لم نعثر على شرح حديث بعد عدة محاولات")

# ---------- التنسيق والإرسال ----------
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
            sharh_html = get_random_hadith()
            hadith_text, hukm, rawi, muhaddith, masdar, page, sharh = extract_data_from_sharh(sharh_html)
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
