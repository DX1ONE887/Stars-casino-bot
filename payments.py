import logging
import requests
import asyncio
import uuid
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, Application
import database
from ui import get_back_to_menu_keyboard_nested, get_payment_confirmation_keyboard, get_deposit_retry_keyboard
from config import MIN_DEPOSIT, MAX_DEPOSIT, YOOMONEY_ACCESS_TOKEN, YOOMONEY_WALLET

logger = logging.getLogger(__name__)

# Состояния разговора для пополнения баланса
DEPOSIT_AMOUNT, LINK_SENT = range(2)

def create_payment_link(amount: float, user_id: int):
    """Создает платежную ссылку ЮMoney для оплаты картой"""
    try:
        # Генерируем уникальный ID платежа
        payment_id = f"casino_{user_id}_{uuid.uuid4().hex[:8]}"
        
        # Параметры для платежа
        params = {
            "receiver": YOOMONEY_WALLET,
            "quickpay-form": "shop",
            "targets": f"Пополнение баланса казино (ID: {user_id})",
            "paymentType": "AC",  # Оплата картой
            "sum": amount,
            "label": payment_id,
            "successURL": "https://t.me/casino_stars_bot"
        }
        
        # Формируем URL
        base_url = "https://yoomoney.ru/quickpay/confirm.xml"
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        payment_url = f"{base_url}?{query_string}"
        
        return {
            "payment_url": payment_url,
            "payment_id": payment_id
        }
    except Exception as e:
        logger.error(f"Ошибка создания платежной ссылки: {e}")
        return None

async def process_payment_request(payment_id: str, user_id: int, amount: int):
    """Проверяет статус платежа по его ID"""
    if not YOOMONEY_ACCESS_TOKEN:
        logger.error("YOOMONEY_ACCESS_TOKEN не настроен!")
        return False
    
    try:
        # Проверяем историю операций
        response = requests.post(
            "https://yoomoney.ru/api/operation-history",
            headers={"Authorization": f"Bearer {YOOMONEY_ACCESS_TOKEN}"},
            data={
                "label": payment_id,
                "type": "deposition"
            },
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            # Ищем наш платеж в истории
            for operation in data.get("operations", []):
                if operation.get("status") == "success" and operation.get("label") == payment_id:
                    # Зачисляем средства
                    await database.update_user_balance(user_id, amount, relative=True)
                    return True
        return False
    except Exception as e:
        logger.error(f"Ошибка проверки платежа: {e}")
        return False

async def deposit_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало процесса пополнения баланса"""
    query = update.callback_query
    await query.answer()
    
    text = (
        f"💳 <b>Пополнение баланса</b>\n\n"
        f"Введите сумму для пополнения в рублях.\n"
        f"• Минимальная сумма: {MIN_DEPOSIT} руб.\n"
        f"• Максимальная сумма: {MAX_DEPOSIT} руб.\n\n"
        "Просто отправьте число, например: 500"
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Назад в меню", callback_data="main_menu_from_nested")]
    ])
    
    await query.edit_message_text(
        text=text,
        reply_markup=keyboard,
        parse_mode='HTML'
    )
    
    # Очищаем предыдущие данные платежа
    context.user_data.pop('deposit_amount', None)
    context.user_data.pop('payment_id', None)
    
    return DEPOSIT_AMOUNT

async def process_deposit_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка введенной суммы для пополнения"""
    try:
        amount = int(update.message.text)
        logger.info(f"Пользователь {update.effective_user.id} ввел сумму: {amount} руб.")
    except (ValueError, TypeError):
        await update.message.reply_text(
            "❌ Пожалуйста, введите целое число.",
            reply_markup=get_back_to_menu_keyboard_nested()
        )
        return LINK_SENT
    
    if amount < MIN_DEPOSIT:
        await update.message.reply_text(
            f"❌ Сумма слишком мала. Минимальное пополнение: {MIN_DEPOSIT} руб.",
            reply_markup=get_back_to_menu_keyboard_nested()
        )
        return LINK_SENT
    
    if amount > MAX_DEPOSIT:
        await update.message.reply_text(
            f"❌ Сумма слишком велика. Максимальное пополнение: {MAX_DEPOSIT} руб.",
            reply_markup=get_back_to_menu_keyboard_nested()
        )
        return LINK_SENT
    
    # Сохраняем сумму в контексте
    context.user_data['deposit_amount'] = amount
    
    # Удаляем сообщение пользователя с суммой
    try:
        await update.message.delete()
    except:
        logger.warning("Не удалось удалить сообщение с суммой")
    
    # Сразу создаем платежную ссылку
    return await create_payment_link_for_user(update, context, amount)

async def create_payment_link_for_user(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: int):
    """Создание и отправка платежной ссылки"""
    user = update.effective_user
    logger.info(f"Создание платежной ссылки для {user.id} на сумму {amount} руб.")
    
    # Убираем reply_to_message_id чтобы избежать ошибки "Message to be replied not found"
    processing_msg = await context.bot.send_message(
        update.effective_chat.id,
        "⏳ Создаем платежную ссылку..."
    )
    
    # Создаем платеж
    payment_data = create_payment_link(amount, user.id)
    
    if not payment_data:
        await processing_msg.edit_text(
            "❌ Не удалось создать платеж. Пожалуйста, попробуйте позже.",
            reply_markup=get_deposit_retry_keyboard()
        )
        return LINK_SENT
    
    # Сохраняем данные платежа в контексте
    context.user_data['payment_id'] = payment_data["payment_id"]
    context.user_data['payment_amount'] = amount
    
    text = (
        f"💳 <b>Пополнение баланса на {amount} руб.</b>\n\n"
        f"Для оплаты перейдите по ссылке:\n"
        f"<a href='{payment_data['payment_url']}'>Оплатить через ЮMoney</a>\n\n"
        "После оплаты нажмите кнопку <b>'✅ Я оплатил(а)'</b> ниже.\n"
        f"<b>ID платежа:</b> <code>{payment_data['payment_id']}</code>\n\n"
        "<i>Примечание: после оплаты может потребоваться до 3 минут для обработки платежа</i>"
    )
    
    await processing_msg.edit_text(
        text, 
        reply_markup=get_payment_confirmation_keyboard(),
        parse_mode='HTML',
        disable_web_page_preview=True
    )
    
    return LINK_SENT

async def check_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Проверка статуса платежа"""
    query = update.callback_query
    await query.answer()
    
    payment_id = context.user_data.get('payment_id')
    amount = context.user_data.get('payment_amount', 0)
    user_id = update.effective_user.id
    
    if not payment_id or not amount:
        await context.bot.send_message(
            update.effective_chat.id,
            "❌ Ошибка: данные платежа не найдены. Начните процесс заново."
        )
        return LINK_SENT
    
    # Убираем reply_to_message_id чтобы избежать ошибки
    processing_msg = await context.bot.send_message(
        update.effective_chat.id,
        f"🔍 Проверяем ваш платеж {payment_id}..."
    )
    
    # Проверяем платеж
    if await process_payment_request(payment_id, user_id, amount):
        # Платеж подтвержден - зачисляем средства
        new_balance = await database.get_user_balance(user_id)
        
        text = (
            f"✅ <b>Платеж подтвержден!</b>\n\n"
            f"На ваш счет зачислено: <b>{amount}</b> руб.\n"
            f"Ваш новый баланс: <b>{new_balance}</b> руб.\n\n"
            f"<b>ID платежа:</b> <code>{payment_id}</code>"
        )
    else:
        text = (
            f"⌛ <b>Платеж еще не поступил</b>\n\n"
            f"Платеж {payment_id} не найден в системе.\n\n"
            "Пожалуйста:\n"
            "1. Убедитесь, что вы завершили оплату\n"
            "2. Подождите 2-3 минуты\n"
            "3. Попробуйте нажать кнопку еще раз\n\n"
            "Если платеж не подтвердится, свяжитесь с поддержкой."
        )
    
    await processing_msg.edit_text(
        text, 
        parse_mode='HTML',
        reply_markup=get_payment_confirmation_keyboard()
    )
    return LINK_SENT

def setup_payment_verification(application: Application):
    """Инициализация платежной системы"""
    if YOOMONEY_ACCESS_TOKEN:
        logger.info("Платежная система ЮMoney инициализирована")
        logger.info(f"Кошелек получателя: {YOOMONEY_WALLET}")
    else:
        logger.warning("YOOMONEY_ACCESS_TOKEN не настроен! Автопроверка платежей работать не будет!")