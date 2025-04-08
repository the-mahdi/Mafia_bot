from telegram import Update
from telegram.ext import ContextTypes
import logging
import asyncio
from src.db import conn, cursor
from src.roles import available_roles
from src.handlers.game_management import show_role_buttons, confirm_and_set_roles

logger = logging.getLogger("Mafia Bot RoleSetupCallbacks")

# Initialize a dictionary to store locks for each game
game_locks = {}

async def handle_increase_role(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the 'increase_[role]' callback queries."""
    query = update.callback_query
    data = query.data
    message_id = query.message.message_id
    role = data.split("_", 1)[1]
    game_id = context.user_data.get('game_id')
    
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
            "INSERT INTO GameRoles (game_id, role, count) VALUES (?, ?, 0) "
            "ON CONFLICT(game_id, role) DO UPDATE SET count = count + 1",
            (game_id, role)
        )
        conn.commit()
    
    await show_role_buttons(update, context, message_id)

async def handle_decrease_role(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the 'decrease_[role]' callback queries."""
    query = update.callback_query
    data = query.data
    message_id = query.message.message_id
    role = data.split("_", 1)[1]
    game_id = context.user_data.get('game_id')
    
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

async def handle_prev_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the 'prev_page' callback query."""
    query = update.callback_query
    message_id = query.message.message_id
    
    logger.debug("Previous page button pressed.")
    current_page = context.user_data.get('current_page', 0)
    context.user_data['current_page'] = max(0, current_page - 1)
    await show_role_buttons(update, context, message_id)

async def handle_next_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the 'next_page' callback query."""
    query = update.callback_query
    message_id = query.message.message_id
    
    logger.debug("Next page button pressed.")
    current_page = context.user_data.get('current_page', 0)
    context.user_data['current_page'] = current_page + 1
    await show_role_buttons(update, context, message_id)

async def handle_reset_roles(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the 'reset_roles' callback query."""
    query = update.callback_query
    message_id = query.message.message_id
    game_id = context.user_data.get('game_id')
    
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
                "INSERT INTO GameRoles (game_id, role, count) VALUES (?, ?, 0) "
                "ON CONFLICT(game_id, role) DO UPDATE SET count=0",
                (game_id, role)
            )
        conn.commit()
        context.user_data['current_page'] = 0
        await show_role_buttons(update, context, message_id)

async def handle_confirm_roles(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the 'confirm_roles' callback query."""
    game_id = context.user_data.get('game_id')
    
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

async def handle_confirm_roles_and_save_template(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the 'confirm_roles_and_save_template' callback query."""
    game_id = context.user_data.get('game_id')
    
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

async def handle_template_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the 'template_[name]' callback queries."""
    query = update.callback_query
    data = query.data
    message_id = query.message.message_id
    template_name = data.split("template_", 1)[1]
    game_id = context.user_data.get('game_id')
    
    logger.debug(f"Template selected: {template_name}")
    if not game_id:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No game selected.")
        return
    
    # Find the selected template
    from src.handlers.game_management import get_player_count, get_templates_for_player_count
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

async def handle_select_template(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the 'select_template' callback query."""
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    from src.handlers.game_management import get_player_count, get_templates_for_player_count
    
    game_id = context.user_data.get('game_id')
    
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