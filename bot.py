import logging
import os
import json
import gspread
import asyncio

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from google.oauth2.service_account import Credentials  # <- новое

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

# Авторизация Google Sheets через переменную окружения
service_account_info = json.loads(os.environ["GOOGLE_CREDENTIALS"])
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

# Запуск через вебхук (для Render)
async def main():
    bot_token = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(bot_token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))

    webhook_url = "https://spring-bot-pvta.onrender.com"

    await app.initialize()
    await app.start()
    await app.bot.set_webhook(webhook_url)
    await app.updater.start_webhook(
        listen="0.0.0.0",
        port=10000,
        webhook_url=webhook_url
    )
    await app.updater.idle()

if __name__ == "__main__":
    asyncio.run(main())
