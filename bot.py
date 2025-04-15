import logging
import os
import json
import gspread
import base64

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from google.oauth2.service_account import Credentials

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# Скоупы
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

# Декодируем base64 переменную в JSON
encoded_creds = os.environ["GOOGLE_CREDENTIALS_B64"]
decoded_creds = base64.b64decode(encoded_creds).decode("utf-8")
service_account_info = json.loads(decoded_creds)

# Авторизация Google Sheets
creds = Credentials.from_service_account_info(service_account_info, scopes=scope)
client = gspread.authorize(creds)

# Открытие таблицы
sheet = client.open_by_url(
    "https://docs.google.com/spreadsheets/d/1-PYvDusEahk2EYI2f4kDtu4uQ-pV756kz6fb_RXn-s8"
).sheet1

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Введи номер пружины, и я покажу на какой она полке.")

# Поиск пружины
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    data = sheet.get_all_records()

    for row in data:
        if str(row["Numer"]) == query:
            response = f"Numer: {row['Numer']}\nPolka: {row['Polka']}"
            await update.message.reply_text(response)
            return

    await update.message.reply_text("Пружина не найдена.")

# Запуск через polling
async def main():
    bot_token = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(bot_token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))

    # Запуск бота с polling
    await app.run_polling()

if __name__ == "__main__":
    # Используем существующий цикл событий
    import nest_asyncio
    nest_asyncio.apply()

    # Запускаем основной асинхронный цикл
    app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))

    # Запускаем бота с polling
    app.run_polling()
