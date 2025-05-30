import logging
import os
import json
import base64
import gspread

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

# Скоупы для Google API
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

# Декодируем base64 переменную с ключами
encoded_creds = os.environ["GOOGLE_CREDENTIALS_B64"]
decoded_creds = base64.b64decode(encoded_creds).decode("utf-8")
service_account_info = json.loads(decoded_creds)

# Авторизация Google Sheets
creds = Credentials.from_service_account_info(service_account_info, scopes=scope)
client = gspread.authorize(creds)

# Открываем таблицу и выбираем первый лист
sheet = client.open_by_url(
    "https://docs.google.com/spreadsheets/d/1-PYvDusEahk2EYI2f4kDtu4uQ-pV756kz6fb_RXn-s8"
).sheet1

# Кнопки полок (в столбцах)
SHELF_BUTTONS = [
    ["a1", "a2", "a3", "a4", "a5", "a6", "a7"],
    ["b1", "b2", "b3", "b4", "b5", "b6", "b7", "b8"],
    ["c1", "c2", "c3"]
]

def shelves_keyboard():
    keyboard = []
    for row in SHELF_BUTTONS:
        buttons = [InlineKeyboardButton(shelf.upper(), callback_data=f"move_shelf:{shelf}") for shelf in row]
        keyboard.append(buttons)
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])
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


# Обработка текстовых сообщений
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
                if str(row.get("Numer")) == number:
                    sheet.delete_rows(idx)
                    await update.message.reply_text(f"❌ Sprężyna {number} została usunięta.")
                    return
            await update.message.reply_text("⚠️ Sprężyna nie znaleziona.")

        elif text.startswith("="):
            # Изменение полки
            content = text[1:].strip()
            number, new_shelf = [x.strip() for x in content.split(",")]
            for idx, row in enumerate(data, start=2):
                if str(row.get("Numer")) == number:
                    sheet.update_cell(idx, 2, new_shelf)
                    await update.message.reply_text(f"🔁 Półka dla sprężyny {number} została zmieniona na {new_shelf}.")
                    return
            await update.message.reply_text("⚠️ Sprężyna nie znaleziona.")

        else:
            # Поиск пружины и показ кнопок
            for idx, row in enumerate(data, start=2):
                if str(row.get("Numer")) == text:
                    context.user_data["selected_spring"] = {"number": row["Numer"], "row": idx}
                    shelf = row.get("Polka", "—")
                    response_text = f"🔍 Найдена пружина:\nНомер: {row['Numer']}\nПолка: {shelf}"
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("Удалить", callback_data="delete_spring")],
                        [InlineKeyboardButton("Редактировать", callback_data="edit_spring")]
                    ])
                    await update.message.reply_text(response_text, reply_markup=keyboard)
                    return
            await update.message.reply_text("⚠️ Sprężyna nie znaleziona.")

    except Exception as e:
        logging.error(f"Błąd przy przetwarzaniu komendy: {e}")
        await update.message.reply_text("❌ Błąd przetwarzania. Upewnij się, że format komendy jest poprawny.")


# Обработка нажатий на кнопки
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "delete_spring":
        spring = context.user_data.get("selected_spring")
        if not spring:
            await query.edit_message_text("⚠️ Ошибка: Нет выбранной пружины.")
            return
        try:
            sheet.delete_rows(spring["row"])
            await query.edit_message_text(f"❌ Пружина {spring['number']} удалена.")
            context.user_data.pop("selected_spring", None)
        except Exception as e:
            await query.edit_message_text(f"Ошибка удаления: {e}")

    elif data == "edit_spring":
        spring = context.user_data.get("selected_spring")
        if not spring:
            await query.edit_message_text("⚠️ Ошибка: Нет выбранной пружины.")
            return
        await query.edit_message_text(
            "Выберите новую полку для пружины:",
            reply_markup=shelves_keyboard()
        )

    elif data.startswith("move_shelf:"):
        new_shelf = data.split(":", 1)[1]
        spring = context.user_data.get("selected_spring")
        if not spring:
            await query.edit_message_text("⚠️ Ошибка: Нет выбранной пружины.")
            return
        try:
            sheet.update_cell(spring["row"], 2, new_shelf)
            await query.edit_message_text(f"🔁 Пружина {spring['number']} перемещена на полку {new_shelf.upper()}.")
            context.user_data.pop("selected_spring", None)
        except Exception as e:
            await query.edit_message_text(f"Ошибка обновления: {e}")

    elif data == "cancel":
        context.user_data.pop("selected_spring", None)
        await query.edit_message_text("Действие отменено.")


def main():
    bot_token = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(bot_token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_input))
    app.add_handler(CallbackQueryHandler(callback_handler))

    app.run_polling()


if __name__ == "__main__":
    main()
