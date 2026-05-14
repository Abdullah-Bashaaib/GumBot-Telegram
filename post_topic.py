import os
import sys
import re
import html
import random
import requests
from bs4 import BeautifulSoup

# ========== الإعدادات ==========
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

if not BOT_TOKEN or not CHANNEL_ID:
    print("❌ يجب تعيين BOT_TOKEN و CHANNEL_ID")
    sys.exit(1)

# ========== كلمات البحث ==========
HADITH_TERMS = [
    "الصلاة", "الصيام", "الزكاة", "الحج", "الإيمان", "الإحسان",
    "بر الوالدين", "صلة الرحم", "الصدق", "الأمانة", "التقوى",
    "الجنة", "النار", "الذكر", "الدعاء", "الاستغفار", "التوبة"
]

FIQH_TERMS = [
    "حكم الصلاة", "حكم الصيام", "الطهارة", "الوضوء", "الزكاة",
    "الحج", "النكاح", "الطلاق", "البيع", "الميراث"
]

# ========== دالة مساعدة لتنظيف النصوص ==========
def clean_text(text):
    """إزالة الروابط وأي ذكر لموقع الدرر فقط، مع الحفاظ على بقية النص"""
    if not text:
        return ""
    # إزالة الروابط
    text = re.sub(r'https?://\S+', '', text)
    # إزالة اسم الموقع
    text = re.sub(r'الدرر السنية', '', text, flags=re.IGNORECASE)
    text = re.sub(r'dorar\.net', '', text, flags=re.IGNORECASE)
    return text.strip()

# ========== 1. جلب رقم حديث عشوائي ==========
def get_random_hadith_id():
    """يبحث بكلمة عشوائية ويعيد رقم حديث صحيح"""
    # نخلط القائمة عشوائياً
    random.shuffle(HADITH_TERMS)
    for term in HADITH_TERMS:
        print(f"🔍 تجربة كلمة: {term}")
        try:
            resp = requests.get(
                f"https://dorar.net/dorar_api.json?skey={term}",
                timeout=20
            )
            resp.raise_for_status()
            data = resp.json()
            # استخراج HTML النتيجة
            html_snippet = data.get("ahadith", {}).get("result", "")
            if not html_snippet:
                continue

            soup = BeautifulSoup(html_snippet, 'html.parser')
            # محاولة العثور على رابط الحديث القانوني
            link_tag = soup.find('link', rel='canonical')
            if link_tag and link_tag.get('href'):
                href = link_tag['href']
                match = re.search(r'/hadith/(\d+)', href)
                if match:
                    return int(match.group(1))

            # محاولة من onclick
            hadith_div = soup.find('div', class_='hadith')
            if hadith_div:
                onclick = hadith_div.get('onclick', '')
                match = re.search(r'/hadith/(\d+)', onclick)
                if match:
                    return int(match.group(1))
        except Exception as e:
            print(f"   فشل: {e}")
            continue
    raise Exception("لم نعثر على أي حديث مناسب")

# ========== 2. جلب بيانات الحديث والشرح من صفحة الشرح ==========
def fetch_hadith_details(hadith_id):
    """تزور صفحة شرح الحديث وتستخرج كل المعلومات"""
    url = f"https://dorar.net/hadith/sharh/{hadith_id}"
    print(f"📖 جلب شرح الحديث: {url}")
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, timeout=20, headers=headers)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, 'html.parser')

    # --- الحديث النبوي ---
    hadith_div = soup.find('div', class_='hadith-text') or soup.find('div', class_='hadith')
    if not hadith_div:
        # إذا لم نجد، نأخذ أي div يحتوي على نص طويل (احتياط)
        hadith_div = soup.find('div', class_='text-justify')
    if not hadith_div:
        raise Exception("لم يتم العثور على نص الحديث في صفحة الشرح")
    # نجمع النصوص النظيفة فقط بدون وسوم داخلية
    hadith_text = ' '.join(hadith_div.stripped_strings)
    hadith_text = clean_text(hadith_text)

    # --- المعلومات: الراوي، المحدث، المصدر، الحكم، الصفحة ---
    rawi = mohdith = book = page = grade = ""

    info_div = soup.find('div', class_='hadith-info')
    if info_div:
        # نبحث عن كل العلامات (span) التي تحمل عنوان المعلومة
        labels = info_div.find_all('span', class_='info-subtitle')
        for label in labels:
            label_text = label.get_text(strip=True)
            # القيمة تكون في span الذي يليه مباشرة
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

    # --- الشرح ---
    sharh_text = ""
    # الشرح عادة يكون في قسم المحتوى العام
    main_content = soup.find('div', class_='content') or soup.find('article')
    if main_content:
        # نستبعد الأجزاء التي تحوي الحديث والمعلومات (لأننا نريد الشرح فقط)
        # ببساطة: نأخذ النص الكامل ونستبعد سطور الحديث والمعلومات
        full_text = main_content.get_text(separator='\n', strip=True)
        lines = full_text.splitlines()
        # نبحث عن بداية الشرح (أول سطر طويل لا يحتوي على كلمات مفتاحية مثل "الراوي" أو "خلاصة")
        sharh_start = 0
        for i, line in enumerate(lines):
            if len(line) > 50 and 'الراوي' not in line and 'خلاصة' not in line and 'المحدث' not in line:
                sharh_start = i
                break
        sharh_text = '\n'.join(lines[sharh_start:]).strip()
    sharh_text = clean_text(sharh_text)

    return hadith_text, grade, rawi, mohdith, book, page, sharh_text

# ========== 3. تنسيق الرسالة (حديث) ==========
def format_hadith_message(hadith_text, grade, rawi, mohdith, book, page, sharh):
    msg = "📜 <b>حديث شريف:</b>\n\n"
    msg += f"قال رسول الله صلى الله عليه وسلم: {html.escape(hadith_text)}\n\n"
    if grade:
        msg += f"خلاصة حكم المحدث: [{html.escape(grade)}]\n"
    info_parts = []
    if rawi:
        info_parts.append(f"الراوي: {html.escape(rawi)}")
    if mohdith:
        info_parts.append(f"المحدث: {html.escape(mohdith)}")
    if book:
        info_parts.append(f"المصدر: {html.escape(book)}")
    if page:
        info_parts.append(f"الصفحة أو الرقم: {html.escape(page)}")
    if info_parts:
        msg += " | ".join(info_parts) + "\n"
    if sharh:
        # قد يكون الشرح طويلاً جداً، نقتطعه إلى 2000 حرف
        short_sharh = sharh[:2000]
        if len(sharh) > 2000:
            short_sharh += " ..."
        msg += f"\n<b>شرح الحديث:</b>\n{html.escape(short_sharh)}"
    return msg

# ========== 4. دوال الفقه (باستخدام API مباشر) ==========
def fetch_fiqh_content():
    """تبحث عن مسألة فقهية بنفس طريقة الحديث ولكن بدون شرح"""
    random.shuffle(FIQH_TERMS)
    for term in FIQH_TERMS:
        print(f"🔍 [فقه] تجربة: {term}")
        try:
            resp = requests.get(
                f"https://dorar.net/dorar_api.json?skey={term}",
                timeout=20
            )
            data = resp.json()
            html_snippet = data.get("ahadith", {}).get("result", "")
            if not html_snippet:
                continue
            soup = BeautifulSoup(html_snippet, 'html.parser')
            hadith_div = soup.find('div', class_='hadith')
            if hadith_div:
                text = ' '.join(hadith_div.stripped_strings)
                text = clean_text(text)
                if len(text) > 10:
                    # نحاول فصل السؤال عن الجواب باستخدام "السؤال:" و "الجواب:"
                    q_match = re.search(r'السؤال\s*:?\s*(.*?)(?:الجواب|$)', text, re.DOTALL)
                    a_match = re.search(r'الجواب\s*:?\s*(.*)', text, re.DOTALL)
                    if q_match and a_match:
                        question = q_match.group(1).strip()
                        answer = a_match.group(1).strip()
                        if len(question) > 5:
                            return question, answer
                    # إذا لم نجد، نعيد النص كاملاً كسؤال
                    return text, ""
        except Exception as e:
            print(f"   فشل: {e}")
            continue
    return "لم نعثر على مسألة فقهية", ""

def format_fiqh_message(question, answer):
    msg = "📚 <b>مسألة فقهية</b>\n\n"
    msg += f"<b>السؤال:</b>\n{html.escape(question)}\n\n"
    if answer:
        short_ans = answer[:1500]
        if len(answer) > 1500:
            short_ans += " ..."
        msg += f"<b>الجواب:</b>\n{html.escape(short_ans)}"
    return msg

# ========== 5. إرسال الرسالة إلى تيليجرام ==========
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
        raise Exception(f"فشل إرسال الرسالة: {r.text}")
    print("✅ تم إرسال الرسالة بنجاح")

# ========== 6. نقطة البداية ==========
def main():
    if len(sys.argv) < 2:
        print("❌ استخدم: python post_topic.py [hadith|fiqh|aqeeda]")
        sys.exit(1)

    topic = sys.argv[1].lower()

    try:
        if topic == "hadith":
            # 1. الحصول على رقم حديث عشوائي
            hid = get_random_hadith_id()
            print(f"🆔 رقم الحديث: {hid}")
            # 2. جلب التفاصيل من صفحة الشرح
            hadith_text, grade, rawi, mohdith, book, page, sharh = fetch_hadith_details(hid)
            # 3. تنسيق وإرسال
            msg = format_hadith_message(hadith_text, grade, rawi, mohdith, book, page, sharh)

        elif topic == "fiqh":
            question, answer = fetch_fiqh_content()
            msg = format_fiqh_message(question, answer)

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
