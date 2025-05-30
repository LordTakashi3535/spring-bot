import logging
import os
import json
import base64
import gspread

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
logger = logging.getLogger(__name__)

# Скоупы Google API
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive",
]

# Декодируем base64 переменную с credentials
encoded_creds = os.environ["GOOGLE_CREDENTIALS_B64"]
decoded_creds = base64.b64decode(encoded_creds).decode("utf-8")
service_account_info = json.loads(decoded_creds)

# Авторизация
creds = Credentials.from_service_account_info(service_account_info, scopes=scope)
client = gspread.authorize(creds)

# Открываем таблицу (замени URL на свою)
sheet = client.open_by_url(
    "https://docs.google.com/spreadsheets/d/1-PYvDusEahk2EYI2f4kDtu4uQ-pV756kz6fb_RXn-s8"
).sheet1

# Клавиатура "Отмена"
def cancel_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("Отмена", callback_data="cancel")]])

# Клавиатура полок (столбцами вниз)
def shelves_keyboard():
    shelves_columns = [
        ["a1", "b1", "c1"],
        ["a2", "b2", "c2"],
        ["a3", "b3", "c3"],
        ["a4", "b4"],
        ["a5", "b5"],
        ["a6", "b6"],
        ["a7", "b7"],
        [      "b8"],
    ]

    keyboard = []
    for column in shelves_columns:
        row_buttons = [InlineKeyboardButton(shelf.upper(), callback_data=f"move_shelf:{shelf}") for shelf in column]
        keyboard.append(row_buttons)
    return InlineKeyboardMarkup(keyboard)

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить пружину", callback_data="add_spring")],
    ])
    await update.message.reply_text(
        "Cześć! Użyj komend lub кнопок:\n"
        "+numer, półka — dodaj sprężynę\n"
        "-numer — usuń sprężynę\n"
        "=numer, nowa_półka — zmień półkę\n"
        "numer — sprawdź gdzie znajduje się sprężyna\n\n"
        "Или нажми кнопку для добавления пружины:",
        reply_markup=keyboard
    )

# Обработка текстовых сообщений
async def handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    data = sheet.get_all_records()

    # Режим добавления пружины (ждём ввод номера)
    if context.user_data.get("adding_spring"):
        if "spring_number" not in context.user_data:
            if text.lower() == "отмена":
                context.user_data.clear()
                await update.message.reply_text("Добавление пружины отменено.")
                return
            context.user_data["spring_number"] = text
            await update.message.reply_text(
                f"Номер пружины: {text}\nВыберите полку:",
                reply_markup=shelves_keyboard()
            )
            return
        else:
            # Здесь ничего не ждём, дальше управление через callback кнопки
            return

    try:
        if text.startswith("+"):
            content = text[1:].strip()
            number, shelf = [x.strip() for x in content.split(",")]
            sheet.append_row([number, shelf])
            await update.message.reply_text(f"✅ Sprężyna {number} dodana na półkę {shelf}.")

        elif text.startswith("-"):
            number = text[1:].strip()
            for idx, row in enumerate(data, start=2):
                if str(row["Numer"]) == number:
                    sheet.delete_rows(idx)
                    await update.message.reply_text(f"❌ Sprężyna {number} została usunięta.")
                    return
            await update.message.reply_text("⚠️ Sprężyna nie znaleziona.")

        elif text.startswith("="):
            content = text[1:].strip()
            number, new_shelf = [x.strip() for x in content.split(",")]
            for idx, row in enumerate(data, start=2):
                if str(row["Numer"]) == number:
                    sheet.update_cell(idx, 2, new_shelf)
                    await update.message.reply_text(f"🔁 Półka dla sprężyny {number} została zmieniona na {new_shelf}.")
                    return
            await update.message.reply_text("⚠️ Sprężyna nie znaleziona.")

        else:
            for row in data:
                if str(row["Numer"]) == text:
                    # Показываем данные с кнопками Удалить и Редактировать
                    keyboard = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("Удалить", callback_data=f"delete:{text}"),
                            InlineKeyboardButton("Редактировать", callback_data=f"edit:{text}")
                        ],
                        [InlineKeyboardButton("Отмена", callback_data="cancel")]
                    ])
                    response = f"🔍 Znaleziono:\nNumer: {row['Numer']}\nPółka: {row['Polka']}"
                    await update.message.reply_text(response, reply_markup=keyboard)
                    return
            await update.message.reply_text("⚠️ Sprężyna nie znaleziona.")

    except Exception as e:
        logger.error(f"Błąd przy przetwarzaniu komendy: {e}")
        await update.message.reply_text("❌ Błąd przetwarzania. Upewnij się, że format komendy jest poprawny.")

# Обработка нажатий кнопок
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "cancel":
        context.user_data.clear()
        await query.edit_message_text("Действие отменено.")
        return

    # Запуск режима добавления пружины
    if data == "add_spring":
        context.user_data.clear()
        context.user_data["adding_spring"] = True
        await query.edit_message_text("Введите номер пружины или напишите 'Отмена' для выхода.", reply_markup=cancel_keyboard())
        return

    # Выбор полки в режиме добавления
    if context.user_data.get("adding_spring") and data.startswith("move_shelf:"):
        shelf = data.split(":", 1)[1]
        context.user_data["spring_shelf"] = shelf
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Подтвердить", callback_data="confirm_add")],
            [InlineKeyboardButton("Отмена", callback_data="cancel")]
        ])
        await query.edit_message_text(
            f"Номер пружины: {context.user_data['spring_number']}\n"
            f"Выбрана полка: {shelf}\n"
            "Нажмите Подтвердить для добавления.",
            reply_markup=keyboard
        )
        return

    # Подтверждение добавления
    if data == "confirm_add" and context.user_data.get("adding_spring"):
        number = context.user_data.get("spring_number")
        shelf = context.user_data.get("spring_shelf")
        if number and shelf:
            sheet.append_row([number, shelf])
            await query.edit_message_text(f"✅ Пружина {number} успешно добавлена на полку {shelf}.")
            context.user_data.clear()
        else:
            await query.edit_message_text("Ошибка: отсутствуют данные для добавления.")
        return

    # Удаление пружины по кнопке
    if data.startswith("delete:"):
        number = data.split(":", 1)[1]
        records = sheet.get_all_records()
        for idx, row in enumerate(records, start=2):
            if str(row["Numer"]) == number:
                sheet.delete_rows(idx)
                await query.edit_message_text(f"❌ Пружина {number} была удалена.")
                return
        await query.edit_message_text("⚠️ Пружина не найдена.")
        return

    # Редактирование полки (выбор новой полки)
    if data.startswith("edit:"):
        number = data.split(":", 1)[1]
        context.user_data["editing_spring"] = number
        await query.edit_message_text(
            f"Выберите новую полку для пружины {number}:",
            reply_markup=shelves_keyboard()
        )
        return

    # Выбор полки при редактировании
    if context.user_data.get("editing_spring") and data.startswith("move_shelf:"):
        shelf = data.split(":", 1)[1]
        number = context.user_data.get("editing_spring")
        records = sheet.get_all_records()
        for idx, row in enumerate(records, start=2):
            if str(row["Numer"]) == number:
                sheet.update_cell(idx, 2, shelf)
                await query.edit_message_text(f"🔁 Пружина {number} перемещена на полку {shelf}.")
                context.user_data.clear()
                return
        await query.edit_message_text("⚠️ Пружина не найдена.")
        context.user_data.clear()
        return

# Основная функция запуска бота
def main():
    bot_token = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(bot_token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_input))
    app.add
