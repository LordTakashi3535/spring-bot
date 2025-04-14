import logging
import os
import gspread
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from oauth2client.service_account import ServiceAccountCredentials

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]
import json
import os
from oauth2client.service_account import ServiceAccountCredentials

creds_dict = json.loads(os.environ['GOOGLE_CREDS_JSON'])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scopes=SCOPES)
client = gspread.authorize(creds)

# ВСТАВЬ ТУТ ССЫЛКУ НА СВОЮ ТАБЛИЦУ:
sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1-PYvDusEahk2EYI2f4kDtu4uQ-pV756kz6fb_RXn-s8")
worksheet = sheet.sheet1

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Введи номер пружины, и я покажу данные.")

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    data = worksheet.get_all_records()
    for row in data:
        if str(row['Номер']) == query:
            response = f"Номер: {row['Номер']}\nПолка: {row['Полка']}\nТип: {row['Тип']}\nСтатус: {row['Статус']}"
            await update.message.reply_text(response)
            return
    await update.message.reply_text("Пружина не найдена.")

def main():
    bot_token = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(bot_token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))
    app.run_polling()

if __name__ == '__main__':
    main()
