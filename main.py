import logging
from telegram.ext import Application
from config import TOKEN  # Import config here
from db import initialize_database  # Import db here
from handlers.start_handler import start_handler
from handlers.button_handler import button_handler
from handlers.passcode_handler import passcode_handler


class ApplicationFilter(logging.Filter):
    def __init__(self, application_name):
        super().__init__()
        self.application_name = application_name

    def filter(self, record):
        # Allow logs from the application and the specified error handler
        if record.name.startswith(self.application_name) or record.name == "Mafia Bot ErrorHandler":
            return True

        # Optionally, suppress logs from specific noisy libraries
        if record.name.startswith("telegram") or record.name.startswith("httpx"):
            return False

        return False  # Default to filtering out other logs

def setup_logging():
    # Configure the root logger
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('mafia_bot.log')
        ]
    )

    # Add the filter to the handlers of the root logger
    for handler in logging.getLogger().handlers:
        handler.addFilter(ApplicationFilter("Mafia Bot"))

    logger = logging.getLogger("Mafia Bot")
    return logger

async def error_handler(update, context):
    logger = logging.getLogger("Mafia Bot ErrorHandler")
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    if update and update.effective_chat:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="An unexpected error occurred. Please try again later.")

def main():
    logger = setup_logging()
    logger.info("Initializing the Mafia Bot...")

    # Initialize the database
    initialize_database()

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TOKEN).build()

    # Register handlers
    application.add_handler(start_handler)
    application.add_handler(button_handler)
    application.add_handler(passcode_handler)

    # Register the error handler
    application.add_error_handler(error_handler)

    # Run the bot
    logger.info("Starting the bot...")
    application.run_polling()

if __name__ == "__main__":
    main()