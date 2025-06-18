from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура главного меню"""
    keyboard = [
        [InlineKeyboardButton("🎲 Играть", callback_data="play")],
        [
            InlineKeyboardButton("💰 Баланс", callback_data="balance"),
            InlineKeyboardButton("📜 Правила", callback_data="rules")
        ],
        [
            InlineKeyboardButton("🏆 Топ игроков", callback_data="top"),
            InlineKeyboardButton("👤 Мой ник", callback_data="set_nickname")
        ],
        [
            InlineKeyboardButton("💳 Пополнить баланс", callback_data="deposit"),
            InlineKeyboardButton("📤 Вывод средств", callback_data="withdraw")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_to_menu_keyboard_simple() -> InlineKeyboardMarkup:
    """Простая кнопка возврата в меню"""
    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="back_to_start")]]
    return InlineKeyboardMarkup(keyboard)

def get_back_to_menu_keyboard_nested() -> InlineKeyboardMarkup:
    """Кнопка возврата из вложенных меню"""
    keyboard = [[InlineKeyboardButton("⬅️ Назад в меню", callback_data="main_menu_from_nested")]]
    return InlineKeyboardMarkup(keyboard)

def get_game_choice_keyboard() -> InlineKeyboardMarkup:
    """Выбор игры"""
    keyboard = [
        [
            InlineKeyboardButton("🎲", callback_data="game_dice"),
            InlineKeyboardButton("🏀", callback_data="game_basketball"),
            InlineKeyboardButton("⚽", callback_data="game_football"),
            InlineKeyboardButton("🎰", callback_data="game_dart"),
        ],
        [InlineKeyboardButton("⬅️ Назад в меню", callback_data="main_menu_from_nested")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_payment_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения оплаты"""
    keyboard = [
        [InlineKeyboardButton("✅ Я оплатил(а)", callback_data="payment_confirmed")],
        [InlineKeyboardButton("⬅️ Назад в меню", callback_data="main_menu_from_nested")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_deposit_retry_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура при ошибке платежа"""
    keyboard = [
        [InlineKeyboardButton("🔄 Попробовать снова", callback_data="deposit")],
        [InlineKeyboardButton("⬅️ Назад в меню", callback_data="main_menu_from_nested")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_deposit_options_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора суммы депозита (упрощенная)"""
    keyboard = [
        [InlineKeyboardButton("💳 Оплатить через ЮMoney", callback_data="method_yoomoney")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_deposit")]
    ]
    return InlineKeyboardMarkup(keyboard)