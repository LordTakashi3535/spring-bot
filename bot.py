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

# НОВАЯ ФУНКЦИЯ: поиск всех пружин по номеру
def find_all_springs_by_number(data, number):
    """Находит ВСЕ пружины с заданным номером"""
    matches = []
    for i, row in enumerate(data):
        if str(row["Numer"]) == number:
            matches.append({
                'row_index': i + 2,  # +2 для строк Google Sheets (1-заголовок + 1-индексация)
                'shelf': row['Polka']
            })
    return matches

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
        "Или нажми кнопку dla добавления пружины:",
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
            matches = find_all_springs_by_number(data, number)
            if matches:
                deleted_count = 0
                for match in matches:
                    sheet.delete_rows(match['row_index'])
                    deleted_count += 1
                await update.message.reply_text(f"❌ Удалено {deleted_count} пружин с номером {number}.")
                await log_action(context, user.id, user.username, "delete_spring", f"Numer: {number}, Ilosc: {deleted_count}")
            else:
                await update.message.reply_text("⚠️ Sprężyna nie znaleziona.")

        elif text.startswith("="):
            content = text[1:].strip()
            number, new_shelf = [x.strip() for x in content.split(",")]
            matches = find_all_springs_by_number(data, number)
            if matches:
                updated_count = 0
                for match in matches:
                    sheet.update_cell(match['row_index'], 2, new_shelf)
                    updated_count += 1
                await update.message.reply_text(f"🔁 {updated_count} пружин {number} перемещено на {new_shelf}.")
                await log_action(context, user.id, user.username, "move_shelf", f"Numer: {number}, Nowa polka: {new_shelf}, Ilosc: {updated_count}")
            else:
                await update.message.reply_text("⚠️ Sprężyna nie znaleziona.")

        else:
            # 🔍 ПОИСК - НОВЫЙ КОД ДЛЯ ДУБЛИКАТОВ
            matches = find_all_springs_by_number(data, text)
            if matches:
                if len(matches) == 1:
                    # Одна пружина - как раньше
                    match = matches[0]
                    row = data[match['row_index'] - 2]
                    keyboard = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("Удалить", callback_data=f"delete:{text}"),
                            InlineKeyboardButton("Редактировать", callback_data=f"edit:{text}:{match['row_index']}")
                        ],
                        [InlineKeyboardButton("Отмена", callback_data="cancel")]
                    ])
                    response = f"🔍 Znaleziono:\nNumer: {row['Numer']}\nPółka: {row['Polka']}"
                else:
                    # Много пружин - показываем список
                    response = f"🔍 Znaleziono {len(matches)} пружин с номером {text}:\n\n"
                    for i, match in enumerate(matches, 1):
                        response += f"{i}. Полка {match['shelf']} (строка {match['row_index']})\n"
                    
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("Удалить все", callback_data=f"delete_all:{text}")],
                        [InlineKeyboardButton("Удалить одну", callback_data=f"delete_one:{text}")],
                        [InlineKeyboardButton("Редактировать", callback_data=f"edit_select:{text}")],
                        [InlineKeyboardButton("Отмена", callback_data="cancel")]
                    ])
                
                await update.message.reply_text(response, reply_markup=keyboard)
                context.user_data[f"search_results_{text}"] = matches  # Сохраняем для кнопок
                return
            await update.message.reply_text("⚠️ Sprężyna nie znaleziona.")

    except Exception as e:
        logger.error(f"Błąd przy przetwarzaniu komendy: {e}")
        await update.message.reply_text("❌ Błąd przetwarzania. Убедитесь, что формат команды правильный.")

# Обработка кнопок - ОБНОВЛЕННАЯ ВЕРСИЯ С ВЫБОРОМ ДЛЯ РЕДАКТИРОВАНИЯ
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
        await query.edit_message_text("Wpisz numer sprężyny или напиши 'Отмена' żeby выйти.", reply_markup=cancel_keyboard())
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
            f"Выбранная полка: {shelf.upper()}\n"
            "Нажми 'Potwierdź', чтобы добавить.",
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
                f"✅ Sprężyna {number} dodana на полку {shelf.upper()}.\n\n"
                "Введи следующий номер или нажми 'Отмена'.",
                reply_markup=cancel_keyboard()
            )
        else:
            await query.edit_message_text("Błąd: brak danych do dodania.")
        return

    # НОВЫЕ ОБРАБОТЧИКИ ДЛЯ ДУБЛИКАТОВ
    if data.startswith("delete_all:"):
        number = data.split(":", 1)[1]
        matches = context.user_data.get(f"search_results_{number}", [])
        deleted_count = 0
        for match in matches:
            sheet.delete_rows(match['row_index'])
            deleted_count += 1
        await log_action(context, user.id, user.username, "delete_all_springs", f"Numer: {number}, Ilosc: {deleted_count}")
        await query.edit_message_text(f"❌ Удалено {deleted_count} пружин с номером {number}.")
        context.user_data.pop(f"search_results_{number}", None)
        return

    if data.startswith("delete_one:"):
        number = data.split(":", 1)[1]
        matches = context.user_data.get(f"search_results_{number}", [])
        if matches:
            keyboard = []
            for match in matches:
                keyboard.append([InlineKeyboardButton(
                    f"Удалить с {match['shelf']} (стр.{match['row_index']})", 
                    callback_data=f"delete_specific:{number}:{match['row_index']}"
                )])
            keyboard.append([InlineKeyboardButton("Отмена", callback_data="cancel")])
            await query.edit_message_text(
                f"Выбери какую пружину {number} удалить:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        return

    if data.startswith("delete_specific:"):
        _, number, row_index = data.split(":", 2)
        sheet.delete_rows(int(row_index))
        await log_action(context, user.id, user.username, "delete_specific_spring", f"Numer: {number}, Rzad: {row_index}")
        await query.edit_message_text(f"❌ Пружина {number} со строки {row_index} удалена.")
        return

    # ✅ НОВОЕ: Выбор пружины для редактирования
    if data.startswith("edit_select:"):
        number = data.split(":", 1)[1]
        matches = context.user_data.get(f"search_results_{number}", [])
        if matches:
            keyboard = []
            for match in matches:
                keyboard.append([InlineKeyboardButton(
                    f"Редактировать {match['shelf']} (стр.{match['row_index']})", 
                    callback_data=f"edit:{number}:{match['row_index']}"
                )])
            keyboard.append([InlineKeyboardButton("Отмена", callback_data="cancel")])
            await query.edit_message_text(
                f"Выбери какую пружину {number} редактировать:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        return

    if data.startswith("delete:"):
        number = data.split(":", 1)[1]
        data_all = sheet.get_all_records()
        matches = find_all_springs_by_number(data_all, number)
        if matches:
            deleted_count = 0
            for match in matches:
                sheet.delete_rows(match['row_index'])
                deleted_count += 1
            await log_action(context, user.id, user.username, "delete_spring", f"Numer: {number}, Ilosc: {deleted_count}")
            await query.edit_message_text(f"❌ Удалено {deleted_count} пружин с номером {number}.")
        else:
            await query.edit_message_text("⚠️ Sprężyna nie znaleziona.")
        return

    # ✅ ОБНОВЛЕНО: edit теперь принимает номер строки
    if data.startswith("edit:"):
        parts = data.split(":")
        number = parts[1]
        row_index = parts[2] if len(parts) > 2 else None
        
        if row_index:
            # Редактирование конкретной пружины
            context.user_data["editing_spring"] = number
            context.user_data["editing_row"] = int(row_index)
            await query.edit_message_text(
                f"Выбери новую полку для пружины {number} (строка {row_index}):",
                reply_markup=shelves_keyboard()
            )
        else:
            # Fallback для старого формата (если нет row_index)
            data_all = sheet.get_all_records()
            matches = find_all_springs_by_number(data_all, number)
            if matches:
                first_match = matches[0]
                context.user_data["editing_spring"] = number
                context.user_data["editing_row"] = first_match['row_index']
                await query.edit_message_text(
                    f"Выбери новую полку для пружины {number} (строка {first_match['row_index']}):",
                    reply_markup=shelves_keyboard()
                )
            else:
                await query.edit_message_text("⚠️ Sprężyna nie znaleziona.")
        return

    if context.user_data.get("editing_spring") and data.startswith("move_shelf:"):
        shelf = data.split(":", 1)[1]
        number = context.user_data.get("editing_spring")
        row_index = context.user_data.get("editing_row")
        if row_index:
            sheet.update_cell(row_index, 2, shelf)
            await log_action(context, user.id, user.username, "move_spring", f"Numer: {number}, Nowa polka: {shelf}, Rzad: {row_index}")
            await query.edit_message_text(f"🔁 Пружина {number} перемещена на полку {shelf.upper()} (строка {row_index}).")
            context.user_data.clear()
        else:
            await query.edit_message_text("⚠️ Ошибка редактирования.")
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
