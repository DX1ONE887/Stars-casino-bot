import logging
import asyncio
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import TELEGRAM_TOKEN
import database
import handlers
import payments
import admin

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

async def post_init(application: Application) -> None:
    await database.init_db()
    logger.info("База данных успешно инициализирована.")
    payments.setup_payment_verification(application)

def main() -> None:
    builder = Application.builder().token(TELEGRAM_TOKEN)
    builder.post_init(post_init)
    application = builder.build()
    
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
    
    # Обработчик пополнения (УПРОЩЕННЫЙ)
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
        entry_points=[CallbackQueryHandler(handlers.request_nickname, pattern='^set_nickname$')],
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
    
    application.add_handler(CommandHandler('top', handlers.show_top))
    application.add_handler(CommandHandler('set_nickname', handlers.request_nickname_from_command))
    
    # Админские команды
    application.add_handler(CommandHandler('admin', admin.admin_panel))
    application.add_handler(CommandHandler('check_balance', admin.check_user_balance))
    application.add_handler(CommandHandler('add_balance', admin.add_to_balance))
    application.add_handler(CommandHandler('sub_balance', admin.subtract_from_balance))
    application.add_handler(CommandHandler('broadcast', admin.broadcast_message))
    application.add_handler(CommandHandler('server_stats', admin.show_server_stats))

    logger.info("Бот запущен...")
    application.run_polling(allowed_updates=True)

if __name__ == "__main__":
    asyncio.run(main())