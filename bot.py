import os
import logging
from io import BytesIO
from PIL import Image, ImageEnhance
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)
import zipfile
from pathlib import Path

logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
PHOTO_LIMIT = 15
BASE_DIR = Path("party_photos")
BASE_DIR.mkdir(exist_ok=True)
ADMIN_ID = 123456789

user_photos_count = {}

def apply_filter(image_bytes):
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    enhancer = ImageEnhance.Color(img)
    img = enhancer.enhance(1.2)
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.1)
    output = BytesIO()
    img.save(output, format="JPEG", quality=90)
    return output.getvalue()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_dir = BASE_DIR / str(user_id)
    user_dir.mkdir(exist_ok=True)
    user_photos_count[user_id] = len(list(user_dir.glob("*.jpg")))
   await update.message.reply_text(
    f"""🎉 Привет, {update.effective_user.first_name}!
Отправь мне до {PHOTO_LIMIT} фото, и я их обработаю 📸"""
)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_dir = BASE_DIR / str(user_id)
    user_dir.mkdir(exist_ok=True)
    count = user_photos_count.get(user_id, len(list(user_dir.glob("*.jpg"))))
    if count >= PHOTO_LIMIT:
        await update.message.reply_text("🚫 Лимит фото исчерпан!")
        return

    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    file_bytes = await file.download_as_bytearray()
    filtered_bytes = apply_filter(file_bytes)
    filename = user_dir / f"{count + 1}.jpg"
    with open(filename, "wb") as f:
        f.write(filtered_bytes)
    user_photos_count[user_id] = count + 1

    await update.message.reply_text(
        f"✅ Фото {count+1}/{PHOTO_LIMIT} сохранено и обработано!"
    )

async def count_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    uploaded = user_photos_count.get(user_id, 0)
    left = PHOTO_LIMIT - uploaded
    await update.message.reply_text(f"📸 Загружено {uploaded}/{PHOTO_LIMIT}. Осталось {left}.")

async def zip_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Доступ запрещен!")
        return
    zip_path = BASE_DIR / "all_photos.zip"
    with zipfile.ZipFile(zip_path, "w") as zipf:
        for root, _, files in os.walk(BASE_DIR):
            for file in files:
                if file.endswith(".jpg"):
                    filepath = Path(root) / file
                    zipf.write(filepath, arcname=filepath.relative_to(BASE_DIR))
    await update.message.reply_document(open(zip_path, "rb"))

def main():
    if not TELEGRAM_TOKEN:
        raise RuntimeError("Не найден TELEGRAM_TOKEN")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("count", count_cmd))
    app.add_handler(CommandHandler("zip", zip_all))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.run_polling()

if __name__ == "__main__":
    main()
