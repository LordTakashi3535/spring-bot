import logging
import os
import json
import gspread
import asyncio
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
    await update.message.reply_text("Привет! Введи номер пружины, и я покажу на какой она полке.")

# Поиск пружины
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    data = sheet.get_all_records()

    for row in data:
        if str(row["Numer"]) == query:
            response = f"Numer: {row['Numer']}\nPolka: {row['Polka']}"
            await update.message.reply_text(response)
            return

    await update.message.reply_text("Пружина не найдена.")

# Запуск через вебхук (для Render)
async def main():
    bot_token = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(bot_token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))

    # Настройка вебхука
    webhook_url = "https://spring-bot-pvta.onrender.com"

    # Устанавливаем вебхук
    await app.bot.set_webhook(webhook_url)

    # Запуск бота
    await app.run_webhook(listen="0.0.0.0", port=10000, webhook_url=webhook_url)

if __name__ == "__main__":
    asyncio.run(main())
4. Проверка на платформе Render
Если вы развертываете бота на платформе типа Render или другом хостинге, важно убедиться, что:

Платформа правильно обрабатывает входящие HTTP-запросы на нужный порт.

Ваш бот имеет доступ к интернету и может связываться с API Telegram.

5. Тестирование через polling
Если с вебхуком возникают проблемы, можно попробовать временно использовать polling для диагностики:

python
Копировать
Редактировать
await app.start_polling()
Это позволит вам проверить, работает ли бот вообще, без необходимости настраивать вебхук. Если с polling всё работает, это подтвердит, что проблема в настройках вебхука.

Дополнительные проверки:
Убедитесь, что переменная окружения GOOGLE_CREDENTIALS_B64 установлена правильно.

Проверьте, что ваш токен Telegram (BOT_TOKEN) указан корректно и не изменился.

Попробуйте эти изменения и проверьте логи для получения дополнительной информации, если что-то не будет работать.







Вы сказали:
перед этим мы делали polling и все работали затем ты сказал что нужно сделать backgraund worker и все перестало работать


ChatGPT сказал:
Понял, если раньше с использованием polling всё работало, а после попытки использования background worker возникли проблемы, вероятно, возникло недоразумение в том, как были объединены разные части кода для обработки запросов.

Давайте попробуем вернуться к polling и убедимся, что всё снова заработает корректно, а затем обсудим, что не так с background worker.

Версия с polling
Если раньше использовался polling и всё работало, то давайте вернемся к нему. Вот обновлённая версия кода, которая должна работать с polling (без вебхуков и background worker):

python
Копировать
Редактировать
import logging
import os
import json
import gspread
import asyncio
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
    await update.message.reply_text("Привет! Введи номер пружины, и я покажу на какой она полке.")

# Поиск пружины
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    data = sheet.get_all_records()

    for row in data:
        if str(row["Numer"]) == query:
            response = f"Numer: {row['Numer']}\nPolka: {row['Polka']}"
            await update.message.reply_text(response)
            return

    await update.message.reply_text("Пружина не найдена.")

# Запуск через polling
async def main():
    bot_token = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(bot_token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))

    # Запуск бота с polling
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
