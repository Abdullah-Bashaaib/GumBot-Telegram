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

# ---------- تنظيف بسيط (يزيل الروابط وإشارات الموقع فقط) ----------
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

def fetch_hadith_data():
    """يطلب API بصيغة JSONP ويعيد حديثاً عشوائياً مع رقمه (إن وجد)"""
    term = random.choice(HADITH_TERMS)
    # نستخدم callback=jsonp للحصول على مصفوفة أحاديث
    api_url = f"https://dorar.net/dorar_api.json?skey={term}&callback=jsonp"
    print(f"🔍 البحث عن: {term}")
    resp = requests.get(api_url, timeout=20)
    resp.raise_for_status()
    # الاستجابة تأتي على شكل: jsonp({...})
    content = resp.text
    # استخراج JSON من داخل jsonp(...)
    json_match = re.search(r'jsonp\((.*)\)\s*$', content, re.DOTALL)
    if not json_match:
        raise Exception("لم نتمكن من استخراج JSON من الاستجابة")
    data = json_match.group(1)
    import json
    data = json.loads(data)
    ahadith = data.get("ahadith", [])
    if not isinstance(ahadith, list) or len(ahadith) == 0:
        raise Exception("لا توجد أحاديث في النتيجة")
    # اختيار حديث عشوائي
    chosen = random.choice(ahadith)
    # نص الحديث كما هو (بترقيمه)
    hadith_text = chosen.get("th", "") or chosen.get("hadith", "")
    if not hadith_text:
        raise Exception("الحديث لا يحتوي على نص")
    # محاولة استخراج رقم الحديث من id أو url
    hadith_id = None
    if "id" in chosen:
        hadith_id = chosen["id"]
    elif "url" in chosen:
        match = re.search(r'/hadith/(\d+)', chosen["url"])
        if match:
            hadith_id = int(match.group(1))
    # إذا لم نجد id، نحاول استخراجه من نص الحديث (مثل "1 - ...")
    if not hadith_id:
        match = re.match(r'^(\d+)\s*-\s*', hadith_text)
        if match:
            hadith_id = int(match.group(1))
    return simple_clean(hadith_text), hadith_id

def fetch_sharh(hadith_id):
    """يجلب شرح الحديث من صفحة sharh إذا عرفنا الرقم"""
    if not hadith_id:
        return ""
    sharh_url = f"https://dorar.net/hadith/sharh/{hadith_id}"
    print(f"📖 جاري جلب الشرح: {sharh_url}")
    try:
        resp = requests.get(sharh_url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            return ""
        soup = BeautifulSoup(resp.text, 'html.parser')
        # نأخذ النص الكامل من القسم الرئيسي (دون ترويسة الموقع)
        main = soup.find('div', class_='container') or soup.find('article')
        if main:
            return simple_clean(main.get_text(separator='\n', strip=True))
        return ""
    except:
        return ""

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
    print("✅ تم إرسال الرسالة بنجاح")

def main():
    if len(sys.argv) < 2:
        print("❌ استخدم: python post_topic.py [hadith|fiqh|aqeeda]")
        sys.exit(1)
    topic = sys.argv[1].lower()
    try:
        if topic == "hadith":
            hadith_text, hadith_id = fetch_hadith_data()
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
