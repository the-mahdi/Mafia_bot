import logging

async def error_handler(update, context):
    logger = logging.getLogger("Mafia Bot ErrorHandler")
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    if update and update.effective_chat:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="An unexpected error occurred. Please try again later.")