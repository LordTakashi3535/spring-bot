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
    CallbackQueryHandler
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
            response = f"Найдено: {row['Numer']}\nПолка: {row['Polka']}"
            
            # Создаем кнопки для удаления или изменения полки
            keyboard = [
                [InlineKeyboardButton("Удалить", callback_data=f"delete_{query}")],
                [InlineKeyboardButton("Поменять полку", callback_data=f"change_shelf_{query}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Отправляем сообщение с кнопками
            await update.message.reply_text(response, reply_markup=reply_markup)
            return

    await update.message.reply_text("Пружина не найдена.")

# Обработчик для кнопок
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data.startswith("delete_"):
        # Логика удаления пружины
        spring_number = data.split("_")[1]
        data = sheet.get_all_records()
        for row in data:
            if str(row["Numer"]) == spring_number:
                sheet.delete_rows(data.index(row) + 2)  # Удаление строки из таблицы
                await query.message.reply_text(f"Пружина {spring_number} удалена.")
                return
        await query.message.reply_text(f"Пружина с номером {spring_number} не найдена.")

    elif data.startswith("change_shelf_"):
        # Логика изменения полки
        spring_number = data.split("_")[2]
        new_shelf = "НоваяПолка"  # Пример новой полки, можно сделать ввод от пользователя
        data = sheet.get_all_records()
        for row in data:
            if str(row["Numer"]) == spring_number:
                row_index = data.index(row) + 2
                sheet.update_cell(row_index, 2, new_shelf)
                await query.message.reply_text(f"Пружина {spring_number} теперь на полке {new_shelf}.")
                return
        await query.message.reply_text(f"Пружина с номером {spring_number} не найдена.")

# Запуск через polling
def main():
    bot_token = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(bot_token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))
    app.add_handler(CallbackQueryHandler(button))

    # Запуск бота с polling
    app.run_polling()

if __name__ == "__main__":
    # Запуск без asyncio.run() (используем run_polling напрямую)
    main()
