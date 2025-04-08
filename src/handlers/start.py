from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CommandHandler, ContextTypes
import logging
from src.utils.context import clear_user_data

logger = logging.getLogger("Mafia Bot StartHandler")

async def start(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.debug("Handling /start command.")
    
    # Clear user data when starting a new interaction (keeps username)
    clear_user_data(context)
    
    keyboard = [
        [InlineKeyboardButton("Create Game", callback_data="create_game")],
        [InlineKeyboardButton("Join Game", callback_data="join_game")],
        [InlineKeyboardButton("Set Roles", callback_data="set_roles")],
        [InlineKeyboardButton("Select Template", callback_data="select_template")],
        [InlineKeyboardButton("Manage Games", callback_data="manage_games")],  # Updated button
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = "Welcome to the Mafia Game Bot!"
    await context.bot.send_message(chat_id=update.effective_chat.id, text=message, reply_markup=reply_markup)

# Create the handler instance
start_handler = CommandHandler("start", start)