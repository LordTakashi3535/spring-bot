import logging
import os
import json
import gspread
import base64

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    CallbackQueryHandler,
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
            context.user_data["found_spring"] = row["Numer"]  # Сохраняем найденную пружину

            response = f"Найдено: {row['Numer']}\nПолка: {row['Polka']}"
            keyboard = [
                [InlineKeyboardButton("Удалить", callback_data=f"delete_{query}")],
                [InlineKeyboardButton("Поменять полку", callback_data=f"change_shelf_{query}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(response, reply_markup=reply_markup)
            return

    await update.message.reply_text("Пружина не найдена.")

# Обработчик кнопок
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    spring_number = data.split("_")[1]

    if data.startswith("delete_"):
        data = sheet.get_all_records()
        for row in data:
            if str(row["Numer"]) == spring_number:
                sheet.delete_rows(data.index(row) + 2)
                await query.message.reply_text(f"Пружина {spring_number} удалена.")
                return
        await query.message.reply_text(f"Пружина с номером {spring_number} не найдена.")

    elif data.startswith("change_shelf_"):
        context.user_data["awaiting_new_shelf"] = spring_number
        await query.message.reply_text("Введите новый номер полки:")

# Обработчик ввода нового номера полки
async def handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip()

    if "awaiting_new_shelf" in context.user_data:
        spring_number = context.user_data["awaiting_new_shelf"]
        new_shelf = user_input
        data = sheet.get_all_records()

        for row in data:
            if str(row["Numer"]) == spring_number:
                row_index = data.index(row) + 2
                sheet.update_cell(row_index, 2, new_shelf)
                await update.message.reply_text(f"Полка для пружины {spring_number} обновлена на {new_shelf}.")
                context.user_data.pop("awaiting_new_shelf", None)
                return

        await update.message.reply_text("Ошибка: пружина не найдена.")
        context.user_data.pop("awaiting_new_shelf", None)

# Запуск
def main():
    bot_token = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(bot_token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_input))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))
    app.add_handler(CallbackQueryHandler(button))

    app.run_polling()

if __name__ == "__main__":
    main()

