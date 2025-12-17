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
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Декодируем credentials
encoded_creds = os.environ["GOOGLE_CREDENTIALS_B64"]
decoded_creds = base64.b64decode(encoded_creds).decode("utf-8")
service_account_info = json.loads(decoded_creds)

# Авторизация
creds = Credentials.from_service_account_info(service_account_info, scopes=scope)
client = gspread.authorize(creds)

# Таблицы
spreadsheet = client.open_by_url(
    "https://docs.google.com/spreadsheets/d/1-PYvDusEahk2EYI2f4kDtu4uQ-pV756kz6fb_RXn-s8"
)
sheet = spreadsheet.sheet1
logs_sheet = spreadsheet.worksheet("Logs")

# Инициализация структуры
def init_sheet():
    try:
        sheet.update('A1', 'Номер')
        sheet.update('B1', 'Полка')
        sheet.update('C1', 'Дата добавления')
        sheet.update('D1', 'Последнее действие')
    except:
        pass

init_sheet()

# Русские названия действий
ACTION_RU = {
    "add_spring": "➕ добавление",
    "delete_spring": "🗑️ удаление",
    "move_spring": "🔄 перемещение",
    "search": "🔍 поиск",
    "delete_all_springs": "🗑️ удалить все",
    "delete_specific_spring": "🗑️ удалить одну"
}

def format_date(date_str):
    """Форматирует дату ДД.ММ.ГГГГ"""
    if not date_str or date_str == '':
        return '❓ нет даты'
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
        return dt.strftime("%d.%m.%Y %H:%M")
    except:
        try:
            return date_str[:10]
        except:
            return '❓ нет даты'

# Запись лога
async def log_action(context, user_id, username, action_type, details="", spring_number=None):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    username = username or "пользователь"
    log_entry = f"{ACTION_RU.get(action_type, action_type)}: {details}"
    row = [timestamp, user_id, username, log_entry, spring_number or ""]
    
    try:
        logs_sheet.append_row(row)
        if spring_number:
            update_last_action(spring_number, f"{ACTION_RU.get(action_type, action_type)} ({username})")
    except Exception as e:
        logger.error(f"Ошибка лога: {e}")

def update_last_action(spring_number, action_text):
    """Обновляет колонку D"""
    data = sheet.get_all_records()
    for i, row in enumerate(data):
        if str(row.get("Номер", "")) == spring_number:
            row_index = i + 2
            if not sheet.cell(row_index, 3).value:
                sheet.update_cell(row_index, 3, datetime.now().strftime("%Y-%m-%d %H:%M"))
            sheet.update_cell(row_index, 4, action_text)
            break

def find_all_springs_by_number(data, number):
    """Находит все пружины по номеру"""
    matches = []
    for i, row in enumerate(data):
        if str(row.get("Номер", "")) == number:
            matches.append({
                'row_index': i + 2,
                'shelf': row.get('Полка', '❓'),
                'add_date': format_date(row.get('Дата добавления', '')),
                'last_action': row.get('Последнее действие', '❓')
            })
    return matches

# Клавиатура полок
def shelves_keyboard(number):
    keyboard = [
        [InlineKeyboardButton("A1", callback_data=f"add_confirm:{number}:a1"), InlineKeyboardButton("B1", callback_data=f"add_confirm:{number}:b1"), InlineKeyboardButton("C1", callback_data=f"add_confirm:{number}:c1")],
        [InlineKeyboardButton("A2", callback_data=f"add_confirm:{number}:a2"), InlineKeyboardButton("B2", callback_data=f"add_confirm:{number}:b2"), InlineKeyboardButton("C2", callback_data=f"add_confirm:{number}:c2")],
        [InlineKeyboardButton("A3", callback_data=f"add_confirm:{number}:a3"), InlineKeyboardButton("B3", callback_data=f"add_confirm:{number}:b3"), InlineKeyboardButton("C3", callback_data=f"add_confirm:{number}:c3")],
        [InlineKeyboardButton("A4", callback_data=f"add_confirm:{number}:a4"), InlineKeyboardButton("B4", callback_data=f"add_confirm:{number}:b4")],
        [InlineKeyboardButton("A5", callback_data=f"add_confirm:{number}:a5"), InlineKeyboardButton("B5", callback_data=f"add_confirm:{number}:b5")],
        [InlineKeyboardButton("A6", callback_data=f"add_confirm:{number}:a6"), InlineKeyboardButton("B6", callback_data=f"add_confirm:{number}:b6")],
        [InlineKeyboardButton("A7", callback_data=f"add_confirm:{number}:a7"), InlineKeyboardButton("B7", callback_data=f"add_confirm:{number}:b7")],
        [InlineKeyboardButton("", callback_data="noop"), InlineKeyboardButton("B8", callback_data=f"add_confirm:{number}:b8")],
        [InlineKeyboardButton("❌ Выход", callback_data="exit_add_mode")]
    ]
    return InlineKeyboardMarkup(keyboard)

def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить пружину", callback_data="add_spring")],
        [InlineKeyboardButton("📊 Все пружины", callback_data="show_all")],
        [InlineKeyboardButton("🔍 Поиск", callback_data="quick_search")]
    ])

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 <b>Склад пружин</b>\n\n"
        "📋 <b>Быстрые команды:</b>\n"
        "• <code>+123, A1</code> — добавить\n"
        "• <code>-123</code> — удалить все\n"
        "• <code>=123, B2</code> — переместить\n"
        "• <code>123</code> — найти\n\n"
        "🎮 Используй кнопки ниже!",
        reply_markup=main_menu_keyboard(),
        parse_mode='HTML'
    )

# Обработка текста
async def handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user = update.effective_user
    data = sheet.get_all_records()

    # Режим массового добавления - ЖДЕТ НОМЕР
    if context.user_data.get("add_mode"):
        if text.lower() in ["выход", "отмена", "exit"]:
            context.user_data.clear()
            await update.message.reply_text("✅ Режим добавления завершён.", reply_markup=main_menu_keyboard())
            return
        
        # Пользователь написал НОМЕР - показываем полки
        context.user_data["current_number"] = text
        await update.message.reply_text(
            f"✅ <b>Номер:</b> <code>{text}</code>\n\n"
            "📍 <b>Выбери полку:</b>",
            reply_markup=shelves_keyboard(text),
            parse_mode='HTML'
        )
        return

    # Обычные команды
    try:
        if text.startswith("+"):
            content = text[1:].strip()
            number, shelf = [x.strip() for x in content.split(",")]
            sheet.append_row([number, shelf, "", ""])
            await update.message.reply_text(
                f"🎉 <b>{number}</b> добавлена на <b>{shelf}</b>!",
                reply_markup=main_menu_keyboard(),
                parse_mode='HTML'
            )
            await log_action(context, user.id, user.username, "add_spring", f"Полка: {shelf}", number)

        elif text.startswith("-"):
            number = text[1:].strip()
            matches = find_all_springs_by_number(data, number)
            if matches:
                for match in matches:
                    sheet.delete_rows(match['row_index'])
                await update.message.reply_text(
                    f"🗑️ <b>Удалено {len(matches)} пружин</b> <code>{number}</code>",
                    reply_markup=main_menu_keyboard(),
                    parse_mode='HTML'
                )
                await log_action(context, user.id, user.username, "delete_spring", f"Количество: {len(matches)}", number)
            else:
                await update.message.reply_text("⚠️ Пружина не найдена.", reply_markup=main_menu_keyboard())

        elif text.startswith("="):
            content = text[1:].strip()
            number, new_shelf = [x.strip() for x in content.split(",")]
            matches = find_all_springs_by_number(data, number)
            if matches:
                for match in matches:
                    sheet.update_cell(match['row_index'], 2, new_shelf)
                await update.message.reply_text(
                    f"🔄 <b>{len(matches)} пружин</b> <code>{number}</code> → <b>{new_shelf}</b>",
                    reply_markup=main_menu_keyboard(),
                    parse_mode='HTML'
                )
                await log_action(context, user.id, user.username, "move_spring", f"Полка: {new_shelf}", number)
            else:
                await update.message.reply_text("⚠️ Пружина не найдена.", reply_markup=main_menu_keyboard())

        else:
            matches = find_all_springs_by_number(data, text)
            if matches:
                if len(matches) == 1:
                    match = matches[0]
                    response = (
                        f"🔍 <b>Пружина {text}</b> (стр. {match['row_index']})\n\n"
                        f"📍 <b>Полка:</b> {match['shelf']}\n"
                        f"📅 <b>Добавлена:</b> {match['add_date']}\n"
                        f"🔍 <b>Последнее:</b> {match['last_action']}"
                    )
                    keyboard = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("🗑️ Удалить", callback_data=f"delete:{text}"),
                            InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit:{text}:{match['row_index']}")
                        ],
                        [InlineKeyboardButton("🏠 Меню", callback_data="main_menu")]
                    ])
                else:
                    response = f"🔍 <b>Найдено {len(matches)} пружин {text}:</b>\n\n"
                    for i, match in enumerate(matches, 1):
                        response += f"{i}. {match['shelf']} • {match['add_date']}\n"
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("🗑️ Удалить все", callback_data=f"delete_all:{text}")],
                        [InlineKeyboardButton("🗑️ Удалить одну", callback_data=f"delete_one:{text}")],
                        [InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_select:{text}")],
                        [InlineKeyboardButton("🏠 Меню", callback_data="main_menu")]
                    ])
                
                await update.message.reply_text(response, reply_markup=keyboard, parse_mode='HTML')
                context.user_data[f"search_results_{text}"] = matches
                await log_action(context, user.id, user.username, "search", f"Найдено: {len(matches)}", text)
            else:
                await update.message.reply_text("⚠️ Пружина не найдена.", reply_markup=main_menu_keyboard())

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await update.message.reply_text("❌ Ошибка. Проверь формат: <code>+123, A1</code>", parse_mode='HTML')

# Обработка кнопок
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = update.effective_user

    if data == "main_menu":
        await query.edit_message_text("🤖 <b>Главное меню</b>", reply_markup=main_menu_keyboard(), parse_mode='HTML')
        context.user_data.clear()
        return

    if data == "exit_add_mode":
        context.user_data.clear()
        await query.edit_message_text("✅ Режим добавления завершён.", reply_markup=main_menu_keyboard())
        return

    if data == "add_spring":
        context.user_data.clear()
        context.user_data["add_mode"] = True
        await query.edit_message_text(
            "➕ <b>Режим массового добавления</b>\n\n"
            "📝 Пиши номера пружин по очереди\n"
            "❌ <code>выход</code> - завершить\n\n"
            "Пример: <code>123</code> → выбери полку → <code>456</code> → полка...",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Выход", callback_data="exit_add_mode")]]),
            parse_mode='HTML'
        )
        return

    # ✅ ИДЕАЛЬНОЕ МАССОВОЕ ДОБАВЛЕНИЕ
    if data.startswith("add_confirm:"):
        parts = data.split(":", 2)
        number = parts[1]
        shelf_code = parts[2]
        shelf = shelf_code.upper()
        
        sheet.append_row([number, shelf, "", ""])
        await log_action(context, user.id, user.username, "add_spring", f"Полка: {shelf}", number)
        
        await query.edit_message_text(
            f"🎉 <b>{number}</b> добавлена на <b>{shelf}</b>!\n\n"
            "📝 Пиши следующий номер пружины или <code>выход</code>:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Выход", callback_data="exit_add_mode")]]),
            parse_mode='HTML'
        )
        return

    if data == "show_all":
        data_all = sheet.get_all_records()
        if len(data_all) <= 1:
            await query.edit_message_text("📭 Склад пуст.", reply_markup=main_menu_keyboard())
            return
        summary = f"📊 <b>Всего: {len(data_all)-1} пружин</b>\n\n"
        for row in data_all[1:6]:
            summary += f"• <code>{row.get('Номер', '?')}</code> → {row.get('Полка', '?')}\n"
        if len(data_all) > 6:
            summary += f"\n... и ещё {len(data_all)-6}"
        await query.edit_message_text(summary, reply_markup=main_menu_keyboard(), parse_mode='HTML')
        return

    if data == "quick_search":
        await query.edit_message_text("🔍 <b>Поиск</b>\n\nНапиши номер пружины в чат!", reply_markup=main_menu_keyboard(), parse_mode='HTML')
        return

    # Остальные обработчики (удаление, редактирование)
    if data.startswith("delete_all:"):
        number = data.split(":", 1)[1]
        matches = context.user_data.get(f"search_results_{number}", [])
        for match in matches:
            sheet.delete_rows(match['row_index'])
        await log_action(context, user.id, user.username, "delete_all_springs", f"Количество: {len(matches)}", number)
        await query.edit_message_text(f"🗑️ <b>Удалено {len(matches)} пружин</b> {number}", reply_markup=main_menu_keyboard(), parse_mode='HTML')
        return

    if data.startswith("delete_one:"):
        number = data.split(":", 1)[1]
        matches = context.user_data.get(f"search_results_{number}", [])
        keyboard = []
        for match in matches:
            keyboard.append([InlineKeyboardButton(
                f"🗑️ {match['shelf']} (стр.{match['row_index']})",
                callback_data=f"delete_specific:{number}:{match['row_index']}"
            )])
        keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="main_menu")])
        await query.edit_message_text(f"🗑️ <b>Выбери какую удалить:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        return

    if data.startswith("delete_specific:"):
        _, number, row_index = data.split(":", 2)
        sheet.delete_rows(int(row_index))
        await log_action(context, user.id, user.username, "delete_specific_spring", f"Строка: {row_index}", number)
        await query.edit_message_text(f"🗑️ Пружина {number} (стр.{row_index}) удалена.", reply_markup=main_menu_keyboard())
        return

    if data.startswith("edit_select:"):
        number = data.split(":", 1)[1]
        matches = context.user_data.get(f"search_results_{number}", [])
        keyboard = []
        for match in matches:
            keyboard.append([InlineKeyboardButton(
                f"✏️ {match['shelf']} (стр.{match['row_index']})",
                callback_data=f"edit:{number}:{match['row_index']}"
            )])
        keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="main_menu")])
        await query.edit_message_text(f"✏️ <b>Выбери для редактирования:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        return

    if data.startswith("edit:"):
        parts = data.split(":")
        number, row_index = parts[1], parts[2]
        context.user_data["editing_spring"] = number
        context.user_data["editing_row"] = int(row_index)
        await query.edit_message_text(
            f"✏️ <b>Пружина {number}</b> (стр. {row_index})\n\n📍 <b>Выбери новую полку:</b>",
            reply_markup=shelves_keyboard(number),
            parse_mode='HTML'
        )
        return

    if data.startswith("add_confirm:") or (context.user_data.get("editing_spring") and data.startswith("add_confirm:")):
        parts = data.split(":", 2)
        number = parts[1]
        shelf_code = parts[2]
        shelf = shelf_code.upper()
        
        if context.user_data.get("editing_spring") and context.user_data.get("editing_row"):
            # Редактирование
            row_index = context.user_data["editing_row"]
            sheet.update_cell(row_index, 2, shelf)
            await log_action(context, user.id, user.username, "move_spring", f"Полка: {shelf}", number)
            await query.edit_message_text(
                f"🔄 <b>{number}</b> перемещена на <b>{shelf}</b>!",
                reply_markup=main_menu_keyboard(),
                parse_mode='HTML'
            )
            context.user_data.clear()
        else:
            # Добавление
            sheet.append_row([number, shelf, "", ""])
            await log_action(context, user.id, user.username, "add_spring", f"Полка: {shelf}", number)
            await query.edit_message_text(
                f"🎉 <b>{number}</b> добавлена на <b>{shelf}</b>!\n\n"
                "📝 Пиши следующий номер пружины:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Выход", callback_data="exit_add_mode")]]),
                parse_mode='HTML'
            )
        return

# Запуск
def main():
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        logger.error("❌ BOT_TOKEN не установлен!")
        return

    app = ApplicationBuilder().token(bot_token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_input))
    app.add_handler(CallbackQueryHandler(callback_handler))

    logger.info("🤖 Бот склада пружин запущен! 🚀")
    app.run_polling()

if __name__ == "__main__":
    main()
