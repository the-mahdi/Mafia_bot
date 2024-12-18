from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, ContextTypes
import logging
from db import conn, cursor
from roles import available_roles, role_descriptions, role_templates, pending_templates, save_role_templates
from handlers.game_management import (
    show_role_buttons,
    confirm_and_set_roles,
    get_player_count,
    get_templates_for_player_count,
    get_random_shuffle,
    create_game,
    join_game,
    set_roles,
    start_game
)
from handlers.start_handler import start
from config import MAINTAINER_ID
import asyncio
import json
from handlers.game_management import ROLES_PER_PAGE

logger = logging.getLogger("Mafia Bot ButtonHandler")

# Initialize a dictionary to store locks for each game
game_locks = {}

async def handle_button(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.debug("Handling a button press.")
    query = update.callback_query
    await query.answer()
    data = query.data
    message_id = query.message.message_id
    user_id = update.effective_user.id

    # Retrieve game_id from user_data
    game_id = context.user_data.get('game_id')

    if data == "back_to_menu":
        logger.debug("back_to_menu button pressed.")
        await start(update, context)  # Ensure 'start' is imported or accessible
        
    elif data == "prev_page":
        logger.debug("Previous page button pressed.")
        current_page = context.user_data.get('current_page', 0)
        context.user_data['current_page'] = max(0, current_page - 1)
        await show_role_buttons(update, context, message_id)

    elif data == "next_page":
        logger.debug("Next page button pressed.")
        current_page = context.user_data.get('current_page', 0)
        context.user_data['current_page'] = current_page + 1
        await show_role_buttons(update, context, message_id)

    elif data == "reset_roles":
        logger.debug("reset_roles button pressed.")
        if not game_id:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="No game selected.")
            return
        game_lock = game_locks.get(game_id)
        if not game_lock:
            game_lock = asyncio.Lock()
            game_locks[game_id] = game_lock
        async with game_lock:
            cursor.execute("DELETE FROM GameRoles WHERE game_id = ?", (game_id,))
            # Initialize role counts to 0 for all roles
            for role in available_roles:
                cursor.execute(
                    "INSERT INTO GameRoles (game_id, role, count) VALUES (?, ?, 0) ON CONFLICT(game_id, role) DO UPDATE SET count=0",
                    (game_id, role)
                )
            conn.commit()
            context.user_data['current_page'] = 0
            await show_role_buttons(update, context, message_id)

    elif data == "create_game":
        logger.debug("create_game button pressed.")
        await create_game(update, context)

    elif data == "join_game":
        logger.debug("join_game button pressed.")
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
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Welcome back, {username}! Do you want to keep your name or change it?", reply_markup=reply_markup)
        else:
            context.user_data["action"] = "awaiting_name"
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Please enter your name.")

    elif data == "set_roles":
        logger.debug("set_roles button pressed.")
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
        await show_role_buttons(update, context)

    elif data == "start_game":
        logger.debug("start_game button pressed.")
        if not game_id:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="No game selected.")
            return
        # Check if the user is the moderator
        cursor.execute("SELECT moderator_id FROM Games WHERE game_id = ?", (game_id,))
        result = cursor.fetchone()
        if not result or result[0] != user_id:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="You are not authorized to start the game.")
            return
        context.user_data["action"] = "start_game"
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Please enter the passcode to start the game.")

    elif data == "select_template":
        logger.debug("select_template button pressed.")
        if not game_id:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="No game selected.")
            return
        player_count = get_player_count(game_id)
        templates = get_templates_for_player_count(player_count)
        if not templates:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"No templates available for {player_count} players.")
            return
        # Create buttons for each template
        template_buttons = [
            [InlineKeyboardButton(template['name'], callback_data=f"template_{template['name']}")]
            for template in templates
        ]
        # Add a back button
        template_buttons.append([InlineKeyboardButton("Back to Menu", callback_data="back_to_menu")])
        reply_markup = InlineKeyboardMarkup(template_buttons)
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Select a role template:", reply_markup=reply_markup)

    elif data.startswith("template_"):
        template_name = data.split("template_", 1)[1]
        logger.debug(f"Template selected: {template_name}")
        if not game_id:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="No game selected.")
            return
        # Find the selected template
        player_count = get_player_count(game_id)
        templates = get_templates_for_player_count(player_count)
        selected_template = next((t for t in templates if t['name'] == template_name), None)
        if not selected_template:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Selected template not found.")
            return
        # Set the roles based on the template
        game_lock = game_locks.get(game_id)
        if not game_lock:
            game_lock = asyncio.Lock()
            game_locks[game_id] = game_lock
        async with game_lock:
            for role, count in selected_template['roles'].items():
                cursor.execute("""
                INSERT INTO GameRoles (game_id, role, count)
                VALUES (?, ?, ?)
                ON CONFLICT(game_id, role)
                DO UPDATE SET count=excluded.count
                """, (game_id, role, count))
            conn.commit()
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Template '{template_name}' has been applied.")
        # Refresh the role buttons to reflect the new counts
        await show_role_buttons(update, context, message_id)

    elif data.startswith("increase_"):
        role = data.split("_", 1)[1]
        logger.debug(f"Increase button pressed for role: {role}")
        if role not in available_roles:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Invalid role.")
            return
        if not game_id:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="No game selected.")
            return
        game_lock = game_locks.get(game_id)
        if not game_lock:
            game_lock = asyncio.Lock()
            game_locks[game_id] = game_lock
        async with game_lock:
            cursor.execute(
                "INSERT INTO GameRoles (game_id, role, count) VALUES (?, ?, 0) ON CONFLICT(game_id, role) DO UPDATE SET count = count + 1",
                (game_id, role)
            )
            conn.commit()
            await show_role_buttons(update, context, message_id)

    elif data.startswith("decrease_"):
        role = data.split("_", 1)[1]
        logger.debug(f"Decrease button pressed for role: {role}")
        if role not in available_roles:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Invalid role.")
            return
        if not game_id:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="No game selected.")
            return
        game_lock = game_locks.get(game_id)
        if not game_lock:
            game_lock = asyncio.Lock()
            game_locks[game_id] = game_lock
        async with game_lock:
            cursor.execute("SELECT count FROM GameRoles WHERE game_id = ? AND role = ?", (game_id, role))
            result = cursor.fetchone()
            current_count = result[0] if result else 0
            if current_count > 0:
                cursor.execute(
                    "UPDATE GameRoles SET count = count - 1 WHERE game_id = ? AND role = ?",
                    (game_id, role)
                )
                logger.debug(f"Role count for {role} decreased to {current_count - 1}")
            else:
                logger.debug(f"Role count for {role} is already 0. Cannot decrease further.")
            conn.commit()
            await show_role_buttons(update, context, message_id)

    elif data == "confirm_roles":
        logger.debug("confirm_roles button pressed.")
        if not game_id:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="No game selected.")
            return
        success, method = await confirm_and_set_roles(update, context, game_id)
        if not success:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Error setting roles. Please try again.")
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Roles have been confirmed and set successfully!\nRandomness source: {method}."
            )

    elif data == "confirm_roles_and_save_template":
        logger.debug("confirm_roles_and_save_template button pressed.")
        if not game_id:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="No game selected.")
            return
        # Confirm roles first
        success, method = await confirm_and_set_roles(update, context, game_id)
        if not success:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Error setting roles. Please try again.")
            return
        # Initiate the template confirmation process
        context.user_data['action'] = 'awaiting_template_name_confirmation'
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Please enter a name for this template.")

    elif data.startswith("maintainer_confirm_"):
        template_name_with_count = data[len("maintainer_confirm_"):]
        await handle_maintainer_confirmation(update, context, template_name_with_count, confirm=True)

    elif data.startswith("maintainer_reject_"):
        template_name_with_count = data[len("maintainer_reject_"):]
        await handle_maintainer_confirmation(update, context, template_name_with_count, confirm=False)

    elif data == "keep_name":
        logger.debug("keep_name button pressed.")
        context.user_data["action"] = "join_game"
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Please enter the passcode to join the game.")

    elif data == "change_name":
        logger.debug("change_name button pressed.")
        context.user_data["action"] = "awaiting_name"
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Please enter your new name.")

    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Unknown action.")

# Refactor to get roles, player count and then save template
# Removed get_roles_and_save_template since it's replaced by the new flow

async def handle_maintainer_confirmation(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, template_name_with_count: str, confirm: bool) -> None:
    user_id = update.effective_user.id
    if str(user_id) != str(MAINTAINER_ID):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="You are not authorized to perform this action.")
        return

    # Extract player_count from template_name_with_count
    if " - " not in template_name_with_count:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Invalid template format.")
        return

    template_name, player_count = template_name_with_count.rsplit(" - ", 1)
    player_count = player_count.strip()

    # Find and remove the template from pending_templates
    if player_count not in pending_templates:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No pending templates found for this player count.")
        return

    template = next((t for t in pending_templates[player_count] if t['name'] == template_name_with_count), None)
    if not template:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Template not found in pending templates.")
        return

    pending_templates[player_count].remove(template)

    if confirm:
        # Add to active templates
        if player_count not in role_templates:
            role_templates[player_count] = []
        role_templates[player_count].append(template)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Template '{template_name_with_count}' has been confirmed and added to active templates.")
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Template '{template_name_with_count}' has been rejected.")

    # Save the updated templates
    save_role_templates(role_templates, pending_templates)

    # TODO, notify the user who created the template
    # This requires tracking which user created which template, which isn't implemented here

# Create the handler instance
button_handler = CallbackQueryHandler(handle_button)