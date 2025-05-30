import logging
import os
import json
import base64
from datetime import datetime

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

# Открываем таблицу и листы
spreadsheet = client.open_by_url(
    "https://docs.google.com/spreadsheets/d/1-PYvDusEahk2EYI2f4kDtu4uQ-pV756kz6fb_RXn-s8"
)
sheet = spreadsheet.sheet1
logs_sheet = spreadsheet.worksheet("Logs")

# Функция записи лога
async def log_action(context, user_id, username, action_type, details=""):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = [timestamp, user_id, username or "", action_type, details]
    try:
        logs_sheet.append_row(row)
    except Exception as e:
        logger.error(f"Błąd zapisu logu: {e}")

# Клавиатура "Отмена"
def cancel_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("Отмена", callback_data="cancel")]])

# Клавиатура полок (столбцами вниз)
def shelves_keyboard():
    A = ["A1", "A2", "A3", "A4", "A5", "A6", "A7"]
    B = ["B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8"]
    C = ["C1", "C2", "C3"]

    max_len = max(len(A), len(B), len(C))
    keyboard = []

    for i in range(max_len):
        row = []
        if i < len(A):
            row.append(InlineKeyboardButton(A[i], callback_data=f"move_shelf:{A[i].lower()}"))
        else:
            row.append(InlineKeyboardButton(" ", callback_data="noop"))

        if i < len(B):
            row.append(InlineKeyboardButton(B[i], callback_data=f"move_shelf:{B[i].lower()}"))
        else:
            row.append(InlineKeyboardButton(" ", callback_data="noop"))

        if i < len(C):
            row.append(InlineKeyboardButton(C[i], callback_data=f"move_shelf:{C[i].lower()}"))
        else:
            row.append(InlineKeyboardButton(" ", callback_data="noop"))

        keyboard.append(row)

    return InlineKeyboardMarkup(keyboard)

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить пружину", callback_data="add_spring")],
    ])
    await update.message.reply_text(
        "Cześć! Użyj komend lub кнопek:\n"
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
    user = update.effective_user
    data = sheet.get_all_records()

    if context.user_data.get("adding_spring"):
        if "spring_number" not in context.user_data:
            if text.lower() == "отмена":
                context.user_data.clear()
                await update.message.reply_text("Dodawanie sprężyny anulowane.")
                await log_action(context, user.id, user.username, "cancel_adding")
                return
            context.user_data["spring_number"] = text
            await update.message.reply_text(
                f"Numer sprężyny: {text}\nWybierz półkę:",
                reply_markup=shelves_keyboard()
            )
            return
        else:
            return

    try:
        if text.startswith("+"):
            content = text[1:].strip()
            number, shelf = [x.strip() for x in content.split(",")]
            sheet.append_row([number, shelf])
            await update.message.reply_text(f"✅ Sprężyna {number} dodana na półkę {shelf}.")
            await log_action(context, user.id, user.username, "add_spring", f"Numer: {number}, Polka: {shelf}")

        elif text.startswith("-"):
            number = text[1:].strip()
            for idx, row in enumerate(data, start=2):
                if str(row["Numer"]) == number:
                    sheet.delete_rows(idx)
                    await update.message.reply_text(f"❌ Sprężyna {number} została usunięta.")
                    await log_action(context, user.id, user.username, "delete_spring", f"Numer: {number}")
                    return
            await update.message.reply_text("⚠️ Sprężyna nie znaleziona.")

        elif text.startswith("="):
            content = text[1:].strip()
            number, new_shelf = [x.strip() for x in content.split(",")]
            for idx, row in enumerate(data, start=2):
                if str(row["Numer"]) == number:
                    sheet.update_cell(idx, 2, new_shelf)
                    await update.message.reply_text(f"🔁 Półka dla sprężyny {number} została zmieniona na {new_shelf}.")
                    await log_action(context, user.id, user.username, "move_shelf", f"Numer: {number}, Nowa polka: {new_shelf}")
                    return
            await update.message.reply_text("⚠️ Sprężyna nie znaleziona.")

        else:
            for row in data:
                if str(row["Numer"]) == text:
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
        await update.message.reply_text("❌ Błąd przetwarzania. Убедитесь, что формат команды правильный.")

# Обработка кнопок
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = update.effective_user

    if data == "cancel":
        await log_action(context, user.id, user.username, "cancel_action")
        context.user_data.clear()
        await query.edit_message_text("Akcja anulowana.")
        return

    if data == "add_spring":
        context.user_data.clear()
        context.user_data["adding_spring"] = True
        await query.edit_message_text("Wpisz numer sprężyny lub napisz 'Отмена' żeby wyjść.", reply_markup=cancel_keyboard())
        await log_action(context, user.id, user.username, "start_adding")
        return

    if context.user_data.get("adding_spring") and data.startswith("move_shelf:"):
        shelf = data.split(":", 1)[1]
        context.user_data["spring_shelf"] = shelf
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Potwierdź", callback_data="confirm_add")],
            [InlineKeyboardButton("Отмена", callback_data="cancel")]
        ])
        await query.edit_message_text(
            f"Numer sprężyny: {context.user_data['spring_number']}\n"
            f"Wybrana półka: {shelf.upper()}\n"
            "Naciśnij Potwierdź, aby dodać.",
            reply_markup=keyboard
        )
        return

    if data == "confirm_add" and context.user_data.get("adding_spring"):
        number = context.user_data.get("spring_number")
        shelf = context.user_data.get("spring_shelf")
        if number and shelf:
            sheet.append_row([number, shelf])
            await log_action(context, user.id, user.username, "add_spring", f"Numer: {number}, Polka: {shelf}")
            context.user_data.pop("spring_number", None)
            context.user_data.pop("spring_shelf", None)
            await query.edit_message_text(
                f"✅ Sprężyna {number} została pomyślnie dodana na półkę {shelf.upper()}.\n\n"
                "Wpisz następny numer sprężyny lub naciśnij 'Отмена' aby wyjść.",
                reply_markup=cancel_keyboard()
            )
        else:
            await query.edit_message_text("Błąd: brak danych do dodania.")
        return

    if data.startswith("delete:"):
        number = data.split(":", 1)[1]
        records = sheet.get_all_records()
        for idx, row in enumerate(records, start=2):
            if str(row["Numer"]) == number:
                sheet.delete_rows(idx)
                await log_action(context, user.id, user.username, "delete_spring", f"Numer: {number}")
                await query.edit_message_text(f"❌ Sprężyna {number} została usunięta.")
                return
        await query.edit_message_text("⚠️ Sprężyna nie znaleziona.")
        return

    if data.startswith("edit:"):
        number = data.split(":", 1)[1]
        context.user_data["editing_spring"] = number
        await query.edit_message_text(
            f"Wybierz nową półkę dla sprężyny {number}:",
            reply_markup=shelves_keyboard()
        )
        return

    if context.user_data.get("editing_spring") and data.startswith("move_shelf:"):
        shelf = data.split(":", 1)[1]
        number = context.user_data.get("editing_spring")
        records = sheet.get_all_records()
        for idx, row in enumerate(records, start=2):
            if str(row["Numer"]) == number:
                sheet.update_cell(idx, 2, shelf)
                await log_action(context, user.id, user.username, "move_shelf", f"Numer: {number}, Nowa polka: {shelf}")
                await query.edit_message_text(f"🔁 Sprężyna {number} została przeniesiona na półkę {shelf.upper()}.")
                context.user_data.clear()
                return
        await query.edit_message_text("⚠️ Sprężyna nie znaleziona.")
        context.user_data.clear()
        return

# Главная функция
def main():
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        logger.error("❌ BOT_TOKEN не установлен!")
        return

    app = ApplicationBuilder().token(bot_token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_input))
    app.add_handler(CallbackQueryHandler(callback_handler))

    logger.info("🤖 Бот запущен. Ожидает команды.")
    app.run_polling()

if __name__ == "__main__":
    main()
