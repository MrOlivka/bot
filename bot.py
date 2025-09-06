import os
import logging
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from PIL import Image, ImageEnhance
import io
import zipfile
from asgiref.sync import async_to_sync

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Токен бота
TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    raise RuntimeError("Не найден TELEGRAM_TOKEN")

# Flask-приложение
app = Flask(__name__)

# Создаём папку для фото
os.makedirs("party_photos", exist_ok=True)

# Ограничение на количество фото
PHOTO_LIMIT = 15
user_photos = {}

# Команда /start
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "🎉 Привет! Загружай сюда фото с вечеринки! Максимум 15 фотографий."
    )

# Фильтр для фото (повышение яркости)
def apply_filter(image_bytes: bytes) -> bytes:
    image = Image.open(io.BytesIO(image_bytes))
    enhancer = ImageEnhance.Brightness(image)
    filtered = enhancer.enhance(1.2)

    output = io.BytesIO()
    filtered.save(output, format="JPEG")
    output.seek(0)
    return output.read()

# Обработка фото
async def handle_photo(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id

    if user_photos.get(user_id, 0) >= PHOTO_LIMIT:
        await update.message.reply_text("⚠️ Лимит 15 фотографий достигнут!")
        return

    photo = await update.message.photo[-1].get_file()
    image_bytes = await photo.download_as_bytearray()

    filtered_bytes = apply_filter(image_bytes)

    file_path = os.path.join("party_photos", f"{user_id}_{user_photos.get(user_id, 0)+1}.jpg")
    with open(file_path, "wb") as f:
        f.write(filtered_bytes)

    user_photos[user_id] = user_photos.get(user_id, 0) + 1
    await update.message.reply_text(f"✅ Фото сохранено! ({user_photos[user_id]}/{PHOTO_LIMIT})")

# Команда /download — скачать ZIP со всеми фото
async def download_all(update: Update, context: CallbackContext):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zipf:
        for filename in os.listdir("party_photos"):
            path = os.path.join("party_photos", filename)
            zipf.write(path, arcname=filename)
    zip_buffer.seek(0)

    await update.message.reply_document(document=zip_buffer, filename="party_photos.zip")

# Создаём Telegram-приложение
application = Application.builder().token(TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("download", download_all))
application.add_handler(MessageHandler(filters.PHOTO, handle_photo))

# Webhook: Telegram присылает сюда обновления
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return "OK"

# Маршрут для установки webhook
@app.route("/set_webhook", methods=["GET"])
def set_webhook():
    url = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/{TOKEN}"
    success = async_to_sync(application.bot.set_webhook)(url)
    return f"Webhook set: {success}"

# Запуск Flask-сервера
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
