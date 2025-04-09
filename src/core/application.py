import logging
from telegram.ext import Application

from src.config import TOKEN
from src.database.schema_extension import setup_database
from src.handlers.start import start_handler
from src.handlers.button_handler import button_handler, final_confirm_vote_handler, cancel_vote_handler
from src.handlers.text_input import text_input_handler
from src.core.error_handler import error_handler

def setup_application():
    logger = logging.getLogger("Mafia Bot")
    logger.info("Initializing the Mafia Bot...")

    # Initialize the database with extended schema
    setup_database()

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TOKEN).build()

    # Register handlers
    application.add_handler(start_handler)
    application.add_handler(button_handler)
    application.add_handler(final_confirm_vote_handler)
    application.add_handler(cancel_vote_handler)
    application.add_handler(text_input_handler)

    # Register the error handler
    application.add_error_handler(error_handler)

    return application

def run_application(application):
    logger = logging.getLogger("Mafia Bot")
    logger.info("Starting the bot...")
    application.run_polling()