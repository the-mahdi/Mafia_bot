from telegram.ext import MessageHandler, filters, ContextTypes
import logging

from src.handlers.game_management.base import get_player_count
from src.handlers.game_management.join_game import join_game
from src.handlers.game_management.start_game import start_game
from src.roles import role_templates, pending_templates, save_role_templates
from src.db import conn, cursor
from src.config import MAINTAINER_ID
import json

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.helpers import escape_markdown  # newly added import

logger = logging.getLogger("Mafia Bot PasscodeHandler")

async def handle_passcode(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE) -> None:
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

async def handle_template_confirmation(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, template_name: str) -> None:
    logger.debug("Handling template confirmation.")
    game_id = context.user_data.get('game_id')

    if not game_id:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No game selected.")
        return

    # Get roles from the database
    cursor.execute("SELECT role, count FROM GameRoles WHERE game_id = ?", (game_id,))
    roles = {role: count for role, count in cursor.fetchall()}
    context.user_data['roles_for_template'] = roles

    # Get player count
    player_count = get_player_count(game_id)
    context.user_data['player_count'] = player_count

    await save_template_as_pending(update, context, template_name)

async def save_template_as_pending(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, template_name: str) -> None:
    logger.debug("Saving template as pending.")
    game_id = context.user_data.get('game_id')
    player_count = context.user_data.get("player_count")  # Get from context
    roles_for_template = context.user_data.get('roles_for_template')  # Get from context

    if not template_name:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Invalid template name.")
        return

    if not game_id:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No game selected.")
        return
    if not roles_for_template:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No roles found.")
        return
    if not player_count:
        player_count = get_player_count(game_id)  # Get from DB, since we might not have it in user_data

    template_name_with_count = f"{template_name} - {player_count}"

    # Check if the template name already exists in active templates
    existing_templates = role_templates.get(str(player_count), [])
    if any(t['name'] == template_name_with_count for t in existing_templates):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="A template with this name already exists. Please use a different name.")
        return

    # Check if the template name already exists in pending templates
    existing_pending = pending_templates.get(str(player_count), [])
    if any(t['name'] == template_name_with_count for t in existing_pending):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="This template is already pending confirmation.")
        return

    new_template = {
        "name": template_name_with_count,
        "roles": roles_for_template
    }

    # Load existing pending templates
    if str(player_count) not in pending_templates:
        pending_templates[str(player_count)] = []
    pending_templates[str(player_count)].append(new_template)

    # Save the updated templates
    save_role_templates(role_templates, pending_templates)

    # Notify the maintainer
    template_details = json.dumps(new_template, indent=2)

    confirmation_keyboard = [
        [InlineKeyboardButton("Confirm", callback_data=f"maintainer_confirm_{template_name_with_count}")],
        [InlineKeyboardButton("Reject", callback_data=f"maintainer_reject_{template_name_with_count}")]
    ]

    confirmation_markup = InlineKeyboardMarkup(confirmation_keyboard)

    try:
        message = f"New role template pending confirmation:\n```{template_details}```"
        safe_text = escape_markdown(message, version=2)
        await context.bot.send_message(
            chat_id=MAINTAINER_ID,
            text=safe_text,
            parse_mode='MarkdownV2',
            reply_markup=confirmation_markup
        )
    except Exception as e:
        logger.error(f"Failed to send confirmation message to maintainer: {e}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Failed to notify the maintainer. The template is saved as pending.")

    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Template '{template_name_with_count}' is pending confirmation by the maintainer.")

    # Reset user_data for the next template
    context.user_data['roles_for_template'] = None
    context.user_data['player_count'] = None
    context.user_data['action'] = None

def is_valid_passcode(text):
    # Basic check for a UUID-like format
    import re
    pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$')
    return bool(pattern.match(text))

# Create the handler instance
passcode_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, handle_passcode)
