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

# Logowanie
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Zakresy Google API
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive",
]

# Dekodowanie zmiennej środowiskowej z credentials (base64)
encoded_creds = os.environ["GOOGLE_CREDENTIALS_B64"]
decoded_creds = base64.b64decode(encoded_creds).decode("utf-8")
service_account_info = json.loads(decoded_creds)

# Autoryzacja
creds = Credentials.from_service_account_info(service_account_info, scopes=scope)
client = gspread.authorize(creds)

# Otwieranie arkusza
sheet = client.open_by_url(
    "https://docs.google.com/spreadsheets/d/1-PYvDusEahk2EYI2f4kDtu4uQ-pV756kz6fb_RXn-s8"
).sheet1

# Klawiatura "Anuluj"
def cancel_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("Anuluj", callback_data="cancel")]])

# Klawiatura półek (kolumnami w dół)
def shelves_keyboard():
    a = ["A1", "A2", "A3", "A4", "A5", "A6", "A7"]
    b = ["B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8"]
    c = ["C1", "C2", "C3"]

    max_len = max(len(a), len(b), len(c))
    keyboard = []

    for i in range(max_len):
        row = []
        if i < len(a):
            row.append(InlineKeyboardButton(a[i], callback_data=f"move_shelf:{a[i].lower()}"))
        else:
            row.append(InlineKeyboardButton(" ", callback_data="noop"))

        if i < len(b):
            row.append(InlineKeyboardButton(b[i], callback_data=f"move_shelf:{b[i].lower()}"))
        else:
            row.append(InlineKeyboardButton(" ", callback_data="noop"))

        if i < len(c):
            row.append(InlineKeyboardButton(c[i], callback_data=f"move_shelf:{c[i].lower()}"))
        else:
            row.append(InlineKeyboardButton(" ", callback_data="noop"))

        keyboard.append(row)

    return InlineKeyboardMarkup(keyboard)

# Komenda /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Dodaj sprężynę", callback_data="add_spring")],
    ])
    await update.message.reply_text(
        "Cześć! Użyj komend lub przycisków:\n"
        "+numer, półka — dodaj sprężynę\n"
        "-numer — usuń sprężynę\n"
        "=numer, nowa_półka — zmień półkę\n"
        "numer — sprawdź gdzie znajduje się sprężyna\n\n"
        "Lub kliknij przycisk, aby dodać sprężynę:",
        reply_markup=keyboard
    )

# Nowa komenda /add — uruchamia tryb dodawania sprężyny
async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["adding_spring"] = True
    await update.message.reply_text(
        "🔧 Tryb dodawania sprężyn\n\nWprowadź numer sprężyny lub wpisz 'Anuluj', aby wyjść.",
        reply_markup=cancel_keyboard()
    )

# Obsługa wiadomości tekstowych
async def handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    data = sheet.get_all_records()

    if context.user_data.get("adding_spring"):
        if "spring_number" not in context.user_data:
            if text.lower() == "anuluj":
                context.user_data.clear()
                await update.message.reply_text("Dodawanie sprężyny anulowane.")
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
                    keyboard = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("Usuń", callback_data=f"delete:{text}"),
                            InlineKeyboardButton("Edytuj", callback_data=f"edit:{text}")
                        ],
                        [InlineKeyboardButton("Anuluj", callback_data="cancel")]
                    ])
                    response = f"🔍 Znaleziono:\nNumer: {row['Numer']}\nPółka: {row['Polka']}"
                    await update.message.reply_text(response, reply_markup=keyboard)
                    return
            await update.message.reply_text("⚠️ Sprężyna nie znaleziona.")

    except Exception as e:
        logger.error(f"Błąd podczas przetwarzania komendy: {e}")
        await update.message.reply_text("❌ Błąd przetwarzania. Upewnij się, że format komendy jest prawidłowy.")

# Obsługa przycisków
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "cancel":
        context.user_data.clear()
        await query.edit_message_text("Akcja anulowana.")
        return

    if data == "add_spring":
        context.user_data.clear()
        context.user_data["adding_spring"] = True
        await query.edit_message_text("Wprowadź numer sprężyny lub wpisz 'Anuluj', aby wyjść.", reply_markup=cancel_keyboard())
        return

    if context.user_data.get("adding_spring") and data.startswith("move_shelf:"):
        shelf = data.split(":", 1)[1]
        context.user_data["spring_shelf"] = shelf
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Potwierdź", callback_data="confirm_add")],
            [InlineKeyboardButton("Anuluj", callback_data="cancel")]
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
            context.user_data.pop("spring_number", None)
            context.user_data.pop("spring_shelf", None)
            await query.edit_message_text(
                f"✅ Sprężyna {number} została dodana na półkę {shelf.upper()}.\n\n"
                "Wprowadź kolejny numer sprężyny lub naciśnij 'Anuluj', aby wyjść.",
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
                await query.edit_message_text(f"🔁 Sprężyna {number} została przeniesiona na półkę {shelf.upper()}.")
                context.user_data.clear()
                return
        await query.edit_message_text("⚠️ Sprężyna nie znaleziona.")
        context.user_data.clear()
        return

# Główna funkcja uruchamiająca bota
def main():
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        logger.error("❌ BOT_TOKEN nie jest ustawiony!")
        return

    app = ApplicationBuilder().token(bot_token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_command))  # dodano komendę /add
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_input))
    app.add_handler(CallbackQueryHandler(callback_handler))

    logger.info("🤖 Bot uruchomiony. Oczekiwanie na komendy.")
    app.run_polling()

if __name__ == "__main__":
    main()
