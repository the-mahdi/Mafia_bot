import logging
from telegram.ext import Application

class ApplicationFilter(logging.Filter):
    """Custom filter for logging."""
    def __init__(self, application_name):
        super().__init__()
        self.application_name = application_name

    def filter(self, record):
        """Filters log records based on application name and specified libraries."""
        if record.name.startswith(self.application_name) or record.name == "Mafia Bot ErrorHandler":
            return True

        if record.name.startswith("telegram") or record.name.startswith("httpx"):
            return False

        return False

def setup_logging():
    """Configures the root logger with custom filter and handlers."""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('mafia_bot.log')
        ]
    )

    for handler in logging.getLogger().handlers:
        handler.addFilter(ApplicationFilter("Mafia Bot"))

    logger = logging.getLogger("Mafia Bot")
    return logger

async def error_handler(update, context):
    """Handles errors during updates."""
    logger = logging.getLogger("Mafia Bot ErrorHandler")
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    if update and update.effective_chat:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="An unexpected error occurred. Please try again later.")