import logging
import asyncio
import re
from html import escape
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
import database
from config import MIN_BET, MAX_BET, MIN_WITHDRAWAL, ADMIN_CHAT_ID
import ui

logger = logging.getLogger(__name__)

# Состояния разговора
MAIN_MENU, GAME_CHOICE, BET_PLACEMENT, RESULT_SHOWN, WITHDRAW_AMOUNT, REQUEST_SENT, SETTING_NICKNAME, NICKNAME_SET = range(8)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка команды /start"""
    user = update.effective_user
    await database.add_user_if_not_exists(user.id, user.username)
    logger.info(f"Пользователь {user.id} ({user.username}) запустил/перезапустил бота.")
    
    text = f"👋 Привет, {user.mention_html()}!\n\nДобро пожаловать в наше казино! Выбери действие:"
    reply_markup = ui.get_main_menu_keyboard()
    
    if update.message:
        await update.message.reply_html(text, reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')

    return MAIN_MENU

async def start_over(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Возврат в начало"""
    query = update.callback_query
    await query.answer()
    logger.info(f"Пользователь {query.from_user.id} нажал 'Назад в начало'")
    return await start(update, context)

async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Возврат в главное меню"""
    query = update.callback_query
    await query.answer()
    logger.info(f"Пользователь {query.from_user.id} нажал 'Назад в меню'")
    
    user = update.effective_user
    text = f"👋 Привет, {user.mention_html()}!\n\nВы в главном меню. Выбери действие:"
    reply_markup = ui.get_main_menu_keyboard()
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    return MAIN_MENU

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать баланс"""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    logger.info(f"Пользователь {user_id} запросил баланс")
    
    user_balance = await database.get_user_balance(user_id)
    text = f"💰 Ваш текущий баланс: <b>{user_balance}</b> руб."
    
    await query.edit_message_text(text, reply_markup=ui.get_back_to_menu_keyboard_simple(), parse_mode='HTML')

async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать правила"""
    logger.info("Обработка запроса правил")
    
    # Получаем query из update
    query = update.callback_query
    
    # Если есть query (вызов из callback)
    if query:
        await query.answer()
        logger.info(f"Пользователь {query.from_user.id} запросил правила через кнопку")
    # Если нет query (прямой вызов команды)
    elif update.message:
        logger.info(f"Пользователь {update.effective_user.id} запросил правила через команду")
    
    rules_text = (
        "<b>📜 Правила Игры и Коэффициенты</b>\n\n"
        f"<b>Ставки:</b> от {MIN_BET} до {MAX_BET} руб.\n"
        f"<b>Вывод:</b> от {MIN_WITHDRAWAL} руб.\n\n"
        "<b>🎰 Слот-машина:</b>\n"
        "  7️⃣7️⃣7️⃣ (Джекпот): <b>x50</b>\n"
        "  🍇🍇🍇 (Три винограда): <b>x20</b>\n"
        "  🍋🍋🍋 (Три лимона): <b>x10</b>\n"
        "  🅱️🅱️🅱️ (Три BAR): <b>x5</b>\n\n"
        "<b>🎲 Кости:</b>\n"
        "  Выпало 6: <b>x3</b>\n"
        "  Выпало 5: <b>x2</b>\n\n"
        "<b>🏀/⚽ Баскетбол/Футбол:</b>\n"
        "  Мяч в цели (попадание): <b>x2.5</b>\n"
        "  Почти попал (рядом): <b>x1 (возврат ставки)</b>"
    )
    
    if query:
        await query.edit_message_text(
            rules_text, 
            reply_markup=ui.get_back_to_menu_keyboard_simple(), 
            parse_mode='HTML'
        )
    else:
        await update.message.reply_text(
            rules_text, 
            reply_markup=ui.get_back_to_menu_keyboard_simple(), 
            parse_mode='HTML'
        )

async def play_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начать игру"""
    query = update.callback_query
    await query.answer()
    logger.info(f"Пользователь {query.from_user.id} начал игру")
    
    await query.edit_message_text("Выберите игру:", reply_markup=ui.get_game_choice_keyboard())
    return GAME_CHOICE

async def choose_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Выбор игры"""
    query = update.callback_query
    await query.answer()
    game_type = query.data.split('_')[1]
    logger.info(f"Пользователь {query.from_user.id} выбрал игру: {game_type}")
    
    context.user_data["game"] = game_type
    await query.edit_message_text(f"Вы выбрали игру. Теперь введите вашу ставку (от {MIN_BET} до {MAX_BET} руб.):")
    return BET_PLACEMENT

async def place_bet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Размещение ставки"""
    user = update.effective_user
    logger.info(f"Пользователь {user.id} вводит ставку")
    
    try:
        bet = int(update.message.text)
        logger.info(f"Ставка пользователя {user.id}: {bet} руб.")
    except (ValueError, TypeError):
        await update.message.reply_text("Пожалуйста, введите числовое значение.", reply_markup=ui.get_back_to_menu_keyboard_nested())
        return RESULT_SHOWN

    user_balance = await database.get_user_balance(user.id)

    if not (MIN_BET <= bet <= MAX_BET) or bet > user_balance:
        error_msg = f"Некорректная ставка. Ваш баланс: {user_balance} руб."
        logger.warning(f"Ошибка ставки: {error_msg}")
        await update.message.reply_text(error_msg, reply_markup=ui.get_back_to_menu_keyboard_nested())
        return RESULT_SHOWN

    await database.update_user_balance(user.id, -bet, relative=True)
    
    game_emoji = {"dice": "🎲", "basketball": "🏀", "football": "⚽", "dart": "🎰"}[context.user_data["game"]]
    
    msg = await context.bot.send_dice(chat_id=update.effective_chat.id, emoji=game_emoji)
    logger.info(f"Отправлен кубик для игры {context.user_data['game']}")
    
    await asyncio.sleep(3.5)
    
    dice_value = msg.dice.value
    win_amount = 0
    result_text = "К сожалению, вы проиграли."
    game = context.user_data["game"]

    if game == 'dart':
        if dice_value == 64: 
            win_amount, result_text = bet * 50, "ДЖЕКПОТ! 7️⃣7️⃣7️⃣"
        elif dice_value == 43: 
            win_amount, result_text = bet * 20, "Отлично! Три винограда! 🍇🍇🍇"
        elif dice_value == 22: 
            win_amount, result_text = bet * 10, "Неплохо! Три лимона! 🍋🍋🍋"
        elif dice_value == 1: 
            win_amount, result_text = bet * 5, "Выигрыш! Три BAR! 🅱️🅱️🅱️"
    elif game == 'dice':
        if dice_value == 6: 
            win_amount, result_text = bet * 3, "Выпало 6! Ваш выигрыш!"
        elif dice_value == 5: 
            win_amount, result_text = bet * 2, "Выпало 5! Вы победили!"
    elif game in ['basketball', 'football']:
        if dice_value == 5: 
            win_amount, result_text = int(bet * 2.5), "ГОЛ! Вы победили!"
        elif dice_value == 4: 
            win_amount, result_text = bet, "Почти! Ваша ставка возвращена."

    if win_amount > 0:
        await database.update_user_balance(user.id, win_amount, relative=True)
        logger.info(f"Пользователь {user.id} выиграл {win_amount} руб.")
    
    await database.update_user_stats(user.id, bet, win_amount)
    
    final_balance = await database.get_user_balance(user.id)
    
    text = (f"{result_text}\n\n"
            f"Ваша ставка: {bet} руб. | Выигрыш: {win_amount} руб.\n"
            f"Ваш новый баланс: <b>{final_balance}</b> руб.")
    
    logger.info(f"Результат игры: {text}")
    await update.message.reply_html(text, reply_markup=ui.get_back_to_menu_keyboard_nested())
    return RESULT_SHOWN

async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрос вывода средств"""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    logger.info(f"Пользователь {user_id} запросил вывод средств")
    
    user_balance = await database.get_user_balance(user_id)

    if user_balance < MIN_WITHDRAWAL:
        error_msg = (f"❌ Ошибка: минимальная сумма для вывода {MIN_WITHDRAWAL} руб. "
                    f"У вас на балансе {user_balance} руб.")
        logger.warning(error_msg)
        await query.edit_message_text(
            error_msg,
            reply_markup=ui.get_back_to_menu_keyboard_nested()
        )
        return REQUEST_SENT
    
    await query.edit_message_text(f"Ваш баланс: {user_balance} руб. Введите сумму, которую хотите вывести:")
    return WITHDRAW_AMOUNT

async def process_withdrawal_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка суммы вывода"""
    user = update.effective_user
    try:
        amount = int(update.message.text)
        logger.info(f"Пользователь {user.id} ввел сумму для вывода: {amount} руб.")
    except (ValueError, TypeError):
        await update.message.reply_text("Пожалуйста, введите числовое значение.", reply_markup=ui.get_back_to_menu_keyboard_nested())
        return REQUEST_SENT

    user_balance = await database.get_user_balance(user.id)

    if amount < MIN_WITHDRAWAL or amount > user_balance:
        error_text = (f"❌ Некорректная сумма.\n"
                    f"• Минимальный вывод: {MIN_WITHDRAWAL} руб.\n"
                    f"• Ваш баланс: {user_balance} руб.")
        logger.warning(error_text)
        await update.message.reply_text(error_text, reply_markup=ui.get_back_to_menu_keyboard_nested())
        return REQUEST_SENT

    # Формируем запрос на вывод
    context.user_data['withdrawal_amount'] = amount
    context.user_data['withdrawal_user_id'] = user.id
    
    # Просто подтверждаем запрос
    success_msg = (f"✅ Ваш запрос на вывод {amount} руб. принят в обработку.\n"
                 "Администратор свяжется с вами в ближайшее время для уточнения деталей.")
    
    logger.info(f"Пользователь {user.id} запросил вывод {amount} руб.")
    await update.message.reply_text(
        success_msg,
        reply_markup=ui.get_back_to_menu_keyboard_nested()
    )
    
    return REQUEST_SENT

async def show_top(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать топ игроков"""
    logger.info("Обработка запроса топа игроков")
    query = update.callback_query
    if query:
        await query.answer()
        logger.info(f"Пользователь {query.from_user.id} запросил топ игроков через кнопку")
    else:
        logger.info(f"Пользователь {update.effective_user.id} запросил топ игроков через команду")
    
    top_users = await database.get_top_users(10)
    
    if not top_users:
        text = "🏆 Таблица лидеров пока пуста."
    else:
        text = "<b>🏆 Топ-10 игроков по балансу:</b>\n\n"
        for i, user in enumerate(top_users):
            rank = i + 1
            display_name = user['nickname'] if user['nickname'] else user['username']
            safe_display_name = escape(display_name) if display_name else f"User {user['user_id']}"
            balance = user['balance']
            
            line = f"<b>{rank}.</b> {safe_display_name} — <code>{balance}</code> руб.\n"
            if user['user_id'] == update.effective_user.id:
                line = f"➡️ {line}"
            text += line
            
    reply_markup = ui.get_back_to_menu_keyboard_simple()
    
    if query:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        await update.message.reply_html(text, reply_markup=reply_markup)

async def request_nickname_from_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрос никнейма через команду"""
    user = update.effective_user
    logger.info(f"Пользователь {user.id} запросил установку никнейма через команду")
    await update.message.reply_text("Введите ваш новый никнейм (3-15 символов, буквы, цифры, _-):")
    return SETTING_NICKNAME

async def request_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрос никнейма через кнопку"""
    query = update.callback_query
    await query.answer()
    logger.info(f"Пользователь {query.from_user.id} запросил установку никнейма")
    await query.edit_message_text("Введите ваш новый никнейм (3-15 символов, буквы, цифры, _-):")
    return SETTING_NICKNAME

async def save_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохранение никнейма"""
    nickname = update.message.text
    user = update.effective_user
    logger.info(f"Пользователь {user.id} пытается установить никнейм: {nickname}")
    
    # Исправленное условие проверки никнейма
    if len(nickname) < 3 or len(nickname) > 15 or not re.match(r'^[a-zA-Z0-9_-]+$', nickname):
        error_msg = "❌ <b>Ошибка:</b> Никнейм должен быть длиной от 3 до 15 символов и содержать только латинские буквы, цифры, знаки подчеркивания (_) или дефисы (-)."
        logger.warning(f"Некорректный никнейм: {nickname}")
        await update.message.reply_html(error_msg)
        return SETTING_NICKNAME

    user_id = update.effective_user.id
    await database.set_user_nickname(user_id, nickname)
    
    success_msg = f"✅ Ваш никнейм успешно изменен на: <b>{escape(nickname)}</b>"
    logger.info(success_msg)
    await update.message.reply_html(
        success_msg,
        reply_markup=ui.get_back_to_menu_keyboard_nested()
    )
    return NICKNAME_SET

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка неизвестных команд"""
    logger.warning(f"Получена неизвестная команда: {update.message.text if update.message else 'callback'}")
    
    if update.message:
        await update.message.reply_text(
            "Неизвестная команда. Используйте /start для начала работы.",
            reply_markup=ui.get_back_to_menu_keyboard_nested()
        )
    elif update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            "Неизвестная команда. Возвращаемся в меню.",
            reply_markup=ui.get_main_menu_keyboard()
        )
    return MAIN_MENU
