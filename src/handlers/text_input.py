from telegram.ext import MessageHandler, filters, ContextTypes
import logging
import json
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.helpers import escape_markdown

from src.database.connection import conn, cursor
from src.config import MAINTAINER_ID
from src.game.setup.join import join_game
from src.game.setup.start import start_game
from src.game.setup.role_assignment import handle_template_confirmation, save_template_as_pending
from src.game.utils import get_player_count

logger = logging.getLogger("Mafia Bot TextInput")

async def handle_text_input(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle text input from users based on their current state/action.
    Manages user name setting, passcode handling, and template name confirmations.
    """
    logger.debug("Handling a text message.")
    user_input = update.message.text.strip()
    action = context.user_data.get("action")
    user_id = update.effective_user.id

    if action == "awaiting_name":
        # Handle name setting
        cursor.execute("SELECT username FROM Users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        if result:
            # Update the user's name if it's different
            if result[0] != user_input:
                cursor.execute("UPDATE Users SET username = ? WHERE user_id = ?", (user_input, user_id))
                conn.commit()
                context.user_data["username"] = user_input
            else:
                # Name is the same, no update needed
                context.user_data["username"] = user_input
        else:
            # Insert new user into the database
            cursor.execute("INSERT INTO Users (user_id, username) VALUES (?, ?)", (user_id, user_input))
            conn.commit()
            context.user_data["username"] = user_input
        context.user_data["action"] = "join_game"  # Now expecting a passcode
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Please enter the passcode to join the game.")

    elif action == "existing_user":
        # Check if the input is a name or a passcode
        if is_valid_passcode(user_input):
            context.user_data["action"] = "join_game"
            await join_game(update, context, user_input)
        else:
            # Update the user's name in the database
            cursor.execute("UPDATE Users SET username = ? WHERE user_id = ?", (user_input, user_id))
            conn.commit()
            context.user_data["username"] = user_input
            context.user_data["action"] = "join_game"
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Name updated. Please enter the passcode to join the game.")

    elif action == "join_game":
        await join_game(update, context, user_input)  # Pass user_input as the passcode

    elif action == "set_roles":
        # In the revised flow, roles are set via buttons, so passcode is not needed here
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Please use the role buttons to set roles.")

    elif action == "start_game":
        await start_game(update, context, user_input)

    elif action == "awaiting_template_name_confirmation":
        # Handle the input as template name and save as pending
        await handle_template_confirmation(update, context, user_input)

    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Unknown action. Please use /start to begin.")

def is_valid_passcode(text):
    """Check if the text matches a UUID-like format for game passcodes."""
    pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$')
    return bool(pattern.match(text))

# Create the handler instance
text_input_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input)