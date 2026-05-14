import os
import sys
import re
import html
import json
import random
import requests
from bs4 import BeautifulSoup

# ---------- الإعدادات ----------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

if not BOT_TOKEN or not CHANNEL_ID:
    print("❌ يجب تعيين BOT_TOKEN و CHANNEL_ID")
    sys.exit(1)

# ---------- كلمات البحث ----------
HADITH_TERMS = [
    "الصلاة", "الصيام", "الزكاة", "الحج", "الإيمان", "الإحسان",
    "بر الوالدين", "صلة الرحم", "الصدق", "الأمانة", "التقوى",
    "الجنة", "النار", "الذكر", "الدعاء", "الاستغفار", "التوبة"
]

FIQH_TERMS = [
    "حكم الصلاة", "حكم الصيام", "الطهارة", "الوضوء", "الزكاة",
    "الحج", "النكاح", "الطلاق", "البيع", "الميراث"
]

# ---------- تنظيف النص ----------
def clean_text(text):
    if not text:
        return ""
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'الدرر السنية', '', text, flags=re.IGNORECASE)
    text = re.sub(r'dorar\.net', '', text, flags=re.IGNORECASE)
    return text.strip()

# ---------- 1. جلب رقم حديث عشوائي من API بصيغة JSONP ----------
def get_random_hadith_id():
    """يستخدم JSONP للحصول على أحاديث ويعيد id لأحدها"""
    random.shuffle(HADITH_TERMS)
    for term in HADITH_TERMS:
        print(f"🔍 تجربة كلمة: {term}")
        try:
            url = f"https://dorar.net/dorar_api.json?skey={term}&callback=jsonp"
            resp = requests.get(url, timeout=20)
            content = resp.text

            # استخراج JSON من داخل jsonp(...)
            match = re.search(r'jsonp\((.*)\)\s*$', content, re.DOTALL)
            if not match:
                continue
            data = json.loads(match.group(1))
            ahadith = data.get("ahadith", [])
            if not isinstance(ahadith, list) or len(ahadith) == 0:
                continue

            chosen = random.choice(ahadith)
            # محاولة استخراج الرقم من id أو url أو من بداية النص
            if "id" in chosen:
                return int(chosen["id"])
            if "url" in chosen:
                m = re.search(r'/hadith/(\d+)', chosen["url"])
                if m:
                    return int(m.group(1))
            # من الترقيم في نص الحديث (مثلاً "1 - ...")
            if "th" in chosen:
                m = re.match(r'^(\d+)\s*-\s*', chosen["th"])
                if m:
                    return int(m.group(1))
            if "hadith" in chosen:
                m = re.match(r'^(\d+)\s*-\s*', chosen["hadith"])
                if m:
                    return int(m.group(1))
        except Exception as e:
            print(f"   فشل: {e}")
            continue
    raise Exception("لم نعثر على أي حديث مناسب بعد تجربة كل الكلمات")

# ---------- 2. جلب بيانات الحديث من صفحة الشرح ----------
def fetch_hadith_details(hadith_id):
    url = f"https://dorar.net/hadith/sharh/{hadith_id}"
    print(f"📖 جلب شرح الحديث: {url}")
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, timeout=20, headers=headers)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')

    # الحديث
    hadith_div = soup.find('div', class_='hadith-text') or soup.find('div', class_='hadith')
    if not hadith_div:
        hadith_div = soup.find('div', class_='text-justify')
    if not hadith_div:
        raise Exception("لم يتم العثور على نص الحديث")
    hadith_text = ' '.join(hadith_div.stripped_strings)
    hadith_text = clean_text(hadith_text)

    # المعلومات
    rawi = mohdith = book = page = grade = ""
    info_div = soup.find('div', class_='hadith-info')
    if info_div:
        labels = info_div.find_all('span', class_='info-subtitle')
        for label in labels:
            label_text = label.get_text(strip=True)
            value_span = label.find_next('span')
            value = value_span.get_text(strip=True) if value_span else ""
            if 'الراوي' in label_text:
                rawi = value
            elif 'المحدث' in label_text:
                mohdith = value
            elif 'المصدر' in label_text:
                book = value
            elif 'الصفحة' in label_text:
                page = value
            elif 'خلاصة' in label_text or 'الحكم' in label_text:
                grade = value

    # الشرح
    sharh_text = ""
    main = soup.find('div', class_='content') or soup.find('article')
    if main:
        full_text = main.get_text(separator='\n', strip=True)
        lines = full_text.splitlines()
        start = 0
        for i, line in enumerate(lines):
            if len(line) > 50 and 'الراوي' not in line and 'خلاصة' not in line and 'المحدث' not in line:
                start = i
                break
        sharh_text = '\n'.join(lines[start:]).strip()
    sharh_text = clean_text(sharh_text)

    return hadith_text, grade, rawi, mohdith, book, page, sharh_text

# ---------- 3. تنسيق الرسالة ----------
def format_hadith_message(hadith_text, grade, rawi, mohdith, book, page, sharh):
    msg = "📜 <b>حديث شريف:</b>\n\n"
    msg += f"قال رسول الله صلى الله عليه وسلم: {html.escape(hadith_text)}\n\n"
    if grade:
        msg += f"خلاصة حكم المحدث: [{html.escape(grade)}]\n"
    info = []
    if rawi:
        info.append(f"الراوي: {html.escape(rawi)}")
    if mohdith:
        info.append(f"المحدث: {html.escape(mohdith)}")
    if book:
        info.append(f"المصدر: {html.escape(book)}")
    if page:
        info.append(f"الصفحة أو الرقم: {html.escape(page)}")
    if info:
        msg += " | ".join(info) + "\n"
    if sharh:
        short_sharh = sharh[:2000]
        if len(sharh) > 2000:
            short_sharh += " ..."
        msg += f"\n<b>شرح الحديث:</b>\n{html.escape(short_sharh)}"
    return msg

# ---------- 4. جلب مسألة فقهية ----------
def fetch_fiqh_content():
    random.shuffle(FIQH_TERMS)
    for term in FIQH_TERMS:
        print(f"🔍 [فقه] تجربة: {term}")
        try:
            url = f"https://dorar.net/dorar_api.json?skey={term}&callback=jsonp"
            resp = requests.get(url, timeout=20)
            match = re.search(r'jsonp\((.*)\)\s*$', resp.text, re.DOTALL)
            if not match:
                continue
            data = json.loads(match.group(1))
            ahadith = data.get("ahadith", [])
            if not ahadith:
                continue
            chosen = random.choice(ahadith)
            text = chosen.get("th") or chosen.get("hadith", "")
            text = clean_text(text)
            if not text:
                continue
            q_match = re.search(r'السؤال\s*:?\s*(.*?)(?:الجواب|$)', text, re.DOTALL)
            a_match = re.search(r'الجواب\s*:?\s*(.*)', text, re.DOTALL)
            if q_match and a_match:
                return q_match.group(1).strip(), a_match.group(1).strip()
            return text, ""
        except:
            continue
    return "لم نعثر على مسألة فقهية", ""

def format_fiqh_message(question, answer):
    msg = "📚 <b>مسألة فقهية</b>\n\n"
    msg += f"<b>السؤال:</b>\n{html.escape(question)}\n\n"
    if answer:
        short = answer[:1500]
        if len(answer) > 1500:
            short += " ..."
        msg += f"<b>الجواب:</b>\n{html.escape(short)}"
    return msg

# ---------- 5. إرسال الرسالة ----------
def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
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

# ---------- 6. الرئيسية ----------
def main():
    if len(sys.argv) < 2:
        print("❌ استخدم: python post_topic.py [hadith|fiqh|aqeeda]")
        sys.exit(1)
    topic = sys.argv[1].lower()
    try:
        if topic == "hadith":
            hid = get_random_hadith_id()
            print(f"🆔 رقم الحديث: {hid}")
            hadith_text, grade, rawi, mohdith, book, page, sharh = fetch_hadith_details(hid)
            msg = format_hadith_message(hadith_text, grade, rawi, mohdith, book, page, sharh)
        elif topic == "fiqh":
            q, a = fetch_fiqh_content()
            msg = format_fiqh_message(q, a)
        else:
            print("⚠️ العقيدة غير مفعلة بعد")
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
