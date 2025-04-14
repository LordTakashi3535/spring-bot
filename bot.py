import logging
import os
import gspread
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from oauth2client.service_account import ServiceAccountCredentials
import json

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# СКОУПЫ
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

# Загрузка кредов
creds_dict = json.loads(os.environ["GOOGLE_CREDS_JSON"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scopes=scope)
client = gspread.authorize(creds)

# Подключаемся к таблице
sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1-PYvDusEahk2EYI2f4kDtu4uQ-pV756kz6fb_RXn-s8").sheet1

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Введи номер пружины, и я покажу на какой она полке.")

# Поиск пружины
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    data = sheet.get_all_records()

    for row in data:
        if str(row["Numer"]) == query:
            response = f"Номер: {row['Numer']}\nПолка: {row['Połka']}"
            await update.message.reply_text(response)
            return

    await update.message.reply_text("Пружина не найдена.")

# Основной запуск
def main():
    bot_token = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(bot_token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))

    app.run_polling()

if __name__ == "__main__":
    main()
