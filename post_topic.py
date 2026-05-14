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

# ---------- أدوات تنظيف بسيطة (فقط الروابط والمصادر) ----------
def simple_clean(text):
    if not text:
        return ""
    # إزالة الروابط
    text = re.sub(r'https?://\S+', '', text)
    # إزالة إشارات الموقع
    text = re.sub(r'الدرر السنية', '', text, flags=re.IGNORECASE)
    text = re.sub(r'dorar\.net', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^(?:المصدر|الرابط|مصدر|رابط)\s*:?\s*.*$', '', text, flags=re.MULTILINE | re.IGNORECASE)
    # نحافظ على التنسيق الأصلي
    text = re.sub(r'\n\s*\n', '\n', text)
    text = re.sub(r' +', ' ', text).strip()
    return text

# ---------- كلمات البحث ----------
HADITH_TERMS = [
    "الصلاة", "الصيام", "الزكاة", "الحج", "الإيمان", "الإحسان",
    "بر الوالدين", "صلة الرحم", "الصدق", "الأمانة", "التقوى",
    "الجنة", "النار", "الذكر", "الدعاء", "الاستغفار", "التوبة"
]

# ---------- دوال جلب الحديث ----------
def fetch_hadith_from_api():
    term = random.choice(HADITH_TERMS)
    api_url = f"https://dorar.net/dorar_api.json?skey={term}"
    print(f"🔍 جاري البحث عن: {term}")
    resp = requests.get(api_url, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    ahadith = data.get("ahadith", {})
    if not ahadith or "result" not in ahadith:
        raise Exception("لم يتم العثور على نتائج")
    return ahadith["result"]

def extract_hadith_and_link(html_snippet):
    soup = BeautifulSoup(html_snippet, 'html.parser')
    # الحديث: أول div بكلاس hadith
    hadith_div = soup.find('div', class_='hadith')
    if not hadith_div:
        raise Exception("لم يتم العثور على نص الحديث")
    # أخذ الحديث كما هو مع ترقيمه
    hadith_text = hadith_div.get_text(separator=' ', strip=True)
    hadith_text = simple_clean(hadith_text)
    
    # استخراج رابط الصفحة (canonical)
    canonical_link = soup.find('link', rel='canonical')
    if canonical_link and canonical_link.get('href'):
        hadith_page = canonical_link['href']
        print(f"🔗 رابط الحديث: {hadith_page}")
        return hadith_text, hadith_page
    
    # إذا لم نجد، نحاول استخراج الرقم من onclick
    onclick = hadith_div.get('onclick', '')
    match = re.search(r'/hadith/(\d+)', onclick)
    if match:
        hadith_page = f"https://dorar.net/hadith/{match.group(1)}"
        return hadith_text, hadith_page
    
    # لا يوجد رابط
    return hadith_text, None

def fetch_sharh(hadith_page_url):
    """تحويل رابط الحديث إلى رابط شرح وجلب الشرح"""
    if not hadith_page_url:
        return ""
    match = re.search(r'/hadith/(\d+)', hadith_page_url)
    if not match:
        print("⚠️ لا يمكن استخراج رقم الحديث من الرابط")
        return ""
    sharh_url = f"https://dorar.net/hadith/sharh/{match.group(1)}"
    print(f"📖 جاري جلب الشرح من: {sharh_url}")
    try:
        resp = requests.get(sharh_url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            return ""
        soup = BeautifulSoup(resp.text, 'html.parser')
        # الشرح يكون عادة في div بكلاس content أو article
        sharh_div = soup.find('div', class_='content') or soup.find('article')
        if not sharh_div:
            # ربما الفقرات بعد معلومات الحديث
            info = soup.find('div', class_='hadith-info')
            if info:
                next_div = info.find_next_sibling()
                if next_div:
                    sharh_div = next_div
        if sharh_div:
            sharh_text = sharh_div.get_text(separator='\n', strip=True)
            return simple_clean(sharh_text)
    except Exception as e:
        print(f"⚠️ خطأ أثناء جلب الشرح: {e}")
    return ""

# ---------- التنسيق ----------
def format_hadith_message(hadith_text, sharh_text):
    msg = "📜 <b>حديث شريف:</b>\n\n"
    msg += f"قال رسول الله صلى الله عليه وسلم: {html.escape(hadith_text)}\n"
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

# ---------- الرئيسية ----------
def main():
    if len(sys.argv) < 2:
        print("❌ استخدم: python post_topic.py [hadith|fiqh|aqeeda]")
        sys.exit(1)
    topic_type = sys.argv[1].lower()
    try:
        if topic_type == "hadith":
            html_snippet = fetch_hadith_from_api()
            hadith_text, hadith_page = extract_hadith_and_link(html_snippet)
            sharh = fetch_sharh(hadith_page) if hadith_page else ""
            msg = format_hadith_message(hadith_text, sharh)
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
