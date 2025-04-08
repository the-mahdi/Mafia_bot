import logging
import json
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.helpers import escape_markdown
from telegram.ext import ContextTypes

from src.database.connection import conn, cursor
from src.config import MAINTAINER_ID
from src.game.utils import get_player_count

# Import the role templates - this will need to be updated later when roles.py is refactored
from src.game.roles.role_manager import role_templates, pending_templates, save_role_templates

logger = logging.getLogger("Mafia Bot RoleAssignment")

async def handle_template_confirmation(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, template_name: str) -> None:
    """
    Handle the confirmation of a new role template name.
    Gets the current roles from the game and prepares them to be saved as a template.
    """
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
    """
    Save a role template as pending confirmation by the maintainer.
    Creates and stores the template, then sends a confirmation request to the maintainer.
    """
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