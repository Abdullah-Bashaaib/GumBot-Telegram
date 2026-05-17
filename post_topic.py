# -*- coding: utf-8 -*-
import os
import sys
import re
import requests
import unicodedata

# ---------- الإعدادات ----------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_IDS_RAW = os.environ.get("CHANNEL_IDS")
ADMIN_CHAT_ID = os.environ.get("ADMIN_ID")

STICKER_FILE_ID = "CAACAgQAAxkBAAFJ0dFqCNqgqqCjECNmTxnrb4BkgfqbQgACOQ4AAmzbwVJxfz2bNDpn8TsE"

print(f"DEBUG ADMIN_ID raw = '{ADMIN_CHAT_ID}'")

if not BOT_TOKEN or not CHANNEL_IDS_RAW:
    print("❌ يجب تعيين BOT_TOKEN و CHANNEL_IDS كمتغيرات بيئة")
    sys.exit(1)

CHANNEL_LIST = [ch.strip() for ch in CHANNEL_IDS_RAW.split(',') if ch.strip()]
print(f"📡 القنوات المستهدفة: {CHANNEL_LIST}")

if ADMIN_CHAT_ID:
    print(f"🔔 سيتم إرسال تنبيهات الأخطاء إلى معرف الأدمن: {ADMIN_CHAT_ID}")
else:
    print("⚠️ لم يتم تعيين ADMIN_ID، لن يتم إرسال تنبيهات الأخطاء.")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ---------- قواميس الترجمة ----------
COLLECTION_NAMES_AR = {
    "sahih bukhari": "صحيح البخاري",
    "sahih muslim": "صحيح مسلم",
    "jami at-tirmidhi": "جامع الترمذي",
    "sunan abi dawud": "سنن أبي داود",
    "sunan an-nasa'i": "سنن النسائي",
    "sunan ibn majah": "سنن ابن ماجه",
    "muwatta malik": "موطأ مالك",
    "musnad ahmad": "مسند أحمد",
    "riyad as-salihin": "رياض الصالحين",
    "al-adab al-mufrad": "الأدب المفرد",
    "bulugh al-maram": "بلوغ المرام",
    "shama'il muhammadiyyah": "الشمائل المحمدية",
    "forty hadith an-nawawi": "الأربعون النووية",
    "forty hadith nawawi": "الأربعون النووية",
    "sunan ad-darimi": "سنن الدارمي",
}

GRADE_AR = {
    "sahih": "صحيح",
    "hasan": "حسن",
    "daif": "ضعيف",
    "mauquf sahih": "صحيح موقوف",
    "hasan sahih": "حسن صحيح",
    "sahih hasan": "صحيح حسن",
    "maudhu": "موضوع",
    "munkar": "منكر",
}

ACCEPTED_GRADES = ["sahih", "hasan", "sahih hasan", "hasan sahih", "mauquf sahih"]

def translate_collection(name_en):
    if not name_en:
        return ""
    return COLLECTION_NAMES_AR.get(name_en.lower().strip(), name_en)

def translate_grade(grade_en):
    if not grade_en:
        return ""
    return GRADE_AR.get(grade_en.lower().strip(), grade_en)

def is_accepted_grade(grade_en):
    if not grade_en:
        return False
    return grade_en.lower().strip() in ACCEPTED_GRADES

# ---------- تنظيف النص العربي ----------
def clean_arabic(text):
    if not text:
        return ""
    text = re.sub(
        r'[\u200b\u200c\u200d\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2060\u2061\u2062\u2063\u2064\u2066\u2067\u2068\u2069\uFEFF]',
        '', text)
    text = unicodedata.normalize('NFC', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# ---------- هروب أحرف MarkdownV2 ----------
def escape_markdown_v2(text):
    if not text:
        return ""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

# ---------- إرسال رسالة نصية ----------
def send_telegram_message(chat_id, text, parse_mode='MarkdownV2'):
    url = f"{TELEGRAM_API}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    try:
        r = requests.post(url, json=payload)
        if r.status_code == 200:
            return True
        else:
            print(f"⚠️ فشل إرسال رسالة إلى {chat_id}: {r.text}")
            return False
    except Exception as e:
        print(f"⚠️ خطأ في الاتصال أثناء إرسال رسالة إلى {chat_id}: {e}")
        return False

# ---------- إرسال ملصق ----------
def send_sticker(chat_id, file_id):
    url = f"{TELEGRAM_API}/sendSticker"
    payload = {
        "chat_id": chat_id,
        "sticker": file_id
    }
    try:
        r = requests.post(url, json=payload)
        if r.status_code == 200:
            print(f"✅ تم إرسال الملصق إلى {chat_id}")
            return True
        else:
            print(f"⚠️ فشل إرسال الملصق إلى {chat_id}: {r.text}")
            return False
    except Exception as e:
        print(f"⚠️ خطأ في إرسال الملصق إلى {chat_id}: {e}")
        return False

# ---------- إرسال إشعار خطأ إلى الأدمن ----------
def send_error_notification(error_message):
    if not ADMIN_CHAT_ID:
        return
    text = f"⚠️ تنبيه خطأ من بوت الحديث:\n{error_message}"
    send_telegram_message(ADMIN_CHAT_ID, text, parse_mode=None)

# ---------- جلب حديث صحيح ----------
def fetch_hadith():
    max_attempts = 10
    for attempt in range(1, max_attempts + 1):
        print(f"📜 محاولة {attempt} لجلب حديث صحيح...")
        try:
            resp = requests.get("https://ummahapi.com/api/hadith/random", timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"   ⚠️ فشل الاتصال: {e}")
            continue

        if not data.get("success"):
            print("   ⚠️ API لم يُرجع نجاحًا")
            continue

        hadith_data = data["data"]
        arabic_text = hadith_data.get("arabic", "").strip()
        collection = hadith_data.get("collection_name", "")
        number = hadith_data.get("hadithnumber", "")
        grade = hadith_data.get("grade", "")

        if not arabic_text:
            print("   ⚠️ نص فارغ")
            continue

        if not is_accepted_grade(grade):
            grade_ar = translate_grade(grade) or grade
            print(f"   ⚠️ الحديث {grade_ar} مرفوض")
            continue

        arabic_text = clean_arabic(arabic_text)
        collection_ar = translate_collection(collection)
        grade_ar = translate_grade(grade)
        print(f"   ✅ حديث مقبول: {grade_ar}")
        return arabic_text, collection_ar, number, grade_ar

    raise Exception("لم نعثر على حديث صحيح بعد عدة محاولات")

# ---------- تنسيق الرسالة ----------
def format_hadith(arabic_text, collection, number, grade):
    text_escaped = escape_markdown_v2(arabic_text)
    collection_esc = escape_markdown_v2(collection) if collection else ""
    grade_esc = escape_markdown_v2(grade) if grade else ""
    number_esc = str(number) if number else ""

    msg = "📜 *حديث اليوم*\n\n"
    msg += f"> *{text_escaped}*\n\n"

    info = []
    if collection_esc:
        info.append(f"📖 *المصدر:* {collection_esc}")
    if number_esc:
        info.append(f"🔢 *رقم الحديث:* {number_esc}")
    if info:
        msg += " ┃ ".join(info) + "\n"
    if grade_esc:
        msg += f"✅ *الحكم:* {grade_esc}"

    return msg

# ---------- إرسال الحديث والملصق إلى جميع القنوات ----------
def send_message(text):
    success_count = 0
    failed_channels = []

    for channel_id in CHANNEL_LIST:
        # أولاً: إرسال الحديث
        if send_telegram_message(channel_id, text):
            print(f"✅ تم إرسال الحديث إلى {channel_id}")
            # ثانياً: إرسال الملصق مباشرة بعده
            send_sticker(channel_id, STICKER_FILE_ID)
            success_count += 1
        else:
            print(f"❌ فشل إرسال الحديث إلى {channel_id}")
            failed_channels.append(channel_id)

    if failed_channels:
        error_msg = "فشل إرسال حديث اليوم إلى القنوات التالية:\n"
        error_msg += "\n".join(f"• {ch}" for ch in failed_channels)
        send_error_notification(error_msg)

    if success_count == 0:
        raise Exception("لم يتم الإرسال إلى أي قناة بنجاح")

    print(f"✅ تم إرسال الرسالة والملصق إلى {success_count} قناة بنجاح")

# ---------- تشغيل ----------
def main():
    if len(sys.argv) < 2:
        print("❌ استخدم: python post_topic.py [hadith]")
        sys.exit(1)

    topic = sys.argv[1].lower()
    if topic != "hadith":
        print("❌ هذا السكريبت مخصص للحديث فقط")
        sys.exit(1)

    if ADMIN_CHAT_ID:
        send_telegram_message(
            ADMIN_CHAT_ID,
            "✅ اختبار تنبيه: البوت يعمل وإعدادات ADMIN_ID صحيحة.",
            parse_mode=None
        )
        print("تم إرسال رسالة اختبار إلى الأدمن")
    else:
        print("⚠️ ADMIN_ID غير معيّن، تخطي رسالة الاختبار")

    try:
        arabic, col, num, grade = fetch_hadith()
        msg = format_hadith(arabic, col, num, grade)

        print("\n" + "=" * 40)
        print(msg)
        print("=" * 40 + "\n")

        send_message(msg)
        print("✅ تم إرسال حديث واحد لجميع القنوات")

    except Exception as e:
        error_str = str(e)
        print(f"❌ خطأ: {error_str}")
        send_error_notification(f"حدث خطأ أثناء تشغيل بوت الحديث:\n{error_str}")
        sys.exit(1)

if __name__ == "__main__":
    main()
