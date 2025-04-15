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
    keyboard = [
        [InlineKeyboardButton("Добавить пружину", callback_data='add')],
        [InlineKeyboardButton("Удалить пружину", callback_data='delete')],
        [InlineKeyboardButton("Изменить полку", callback_data='change_shelf')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Привет! Выберите действие:", reply_markup=reply_markup)

# Добавление пружины
async def add_spring(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("Введите данные для добавления пружины (формат: Номер, Полка)")

# Удаление пружины
async def delete_spring(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("Введите номер пружины для удаления")

# Изменение полки
async def change_shelf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("Введите номер пружины, для которой хотите изменить полку")

# Обработчик ответов пользователя на действия с пружинами
async def handle_user_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip()
    action = context.user_data.get("action")

    if action == "add":
        # Логика добавления пружины
        try:
            numer, polka = user_input.split(",")
            sheet.append_row([numer.strip(), polka.strip()])
            await update.message.reply_text(f"Пружина {numer.strip()} добавлена на полку {polka.strip()}.")
        except ValueError:
            await update.message.reply_text("Неверный формат данных. Попробуйте снова.")

    elif action == "delete" or action == "change_shelf":
        # Логика поиска пружины
        data = sheet.get_all_records()
        for row in data:
            if str(row["Numer"]) == user_input:
                # Создание кнопок для удаления или изменения полки
                keyboard = [
                    [InlineKeyboardButton("Удалить", callback_data=f"delete_{user_input}")],
                    [InlineKeyboardButton("Поменять полку", callback_data=f"change_shelf_{user_input}")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(f"Пружина {user_input} найдена. Что хотите сделать?", reply_markup=reply_markup)
                return
        
        await update.message.reply_text(f"Пружина с номером {user_input} не найдена.")

    # Сбросить действие после завершения
    context.user_data["action"] = None

# Обработчик для кнопок
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data == "add":
        context.user_data["action"] = "add"
        await add_spring(update, context)
    elif data == "delete":
        context.user_data["action"] = "delete"
        await delete_spring(update, context)
    elif data == "change_shelf":
        context.user_data["action"] = "change_shelf"
        await change_shelf(update, context)
    elif data.startswith("delete_"):
        # Удаление пружины
        spring_number = data.split("_")[1]
        data = sheet.get_all_records()
        for row in data:
            if str(row["Numer"]) == spring_number:
                sheet.delete_rows(data.index(row) + 2)
                await query.message.reply_text(f"Пружина {spring_number} удалена.")
                return
        await query.message.reply_text(f"Пружина с номером {spring_number} не найдена.")
    elif data.startswith("change_shelf_"):
        # Изменение полки
        spring_number = data.split("_")[2]
        new_shelf = "НоваяПолка"  # Пример новой полки, это можно реализовать через следующий ввод
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
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_input))

    # Запуск бота с polling
    app.run_polling()

if __name__ == "__main__":
    main()
