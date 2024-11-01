from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CommandHandler, ContextTypes
import logging

logger = logging.getLogger("Mafia Bot StartHandler")

async def start(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.debug("Handling /start command.")
    keyboard = [
        [InlineKeyboardButton("Create Game", callback_data="create_game")],
        [InlineKeyboardButton("Join Game", callback_data="join_game")],
        [InlineKeyboardButton("Set Roles", callback_data="set_roles")],
        [InlineKeyboardButton("Select Template", callback_data="select_template")],
        [InlineKeyboardButton("Start Game", callback_data="start_game")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = "Welcome to the Mafia Game Bot!"
    await context.bot.send_message(chat_id=update.effective_chat.id, text=message, reply_markup=reply_markup)

# Create the handler instance
start_handler = CommandHandler("start", start)
