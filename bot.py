import logging
import os
import json
import gspread
import base64

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
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
    await update.message.reply_text(
        "Cześć! Użyj komend:\n"
        "+numer, półka — dodaj sprężynę\n"
        "-numer — usuń sprężynę\n"
        "=numer, nowa_półka — zmień półkę\n"
        "numer — sprawdź gdzie znajduje się sprężyna"
    )

# Обработка пользовательского ввода
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
            # Изменение полки
            content = text[1:].strip()
            number, new_shelf = [x.strip() for x in content.split(",")]
            for idx, row in enumerate(data, start=2):
                if str(row["Numer"]) == number:
                    sheet.update_cell(idx, 2, new_shelf)
                    await update.message.reply_text(f"🔁 Półka dla sprężyny {number} została zmieniona na {new_shelf}.")
                    return
            await update.message.reply_text("⚠️ Sprężyna nie znaleziona.")

        else:
            # Поиск пружины
            for row in data:
                if str(row["Numer"]) == text:
                    response = f"🔍 Znaleziono:\nNumer: {row['Numer']}\nPółka: {row['Polka']}"
                    await update.message.reply_text(response)
                    return
            await update.message.reply_text("⚠️ Sprężyna nie znaleziona.")

    except Exception as e:
        logging.error(f"Błąd przy przetwarzaniu komendy: {e}")
        await update.message.reply_text("❌ Błąd przetwarzania. Upewnij się, że format komendy jest poprawny.")

# Запуск через polling
def main():
    bot_token = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(bot_token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_input))

    app.run_polling()

if __name__ == "__main__":
    main()
