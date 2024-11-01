# main.py
import logging
from telegram.ext import Application
from config import TOKEN
from db import initialize_database
from handlers.start_handler import start_handler
from handlers.button_handler import button_handler
from handlers.passcode_handler import passcode_handler

def setup_logging():
    # Create a logger for your application
    logger = logging.getLogger("Mafia Bot")
    logger.setLevel(logging.DEBUG)

    # Create handlers
    console_handler = logging.StreamHandler()
    file_handler = logging.FileHandler('mafia_bot.log')  # Optional: log to a file

    # Create formatters and add them to handlers
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    # Add handlers to the logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger

async def error_handler(update, context):
    logger = logging.getLogger("Mafia Bot ErrorHandler")
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    # Optionally, notify the user about the error
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
