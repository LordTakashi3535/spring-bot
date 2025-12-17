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
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
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
        sheet.update('A1', [['Номер', 'Полка', 'Дата добавления']])
    except:
        pass

init_sheet()

def format_date(date_str):
    """Форматирует дату ДД.ММ.ГГГГ ЧЧ:ММ"""
    if not date_str or date_str == '':
        return '❓ нет даты'
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
        return dt.strftime("%d.%m.%Y %H:%M")
    except:
        try:
            return date_str[:16]
        except:
            return '❓ нет даты'

def find_all_springs_by_number(number):
    """Находит все пружины по номеру"""
    matches = []
    all_values = sheet.get_all_values()
    for i, row in enumerate(all_values[1:], 1):
        if row and len(row) > 0 and str(row[0]).strip() == number.strip():
            matches.append({
                'row_index': i + 1,
                'shelf': row[1] if len(row) > 1 else '❓',
                'add_date': format_date(row[2] if len(row) > 2 else ''),
                'number': number
            })
    return matches

def find_logs_by_number(number):
    """Находит все логи по номеру пружины"""
    logs = []
    all_logs = logs_sheet.get_all_values()
    for i, row in enumerate(all_logs[1:], 1):
        if row and len(row) >= 5 and str(row[4]).strip() == number.strip():
            logs.append({
                'timestamp': row[0],
                'user_id': row[1],
                'username': row[2],
                'action': row[3],
                'number': row[4]
            })
    return sorted(logs, key=lambda x: x['timestamp'], reverse=True)

def find_last_added_row():
    """Возвращает номер последней строки с пружиной"""
    all_values = sheet.get_all_values()
    for i in range(len(all_values)-1, 0, -1):
        if all_values[i] and len(all_values[i]) > 0 and all_values[i][0]:
            return i + 1
    return 1

def shelves_keyboard(number):
    keyboard = [
        [InlineKeyboardButton("A1", callback_data=f"add_confirm:{number}:a1"), 
         InlineKeyboardButton("B1", callback_data=f"add_confirm:{number}:b1"), 
         InlineKeyboardButton("C1", callback_data=f"add_confirm:{number}:c1")],
        [InlineKeyboardButton("A2", callback_data=f"add_confirm:{number}:a2"), 
         InlineKeyboardButton("B2", callback_data=f"add_confirm:{number}:b2"), 
         InlineKeyboardButton("C2", callback_data=f"add_confirm:{number}:c2")],
        [InlineKeyboardButton("A3", callback_data=f"add_confirm:{number}:a3"), 
         InlineKeyboardButton("B3", callback_data=f"add_confirm:{number}:b3"), 
         InlineKeyboardButton("C3", callback_data=f"add_confirm:{number}:c3")],
        [InlineKeyboardButton("A4", callback_data=f"add_confirm:{number}:a4"), 
         InlineKeyboardButton("B4", callback_data=f"add_confirm:{number}:b4")],
        [InlineKeyboardButton("A5", callback_data=f"add_confirm:{number}:a5"), 
         InlineKeyboardButton("B5", callback_data=f"add_confirm:{number}:b5")],
        [InlineKeyboardButton("A6", callback_data=f"add_confirm:{number}:a6"), 
         InlineKeyboardButton("B6", callback_data=f"add_confirm:{number}:b6")],
        [InlineKeyboardButton("A7", callback_data=f"add_confirm:{number}:a7"), 
         InlineKeyboardButton("B7", callback_data=f"add_confirm:{number}:b7")],
        [InlineKeyboardButton("", callback_data="noop"), 
         InlineKeyboardButton("B8", callback_data=f"add_confirm:{number}:b8")]
    ]
    return InlineKeyboardMarkup(keyboard)

def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить пружину", callback_data="add_spring")],
        [InlineKeyboardButton("📋 Логи", callback_data="logs_mode")]
    ])

def saved_keyboard(number):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑️ Удалить эту", callback_data=f"delete_last:{number}")],
        [InlineKeyboardButton("✅ Готово", callback_data="exit_add_mode")]
    ])

async def log_action(context, user_id, username, action_type, details="", spring_number=None):
    """Логирование с правильным форматом удаления"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    username = username or "пользователь"
    
    if "удал" in action_type.lower():
        log_entry = f"{action_type}: Полка: {details}"
    else:
        log_entry = f"{action_type}: {details}"
    
    row = [timestamp, user_id, username, log_entry, spring_number or ""]
    
    try:
        logs_sheet.append_row(row)
    except Exception as e:
        logger.error(f"Ошибка лога: {e}")

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user = update.effective_user
    
    if context.user_data.get("add_mode"):
        context.user_data["current_number"] = text
        await update.message.reply_text(
            f"✅ <b>Номер:</b> <code>{text}</code>\n\n"
            "📍 <b>Выбери полку:</b>",
            reply_markup=shelves_keyboard(text),
            parse_mode='HTML'
        )
        return
    
    if context.user_data.get("logs_mode"):
        logs = find_logs_by_number(text)
        if logs:
            response = f"📋 <b>История <code>{text}</code> ({len(logs)} действий):</b>\n\n"
            for i, log in enumerate(logs[:10], 1):
                timestamp = log['timestamp'][:16]
                response += f"{i}. {timestamp} | <code>{log['username']}</code>\n"
                response += f"   {log['action']}\n\n"
            
            if len(logs) > 10:
                response += f"... и ещё {len(logs)-10} действий"
        else:
            response = f"⚠️ Логов для <code>{text}</code> не найдено."
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Меню", callback_data="main_menu")]
        ])
        
        await update.message.reply_text(response, reply_markup=keyboard, parse_mode='HTML')
        context.user_data.clear()
        return

    try:
        if text.startswith("+"):
            content = text[1:].strip()
            number, shelf = [x.strip() for x in content.split(",")]
            sheet.append_row([number, shelf, datetime.now().strftime("%Y-%m-%d %H:%M")])
            await log_action(context, user.id, user.username, "➕ добавление", f"Полка: {shelf}", number)
            await update.message.reply_text(
                f"🎉 <b>{number}</b> добавлена на <b>{shelf}</b>!",
                reply_markup=main_menu_keyboard(),
                parse_mode='HTML'
            )
            return

        elif text.startswith("-"):
            number = text[1:].strip()
            matches = find_all_springs_by_number(number)
            if matches:
                for match in matches:
                    sheet.delete_rows(match['row_index'])
                await update.message.reply_text(
                    f"🗑️ <b>Удалено {len(matches)} пружин</b> <code>{number}</code>",
                    reply_markup=main_menu_keyboard(),
                    parse_mode='HTML'
                )
                await log_action(context, user.id, user.username, "🗑️ удаление", f"{len(matches)} шт", number)
            else:
                await update.message.reply_text("⚠️ Пружина не найдена.", reply_markup=main_menu_keyboard())
            return

        elif text.startswith("="):
            content = text[1:].strip()
            number, new_shelf = [x.strip() for x in content.split(",")]
            matches = find_all_springs_by_number(number)
            if matches:
                for match in matches:
                    sheet.update_cell(match['row_index'], 2, new_shelf)
                await update.message.reply_text(
                    f"🔄 <b>{len(matches)} пружин</b> <code>{number}</code> → <b>{new_shelf}</b>",
                    reply_markup=main_menu_keyboard(),
                    parse_mode='HTML'
                )
                await log_action(context, user.id, user.username, "🔄 перемещение", f"Полка: {new_shelf}", number)
            else:
                await update.message.reply_text("⚠️ Пружина не найдена.", reply_markup=main_menu_keyboard())
            return

        else:
            matches = find_all_springs_by_number(text)
            if matches:
                if len(matches) == 1:
                    match = matches[0]
                    response = (
                        f"🔍 <b>Пружина <code>{text}</code></b> (стр. {match['row_index']})\n\n"
                        f"📍 <b>Полка:</b> <b>{match['shelf']}</b>\n"
                        f"📅 <b>Добавлена:</b> {match['add_date']}"
                    )
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("🗑️ Удалить", callback_data=f"delete_select:{text}")],
                        [InlineKeyboardButton("🔄 Переместить", callback_data=f"move_select:{text}")],
                        [InlineKeyboardButton("🏠 Меню", callback_data="main_menu")]
                    ])
                else:
                    response = f"🔍 <b>Найдено <code>{len(matches)}</code> пружин <code>{text}</code>:</b>\n\n"
                    for i, match in enumerate(matches, 1):
                        response += (
                            f"{i}. <b>стр.{match['row_index']} {match['shelf']}</b>\n"
                            f"   📅 {match['add_date']}\n\n"
                        )
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("🗑️ Удалить", callback_data=f"delete_select:{text}")],
                        [InlineKeyboardButton("🔄 Переместить", callback_data=f"move_select:{text}")],
                        [InlineKeyboardButton("🏠 Меню", callback_data="main_menu")]
                    ])
                
                await update.message.reply_text(response, reply_markup=keyboard, parse_mode='HTML')
            else:
                await update.message.reply_text("⚠️ Пружина не найдена.", reply_markup=main_menu_keyboard())

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await update.message.reply_text("❌ Ошибка. Проверь формат: <code>+123, A1</code>", parse_mode='HTML')

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

    if data == "logs_mode":
        context.user_data.clear()
        context.user_data["logs_mode"] = True
        await query.edit_message_text(
            "📋 <b>Режим логов</b>\n\n"
            "📝 Впиши номер пружины для просмотра истории:\n\n"
            "Пример: <code>123</code>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Меню", callback_data="main_menu")]]),
            parse_mode='HTML'
        )
        return

    if data == "add_spring":
        context.user_data.clear()
        context.user_data["add_mode"] = True
        await query.edit_message_text(
            "➕ <b>Режим массового добавления</b>\n\n"
            "📝 Пиши номера пружин по очереди\n"
            "❌ <code>выход</code> - завершить\n\n"
            "Пример: <code>123</code> → полка → <code>456</code> → полка...",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Выход", callback_data="exit_add_mode")]]),
            parse_mode='HTML'
        )
        return

    if data.startswith("add_confirm:"):
        parts = data.split(":", 2)
        number = parts[1]
        shelf_code = parts[2]
        shelf = shelf_code.upper()
        
        sheet.append_row([number, shelf, datetime.now().strftime("%Y-%m-%d %H:%M")])
        row_index = find_last_added_row()
        
        await log_action(context, user.id, user.username, "➕ добавление", f"Полка: {shelf}", number)
        
        await query.edit_message_text(
            f"✅ <b>{number}</b> сохранена на <b>{shelf}</b> (стр. {row_index})!\n\n"
            f"📝 Пиши следующий номер пружины:",
            reply_markup=saved_keyboard(number),
            parse_mode='HTML'
        )
        return

    if data.startswith("delete_last:"):
        number = data.split(":", 1)[1]
        matches = find_all_springs_by_number(number)
        if matches:
            last_match = matches[-1]
            row_index = last_match['row_index']
            shelf = last_match['shelf']
            sheet.delete_rows(row_index)
            await log_action(context, user.id, user.username, "🗑️ удаление", f"Полка: {shelf}", number)
            await query.edit_message_text(
                f"🗑️ <b>{number}</b> (стр. {row_index}) удалена!\n\n"
                f"📝 Пиши следующий номер:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Выход", callback_data="exit_add_mode")]]),
                parse_mode='HTML'
            )
        return

    # ✅ Выбор строки для УДАЛЕНИЯ
    if data.startswith("delete_select:"):
        number = data.split(":", 1)[1]
        matches = find_all_springs_by_number(number)
        if matches:
            await query.edit_message_text(
                f"🗑️ <b>Выбери строку для удаления <code>{number}</code>:</b>",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"🗑️ стр.{m['row_index']} {m['shelf']}", 
                                        callback_data=f"del_select:{m['row_index']}:{number}:{m['shelf']}")] for m in matches[:8]
                ] + [[InlineKeyboardButton("🏠 Меню", callback_data="main_menu")]]),
                parse_mode='HTML'
            )
        return

    # ✅ НОВОЕ: Выбор строки для ПЕРЕМЕЩЕНИЯ
    if data.startswith("move_select:"):
        number = data.split(":", 1)[1]
        matches = find_all_springs_by_number(number)
        if matches:
            await query.edit_message_text(
                f"🔄 <b>Выбери строку для перемещения <code>{number}</code>:</b>",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"🔄 стр.{m['row_index']} {m['shelf']} →", 
                                        callback_data=f"move_row:{m['row_index']}:{number}:{m['shelf']}")] for m in matches[:8]
                ] + [[InlineKeyboardButton("🏠 Меню", callback_data="main_menu")]]),
                parse_mode='HTML'
            )
        return

    # ✅ Удаление конкретной строки
    if data.startswith("del_select:"):
        parts = data.split(":", 3)
        row_index = int(parts[1])
        number = parts[2]
        shelf = parts[3] if len(parts) > 3 else "❓"
        
        try:
            sheet.delete_rows(row_index)
            await log_action(context, user.id, user.username, "🗑️ удаление", f"Полка: {shelf}", number)
            await query.edit_message_text(
                f"✅ <b>{number}</b> (стр. {row_index}, {shelf}) удалена!",
                reply_markup=main_menu_keyboard(),
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Ошибка удаления строки {row_index}: {e}")
            await query.edit_message_text("⚠️ Ошибка удаления.", reply_markup=main_menu_keyboard())
        return

    # ✅ НОВОЕ: Выбор новой полки для перемещения
    if data.startswith("move_row:"):
        parts = data.split(":", 3)
        row_index = int(parts[1])
        number = parts[2]
        old_shelf = parts[3]
        
        context.user_data["move_row_index"] = row_index
        context.user_data["move_number"] = number
        context.user_data["move_old_shelf"] = old_shelf
        
        await query.edit_message_text(
            f"🔄 <b>{number}</b> (стр. {row_index}, {old_shelf}) → <b>выбери новую полку:</b>",
            reply_markup=shelves_keyboard(f"move:{number}"),
            parse_mode='HTML'
        )
        return

    # ✅ Подтверждение перемещения
    if data.startswith("add_confirm:") and context.user_data.get("move_row_index"):
        parts = data.split(":", 2)
        number = parts[1]
        shelf_code = parts[2]
        shelf = shelf_code.upper()
        
        row_index = context.user_data["move_row_index"]
        old_shelf = context.user_data["move_old_shelf"]
        
        sheet.update_cell(row_index, 2, shelf)
        await log_action(context, user.id, user.username, "🔄 перемещение", f"Полка: {old_shelf} → {shelf}", number)
        
        await query.edit_message_text(
            f"✅ <b>{number}</b> перемещена!\n"
            f"📍 {old_shelf} → <b>{shelf}</b> (стр. {row_index})",
            reply_markup=main_menu_keyboard(),
            parse_mode='HTML'
        )
        context.user_data.clear()
        return

def main():
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        logger.error("❌ BOT_TOKEN не установлен!")
        return

    app = ApplicationBuilder().token(bot_token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    app.add_handler(CallbackQueryHandler(callback_handler))

    logger.info("🤖 Бот склада пружин запущен! 🚀")
    app.run_polling()

if __name__ == "__main__":
    main()
