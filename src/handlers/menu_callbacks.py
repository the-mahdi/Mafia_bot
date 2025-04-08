from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import ContextTypes
import logging
from src.utils.context import clear_user_data
from src.db import conn, cursor
from src.handlers.start_handler import start
from src.handlers.game_management import create_game, join_game, show_manage_games_menu

logger = logging.getLogger("Mafia Bot MenuCallbacks")

async def handle_back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the 'back_to_menu' callback query."""
    logger.debug("back_to_menu button pressed.")
    # Clean up user data before returning to the main menu (keeps username)
    clear_user_data(context)
    await start(update, context)

async def handle_create_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the 'create_game' callback query."""
    logger.debug("create_game button pressed.")
    await create_game(update, context)

async def handle_join_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the 'join_game' callback query."""
    logger.debug("join_game button pressed.")
    user_id = update.effective_user.id
    # Check if the user exists
    cursor.execute("SELECT username FROM Users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    if result:
        username = result[0]
        context.user_data["username"] = username
        context.user_data["action"] = "existing_user"
        keyboard = [
            [InlineKeyboardButton("Keep Name", callback_data="keep_name")],
            [InlineKeyboardButton("Change Name", callback_data="change_name")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Welcome back, {username}! Do you want to keep your name or change it?",
            reply_markup=reply_markup
        )
    else:
        context.user_data["action"] = "awaiting_name"
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Please enter your name.")

async def handle_manage_games(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the 'manage_games' callback query."""
    logger.debug("manage_games button pressed.")
    await show_manage_games_menu(update, context)

async def handle_keep_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the 'keep_name' callback query."""
    logger.debug("keep_name button pressed.")
    context.user_data["action"] = "join_game"
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Please enter the passcode to join the game.")

async def handle_change_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the 'change_name' callback query."""
    logger.debug("change_name button pressed.")
    context.user_data["action"] = "awaiting_name"
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Please enter your new name.")

async def handle_set_roles(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the 'set_roles' callback query."""
    logger.debug("set_roles button pressed.")
    user_id = update.effective_user.id
    game_id = context.user_data.get('game_id')
    if not game_id:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No game selected.")
        return
    # Check if the user is the moderator
    cursor.execute("SELECT moderator_id FROM Games WHERE game_id = ?", (game_id,))
    result = cursor.fetchone()
    if not result or result[0] != user_id:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="You are not authorized to set roles.")
        return
    context.user_data["action"] = "set_roles"
    context.user_data['current_page'] = 0
    
    from src.handlers.game_management import show_role_buttons
    await show_role_buttons(update, context)