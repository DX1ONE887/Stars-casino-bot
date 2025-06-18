import os
import asyncio
import logging
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)
from config import TELEGRAM_TOKEN, WEBHOOK_MODE, PORT, WEBHOOK_URL, WEBHOOK_SECRET
import database
import handlers
import payments
import admin

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

async def post_init(application: Application) -> None:
    """Инициализация после запуска приложения"""
    await database.init_db()
    logger.info("База данных успешно инициализирована.")
    payments.setup_payment_verification(application)

def setup_handlers(application: Application) -> None:
    """Настройка всех обработчиков бота"""
    # Обработчик игры
    game_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(handlers.play_game, pattern='^play$')],
        states={
            handlers.GAME_CHOICE: [CallbackQueryHandler(handlers.choose_game, pattern='^game_')],
            handlers.BET_PLACEMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.place_bet)],
            handlers.RESULT_SHOWN: [CallbackQueryHandler(handlers.back_to_menu, pattern='^main_menu_from_nested$')]
        },
        fallbacks=[CallbackQueryHandler(handlers.back_to_menu, pattern='^main_menu_from_nested$')],
        map_to_parent={ ConversationHandler.END: handlers.MAIN_MENU }
    )
    
    # Обработчик пополнения баланса
    deposit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(payments.deposit_start, pattern='^deposit$')],
        states={
            payments.DEPOSIT_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, payments.process_deposit_amount),
                CallbackQueryHandler(handlers.back_to_menu, pattern='^main_menu_from_nested$')
            ],
            payments.LINK_SENT: [
                CallbackQueryHandler(payments.check_payment, pattern='^payment_confirmed$'),
                CallbackQueryHandler(handlers.back_to_menu, pattern='^main_menu_from_nested$')
            ]
        },
        fallbacks=[CallbackQueryHandler(handlers.back_to_menu, pattern='^main_menu_from_nested$')],
        map_to_parent={ ConversationHandler.END: handlers.MAIN_MENU }
    )

    # Обработчик вывода средств
    withdraw_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(handlers.withdraw, pattern='^withdraw$')],
        states={
            handlers.WITHDRAW_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.process_withdrawal_amount)],
            handlers.REQUEST_SENT: [CallbackQueryHandler(handlers.back_to_menu, pattern='^main_menu_from_nested$')]
        },
        fallbacks=[CallbackQueryHandler(handlers.back_to_menu, pattern='^main_menu_from_nested$')],
        map_to_parent={ ConversationHandler.END: handlers.MAIN_MENU }
    )
    
    # Обработчик установки никнейма
    set_nickname_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handlers.request_nickname, pattern='^set_nickname$'),
            CommandHandler('set_nickname', handlers.request_nickname_from_command)
        ],
        states={
            handlers.SETTING_NICKNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.save_nickname)],
            handlers.NICKNAME_SET: [CallbackQueryHandler(handlers.back_to_menu, pattern='^main_menu_from_nested$')]
        },
        fallbacks=[CallbackQueryHandler(handlers.back_to_menu, pattern='^main_menu_from_nested$')],
        map_to_parent={ ConversationHandler.END: handlers.MAIN_MENU }
    )

    # Главный обработчик
    main_handler = ConversationHandler(
        entry_points=[CommandHandler('start', handlers.start)],
        states={
            handlers.MAIN_MENU: [
                game_conv,
                deposit_conv,
                withdraw_conv,
                set_nickname_conv,
                CallbackQueryHandler(handlers.balance, pattern='^balance$'),
                CallbackQueryHandler(handlers.rules, pattern='^rules$'),
                CallbackQueryHandler(handlers.show_top, pattern='^top$'),
                CallbackQueryHandler(handlers.start_over, pattern='^back_to_start$'),
            ]
        },
        fallbacks=[CommandHandler('start', handlers.start)],
    )

    application.add_handler(main_handler)
    
    # Отдельные команды
    application.add_handler(CommandHandler('top', handlers.show_top))
    
    # Админские команды
    application.add_handler(CommandHandler('admin', admin.admin_panel))
    application.add_handler(CommandHandler('check_balance', admin.check_user_balance))
    application.add_handler(CommandHandler('add_balance', admin.add_to_balance))
    application.add_handler(CommandHandler('sub_balance', admin.subtract_from_balance))
    application.add_handler(CommandHandler('broadcast', admin.broadcast_message))
    application.add_handler(CommandHandler('server_stats', admin.show_server_stats))

async def start_webhook(application: Application) -> None:
    """Запуск в режиме вебхука"""
    await application.bot.set_webhook(
        url=f"{WEBHOOK_URL}/telegram",
        secret_token=WEBHOOK_SECRET,
        drop_pending_updates=True
    )
    logger.info(f"Webhook установлен на {WEBHOOK_URL}/telegram")

async def start_polling(application: Application) -> None:
    """Запуск в режиме поллинга"""
    await application.bot.delete_webhook(drop_pending_updates=True)
    logger.info("Бот запущен в режиме поллинга...")
    await application.start_polling(allowed_updates=True)

def main() -> None:
    """Основная функция запуска бота"""
    # Создание приложения
    builder = Application.builder().token(TELEGRAM_TOKEN)
    builder.post_init(post_init)
    application = builder.build()
    
    # Настройка обработчиков
    setup_handlers(application)
    
    # Запуск в соответствующем режиме
    if WEBHOOK_MODE and WEBHOOK_URL and WEBHOOK_SECRET:
        logger.info("Запуск в режиме WEBHOOK")
        logger.info(f"URL: {WEBHOOK_URL}")
        logger.info(f"PORT: {PORT}")
        logger.info(f"Secret: {WEBHOOK_SECRET[:3]}...")
        
        # Создание веб-сервера
        from aiohttp import web
        
        async def telegram_webhook(request):
            """Обработчик входящих обновлений Telegram"""
            if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET:
                return web.Response(status=403)
            
            await application.update_queue.put(await request.json())
            return web.Response()
        
        async def health_check(request):
            """Проверка работоспособности сервера"""
            return web.Response(text="OK")
        
        app = web.Application()
        app.router.add_post('/telegram', telegram_webhook)
        app.router.add_get('/health', health_check)
        
        async def run_app():
            """Запуск веб-сервера"""
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, '0.0.0.0', PORT)
            await site.start()
            
            logger.info(f"Сервер запущен на порту {PORT}")
            await start_webhook(application)
            
            # Бесконечный цикл для поддержания работы приложения
            while True:
                await asyncio.sleep(3600)
        
        loop = asyncio.get_event_loop()
        loop.run_until_complete(run_app())
        
    else:
        logger.info("Запуск в режиме POLLING")
        application.run_polling(allowed_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
