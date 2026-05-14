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

# ---------- تنظيف بسيط (يحافظ على الترقيم) ----------
def simple_clean(text):
    if not text:
        return ""
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'الدرر السنية', '', text, flags=re.IGNORECASE)
    text = re.sub(r'dorar\.net', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^(?:المصدر|الرابط|مصدر|رابط)\s*:?\s*.*$', '', text, flags=re.MULTILINE | re.IGNORECASE)
    return text.strip()

# ---------- كلمات البحث ----------
HADITH_TERMS = [
    "الصلاة", "الصيام", "الزكاة", "الحج", "الإيمان", "الإحسان",
    "بر الوالدين", "صلة الرحم", "الصدق", "الأمانة", "التقوى",
    "الجنة", "النار", "الذكر", "الدعاء", "الاستغفار", "التوبة"
]

# ---------- دوال جلب الحديث ----------
def fetch_hadith_from_api(keyword):
    """يبحث بكلمة ويعيد HTML النتيجة إن وجدت"""
    api_url = f"https://dorar.net/dorar_api.json?skey={keyword}"
    print(f"🔍 تجربة البحث عن: {keyword}")
    resp = requests.get(api_url, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    ahadith = data.get("ahadith", {})
    if not ahadith or "result" not in ahadith:
        return None
    return ahadith["result"]

def extract_hadith_and_id(html_snippet):
    """يستخرج نص الحديث (كما هو) ورقم الحديث من HTML"""
    soup = BeautifulSoup(html_snippet, 'html.parser')
    hadith_div = soup.find('div', class_='hadith')
    if not hadith_div:
        return None, None
    # الحديث كما يظهر بالموقع (بالترقيم)
    hadith_text = hadith_div.get_text(separator=' ', strip=True)
    hadith_text = simple_clean(hadith_text)
    
    # محاولة استخراج رقم الحديث
    hadith_id = None
    # 1. من الرابط القانوني
    link = soup.find('link', rel='canonical')
    if link and link.get('href'):
        match = re.search(r'/hadith/(\d+)', link['href'])
        if match:
            hadith_id = int(match.group(1))
    # 2. من onclick
    if not hadith_id:
        onclick = hadith_div.get('onclick', '')
        match = re.search(r'/hadith/(\d+)', onclick)
        if match:
            hadith_id = int(match.group(1))
    # 3. من بداية النص (مثلاً "1 - ...")
    if not hadith_id:
        match = re.match(r'^(\d+)\s*-\s*', hadith_text)
        if match:
            hadith_id = int(match.group(1))
    return hadith_text, hadith_id

def get_random_hadith():
    """يجرب كلمات عشوائية حتى ينجح في جلب حديث برقم"""
    random.shuffle(HADITH_TERMS)  # ترتيب عشوائي
    for term in HADITH_TERMS:
        html = fetch_hadith_from_api(term)
        if not html:
            continue
        hadith_text, hadith_id = extract_hadith_and_id(html)
        if hadith_text and hadith_id:
            return hadith_text, hadith_id
    raise Exception("لم نعثر على حديث مع رقم بعد تجربة كل الكلمات")

def fetch_sharh(hadith_id):
    """يجلب شرح الحديث من صفحة sharh"""
    if not hadith_id:
        return ""
    sharh_url = f"https://dorar.net/hadith/sharh/{hadith_id}"
    print(f"📖 جلب الشرح: {sharh_url}")
    try:
        resp = requests.get(sharh_url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            return ""
        soup = BeautifulSoup(resp.text, 'html.parser')
        main = soup.find('div', class_='container') or soup.find('article')
        if main:
            return simple_clean(main.get_text(separator='\n', strip=True))
        return ""
    except:
        return ""

# ---------- تنسيق وإرسال ----------
def format_message(hadith_text, sharh):
    msg = "📜 <b>حديث شريف:</b>\n\n"
    msg += f"قال رسول الله صلى الله عليه وسلم: {html.escape(hadith_text)}\n"
    if sharh:
        msg += f"\n<b>شرح الحديث:</b>\n{html.escape(sharh)}"
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
    print("✅ تم الإرسال بنجاح")

# ---------- الرئيسية ----------
def main():
    if len(sys.argv) < 2:
        print("❌ استخدم: python post_topic.py [hadith|fiqh|aqeeda]")
        sys.exit(1)
    topic = sys.argv[1].lower()
    try:
        if topic == "hadith":
            hadith_text, hadith_id = get_random_hadith()
            sharh = fetch_sharh(hadith_id)
            msg = format_message(hadith_text, sharh)
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
