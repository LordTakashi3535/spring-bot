import logging
import os
import json
import gspread
import base64

from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from google.oauth2.service_account import Credentials

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# Скоупы для Google Sheets
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

# Клавиатура для выбора полки (столбцами сверху вниз)
SHELVES = [
    ["A1", "B1", "C1"],
    ["A2", "B2", "C2"],
    ["A3", "B3", "C3"],
    ["A4", "B4"],
    ["A5", "B5"],
    ["A6", "B6"],
    ["A7", "B7"],
    [        "B8"]
]

def shelves_keyboard():
    keyboard = []
    for row in SHELVES:
        buttons = [InlineKeyboardButton(shelf.upper(), callback_data=f"move_shelf:{shelf}") for shelf in row]
        keyboard.append(buttons)
    keyboard.append([InlineKeyboardButton("Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(keyboard)

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Cześć! Użyj komend:\n"
        "+numer, półka — dodaj sprężynę\n"
        "-numer — usuń sprężynę\n"
        "=numer, nowa_półka — zmień półkę\n"
        "numer — sprawdź gdzie znajduje się sprężyna"
    )

# Функция отправки информации о пружине с кнопками Удалить и Редактировать
async def send_spring_info(update, context, number, shelf):
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Удалить", callback_data=f"delete:{number}"),
            InlineKeyboardButton("Редактировать", callback_data=f"edit:{number}")
        ]
    ])
    text = f"🔍 Znaleziono:\nNumer: {number}\nPółka: {shelf}"
    if update.message:
        await update.message.reply_text(text, reply_markup=keyboard)
    else:
        # если вызывается из callback_query
        await update.callback_query.edit_message_text(text, reply_markup=keyboard)

# Обработка сообщений пользователя
async def handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    data = sheet.get_all_records()

    try:
        if text.startswith("+"):
            # Добавление пружины
            content = text[1:].strip()
            number, shelf = [x.strip() for x in content.split(",")]
            sheet.append_row([number, shelf])
            await update.message.reply_text(f"✅ Sprężyna {number} dodana na półkę {shelf}.")

        elif text.startswith("-"):
            # Удаление пружины
            number = text[1:].strip()
            for idx, row in enumerate(data, start=2):
                if str(row["Numer"]) == number:
                    sheet.delete_rows(idx)
                    await update.message.reply_text(f"❌ Sprężyna {number} została usunięta.")
                    return
            await update.message.reply_text("⚠️ Sprężyna nie znaleziona.")

        elif text.startswith("="):
            # Изменение полки через текст
            content = text[1:].strip()
            number, new_shelf = [x.strip() for x in content.split(",")]
            for idx, row in enumerate(data, start=2):
                if str(row["Numer"]) == number:
                    sheet.update_cell(idx, 2, new_shelf)
                    await update.message.reply_text(f"🔁 Półka dla sprężyny {number} została zmieniona na {new_shelf}.")
                    return
            await update.message.reply_text("⚠️ Sprężyna nie znaleziona.")

        else:
            # Поиск пружины и вывод с кнопками
            for row in data:
                if str(row["Numer"]) == text:
                    await send_spring_info(update, context, row["Numer"], row["Polka"])
                    # Запоминаем номер для последующих действий редактирования/удаления
                    context.user_data["current_spring"] = row["Numer"]
                    return
            await update.message.reply_text("⚠️ Sprężyna nie znaleziona.")

    except Exception as e:
        logging.error(f"Błąd przy przetwarzaniu komendy: {e}")
        await update.message.reply_text("❌ Błąd przetwarzania. Upewnij się, że format komendy jest poprawny.")

# Обработка callback запросов (нажатий кнопок)
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "cancel":
        await query.edit_message_text("Действие отменено.")
        context.user_data.pop("edit_number", None)
        context.user_data.pop("current_spring", None)
        return

    elif data.startswith("delete:"):
        number_to_delete = data.split(":", 1)[1]
        data_sheet = sheet.get_all_records()
        for idx, row in enumerate(data_sheet, start=2):
            if str(row["Numer"]) == number_to_delete:
                sheet.delete_rows(idx)
                await query.edit_message_text(f"❌ Sprężyna {number_to_delete} została usunięta.")
                context.user_data.pop("current_spring", None)
                return
        await query.edit_message_text("⚠️ Sprężyna nie znaleziona.")

    elif data.startswith("edit:"):
        number_to_edit = data.split(":", 1)[1]
        context.user_data["edit_number"] = number_to_edit
        # Показать клавиатуру с выбором полки
        await query.edit_message_text(
            f"Выберите новую полку для пружины {number_to_edit}:",
            reply_markup=shelves_keyboard()
        )

    elif data.startswith("move_shelf:"):
        new_shelf = data.split(":", 1)[1]
        number_to_edit = context.user_data.get("edit_number")
        if not number_to_edit:
            await query.edit_message_text("Ошибка: не выбран номер пружины для редактирования.")
            return

        data_sheet = sheet.get_all_records()
        for idx, row in enumerate(data_sheet, start=2):
            if str(row["Numer"]) == number_to_edit:
                sheet.update_cell(idx, 2, new_shelf)
                await query.edit_message_text(
                    f"🔁 Пружина {number_to_edit} перемещена на полку {new_shelf}."
                )
                context.user_data.pop("edit_number", None)
                context.user_data.pop("current_spring", None)
                return
        await query.edit_message_text("⚠️ Sprężyna nie znaleziona.")

# Запуск бота
def main():
    bot_token = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(bot_token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_input))
    app.add_handler(CallbackQueryHandler(callback_handler))

    app.run_polling()

if __name__ == "__main__":
    main()
