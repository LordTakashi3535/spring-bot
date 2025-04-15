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
        "Привет! Используй команды:\n"
        "+номер, полка — добавить пружину\n"
        "-номер — удалить пружину\n"
        "=номер, новая_полка — изменить полку\n"
        "номер — узнать где находится пружина"
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
            await update.message.reply_text(f"✅ Пружина {number} добавлена на полку {shelf}.")

        elif text.startswith("-"):
            # Удаление пружины
            number = text[1:].strip()
            for idx, row in enumerate(data, start=2):
                if str(row["Numer"]) == number:
                    sheet.delete_rows(idx)
                    await update.message.reply_text(f"❌ Пружина {number} удалена.")
                    return
            await update.message.reply_text("⚠️ Пружина не найдена.")

        elif text.startswith("="):
            # Изменение полки
            content = text[1:].strip()
            number, new_shelf = [x.strip() for x in content.split(",")]
            for idx, row in enumerate(data, start=2):
                if str(row["Numer"]) == number:
                    sheet.update_cell(idx, 2, new_shelf)
                    await update.message.reply_text(f"🔁 Полка для пружины {number} обновлена на {new_shelf}.")
                    return
            await update.message.reply_text("⚠️ Пружина не найдена.")

        else:
            # Поиск пружины
            for row in data:
                if str(row["Numer"]) == text:
                    response = f"🔍 Найдено:\nNumer: {row['Numer']}\nPolka: {row['Polka']}"
                    await update.message.reply_text(response)
                    return
            await update.message.reply_text("⚠️ Пружина не найдена.")

    except Exception as e:
        logging.error(f"Ошибка при обработке команды: {e}")
        await update.message.reply_text("❌ Ошибка обработки. Убедись, что формат команды верный.")

# Запуск через polling
def main():
    bot_token = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(bot_token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_input))

    app.run_polling()

if __name__ == "__main__":
    main()
