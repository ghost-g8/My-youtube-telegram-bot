import os
import math
import uuid
from pytube import YouTube
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)
from moviepy.video.io.VideoFileClip import VideoFileClip

BOT_TOKEN = os.getenv("BOT_TOKEN")

# محاسبه حجم فایل برای نمایش
def sizeof_fmt(num, suffix="B"):
    for unit in ["", "K", "M", "G", "T"]:
        if abs(num) < 1024.0:
            return f"{num:.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}P{suffix}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! لینک یوتیوب رو بفرست.")

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    try:
        yt = YouTube(url)
        context.user_data['yt'] = yt

        buttons = []
        seen = set()
        for stream in yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc():
            label = f"{stream.resolution}, {stream.fps}fps, {sizeof_fmt(stream.filesize)}"
            if label in seen: continue
            seen.add(label)
            cb = f"video|{stream.itag}"
            buttons.append([InlineKeyboardButton(label, callback_data=cb)])

        audio = yt.streams.filter(only_audio=True).first()
        buttons.append([InlineKeyboardButton(f"Audio Only, {sizeof_fmt(audio.filesize)}", callback_data=f"audio|{audio.itag}")])

        await update.message.reply_text("📥 کیفیت مورد نظر را انتخاب کن:", reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        await update.message.reply_text(f"❌ خطا: {e}")

async def handle_quality_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    yt = context.user_data.get('yt')
    if not yt:
        await query.edit_message_text("❌ لینک نامعتبر است.")
        return

    file_id = str(uuid.uuid4())
    kind, itag = query.data.split("|")
    stream = yt.streams.get_by_itag(int(itag))
    ext = '.mp4' if kind == 'video' else '.mp3'
    filename = f"downloads/{file_id}{ext}"
    context.user_data['filename'] = filename
    context.user_data['kind'] = kind

    await query.edit_message_text("⏳ لطفاً صبر کن، فایل در حال دانلود است...")
    stream.download(filename=filename)

    await query.message.reply_text("✂️ لطفاً بازه زمانی کات را وارد کن (مثلاً 30-90):")

async def handle_cut_range(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if 'filename' not in context.user_data:
        return
    if '-' not in text:
        await update.message.reply_text("❌ فرمت نادرست. مثلاً بنویس 30-90")
        return
    try:
        start, end = map(int, text.split('-'))
        input_path = context.user_data['filename']
        output_path = input_path.replace(".mp4", "_cut.mp4").replace(".mp3", "_cut.mp4")
        if context.user_data['kind'] == 'video':
            clip = VideoFileClip(input_path).subclip(start, end)
            clip.write_videofile(output_path, codec="libx264", audio_codec="aac")
        else:
            await update.message.reply_text("❌ برش صدا پشتیبانی نمی‌شود.")
            return

        context.user_data['cut_path'] = output_path
        await update.message.reply_text("📛 می‌خوای اسم فایل رو عوض کنی؟ اگر بله اسم جدید رو بفرست، اگر نه بنویس: نه")
    except Exception as e:
        await update.message.reply_text(f"❌ خطا در برش: {e}")

async def handle_rename(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'cut_path' not in context.user_data:
        return
    name = update.message.text.strip()
    final_path = context.user_data['cut_path']
    if name.lower() != "نه":
        base, ext = os.path.splitext(final_path)
        new_path = os.path.join("downloads", name + ext)
        os.rename(final_path, new_path)
        final_path = new_path

    with open(final_path, 'rb') as f:
        await update.message.reply_video(f)

    os.remove(context.user_data['filename'])
    os.remove(final_path)
    context.user_data.clear()

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    app.add_handler(CallbackQueryHandler(handle_quality_selection))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_cut_range))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_rename))
    os.makedirs("downloads", exist_ok=True)
    print("🤖 ربات آماده اجراست")
    app.run_polling()

if __name__ == "__main__":
    main()
