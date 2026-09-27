import os
import shutil
import asyncio
import fitz  # PyMuPDF
from pptx import Presentation
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai
import arabic_reshaper
from bidi.algorithm import get_display

# 1. الإعدادات والمفاتيح
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "ضع_توكن_بوت_تليجرام_هنا")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "ضع_مفتاح_GEMINI_API_هنا")

# ضع هنا معرف قناتك أو رابطها (مثال: @frfshh_98)
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "@frfshh_98") 

client = genai.Client(api_key=GEMINI_API_KEY)

# دالة التحقق من اشتراك المستخدم الإجباري
async def is_subscribed(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        # السماح للمشرفين، المالك، والأعضاء
        if member.status in ['creator', 'administrator', 'member']:
            return True
        return False
    except Exception as e:
        print(f"خطأ أثناء فحص الاشتراك (تأكد من رفع البوت مشرفاً في القناة): {e}")
        # في حال حدوث خطأ بالسيرفر أو المعرف، نسمح له بالمرور حتى لا يتعطل البوت تماماً
        return True

# رسالة إجبار الاشتراك مع زر شفاف للدخول إلى القناة
async def send_join_prompt(update: Update):
    clean_username = CHANNEL_USERNAME.replace("@", "")
    keyboard = [
        [InlineKeyboardButton("📢 اشترك في القناة هنا", url=f"https://t.me/{clean_username}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        "⚠️ **عذراً عزيزي، لا يمكنك استخدام البوت قبل الاشتراك في القناة!**\n\n"
        f"اضغط على الزر أدناه للاشتراك في القناة: {CHANNEL_USERNAME}\n"
        "ثم أعد إرسال الملف وسيقوم البوت بترجمته لك فوراً."
    )
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

# 2. دالة الترجمة باستخدام Gemini
def translate_text(text: str) -> str:
    if not text.strip():
        return ""
    prompt = (
        "Translate the following academic content into clear, accurate Arabic. "
        "Keep technical terms, formulas, code snippets, and symbols intact. "
        "Only output the translation:\n\n" + text
    )
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt
    )
    return response.text.strip()

# ضبط اتجاه وتشكيل النص العربي للـ PDF
def fix_arabic(text: str) -> str:
    reshaped_text = arabic_reshaper.reshape(text)
    return get_display(reshaped_text)

# 3. معالجة وتوليد ملف PDF المزدوج
def process_pdf(input_path: str, output_path: str):
    doc = fitz.open(input_path)
    new_doc = fitz.open()

    for page_num in range(len(doc)):
        original_page = doc[page_num]
        new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)

        text = original_page.get_text()
        if text.strip():
            translated = translate_text(text)
            rect = original_page.rect
            trans_page = new_doc.new_page(width=rect.width, height=rect.height)
            
            formatted_text = fix_arabic(translated)
            text_rect = fitz.Rect(40, 40, rect.width - 40, rect.height - 40)
            trans_page.insert_textbox(
                text_rect,
                formatted_text,
                fontsize=11,
                align=2 # محاذاة لليمين
            )

    new_doc.save(output_path)
    new_doc.close()
    doc.close()

# 4. معالجة وتوليد ملف PPTX المزدوج
def process_pptx(input_path: str, output_path: str):
    prs = Presentation(input_path)
    blank_layout = prs.slide_layouts[6]
    total_slides = len(prs.slides)

    for i in range(total_slides - 1, -1, -1):
        slide = prs.slides[i]
        slide_texts = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                slide_texts.append(shape.text_frame.text)

        full_text = "\n".join(slide_texts)
        if full_text.strip():
            translated = translate_text(full_text)
            new_slide = prs.slides.add_slide(blank_layout)
            txBox = new_slide.shapes.add_textbox(left=0, top=0, width=prs.slide_width, height=prs.slide_height)
            tf = txBox.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.text = translated

    prs.save(output_path)

# 5. معالجات التليجرام
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # فحص الاشتراك الإجباري عند إرسال /start
    user_id = update.effective_user.id
    if not await is_subscribed(user_id, context):
        await send_join_prompt(update)
        return

    await update.message.reply_text(
        "أهلاً بك! أرسل لي أي ملف محاضرة بصيغة PDF أو PPTX وسأقوم بترجمته مع إبقاء الصفحة الأصلية متبوعة بصفحة الترجمة."
    )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # فحص الاشتراك الإجباري قبل بدء معالجة الملف
    if not await is_subscribed(user_id, context):
        await send_join_prompt(update)
        return

    document = update.message.document
    file_name = document.file_name
    ext = os.path.splitext(file_name)[1].lower()

    if ext not in ['.pdf', '.pptx']:
        await update.message.reply_text("عذراً، يدعم البوت ملفات PDF و PPTX فقط.")
        return

    status_msg = await update.message.reply_text("جاري تنزيل الملف وبدء الترجمة المزدوجة صفحة بصفحة...")

    file = await document.get_file()
    input_file = f"temp_{document.file_id}{ext}"
    output_file = f"translated_{file_name}"

    await file.download_to_drive(input_file)

    try:
        if ext == '.pdf':
            process_pdf(input_file, output_file)
        else:
            process_pptx(input_file, output_file)

        await status_msg.edit_text("اكتملت الترجمة! جاري رفع الملف...")
        with open(output_file, 'rb') as f:
            await update.message.reply_document(document=f, caption="تمت الترجمة بنجاح (صفحة أصلية تليها صفحة مترجمة).")
    except Exception as e:
        await update.message.reply_text(f"حدث خطأ أثناء المعالجة: {e}")
    finally:
        if os.path.exists(input_file): os.remove(input_file)
        if os.path.exists(output_file): os.remove(output_file)
        await status_msg.delete()

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    print("البوت يعمل الآن بنجاح مع تفعيل الاشتراك الإجباري...")
    app.run_polling()
