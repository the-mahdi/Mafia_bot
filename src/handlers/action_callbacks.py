from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import logging
from src.db import conn, cursor

logger = logging.getLogger("Mafia Bot ActionCallbacks")

async def handle_action_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for action prompts (buttons ending with '_prompt_[game_id]')."""
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id
    
    # Extract the action_command and game_id from the callback data
    parts = data.split("_prompt_")
    if len(parts) != 2:
        await context.bot.send_message(chat_id=user_id, text="Invalid action prompt.")
        return
    
    action_command = parts[0]
    game_id = parts[1]
    
    # Check if the player can perform actions
    cursor.execute("SELECT role, eliminated FROM Roles WHERE game_id = ? AND user_id = ?", (game_id, user_id))
    result = cursor.fetchone()
    if not result or result[1] == 1:
        await context.bot.send_message(chat_id=user_id, text="You cannot perform actions.")
        return
    
    role = result[0]
    
    # Get current phase
    cursor.execute("SELECT current_phase FROM Games WHERE game_id = ?", (game_id,))
    phase = cursor.fetchone()[0]
    
    # Get role actions
    from src.roles import role_actions
    actions = role_actions.get(role, {}).get(phase, [])
    action = next((a for a in actions if a['command'] == action_command), None)
    
    if not action:
        await context.bot.send_message(chat_id=user_id, text="Invalid action.")
        return
    
    if action.get('targets', 0) == 0:
        await perform_action(update, context, game_id, user_id, action_command, None)
    else:
        # Show target selection
        cursor.execute("SELECT user_id, username FROM Users JOIN Roles ON Users.user_id = Roles.user_id WHERE game_id = ? AND eliminated = 0", (game_id,))
        players = cursor.fetchall()
        keyboard = [
            [InlineKeyboardButton(username, callback_data=f"{action_command}_{target_id}_{game_id}")]
            for target_id, username in players if action.get('self_target', False) or target_id != user_id
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=user_id,
            text=f"Select a target for {action.get('name', action_command)}:",
            reply_markup=reply_markup
        )

async def handle_action_target(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for action targets (buttons with format '[action]_[target_id]_[game_id]')."""
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id
    
    # Check if this is a properly formatted action target callback
    parts = data.split("_")
    if len(parts) < 3:
        await context.bot.send_message(chat_id=user_id, text="Invalid action target.")
        return
    
    action_command = parts[0]
    target_id = int(parts[1])
    game_id = parts[2]
    
    await perform_action(update, context, game_id, user_id, action_command, target_id)

async def handle_double_kill_first(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the first target of a double kill."""
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id
    
    # Extract first_target_id and game_id
    parts = data.split("_")
    if len(parts) < 5:
        await context.bot.send_message(chat_id=user_id, text="Invalid double kill first target.")
        return
    
    first_target_id = int(parts[3])
    game_id = parts[4]
    
    logger.debug(f"Godfather selected first kill target: {first_target_id} in game {game_id}")
    
    # Store the first target in user_data
    if 'double_kill_targets' not in context.user_data:
        context.user_data['double_kill_targets'] = {}
    context.user_data['double_kill_targets']['first'] = first_target_id
    
    # Fetch remaining players for second target
    cursor.execute("""
        SELECT r.user_id, u.username 
        FROM Roles r 
        JOIN Users u ON r.user_id = u.user_id 
        WHERE r.game_id = ? AND r.eliminated = 0 AND r.user_id != ? AND r.user_id != ?
    """, (game_id, user_id, first_target_id))
    
    potential_targets = cursor.fetchall()
    
    # Create a button grid for the second kill target
    keyboard = []
    for target_id, target_name in potential_targets:
        keyboard.append([InlineKeyboardButton(
            f"{target_name}", 
            callback_data=f"double_kill_second_{target_id}_{game_id}"
        )])
    
    keyboard.append([InlineKeyboardButton("Pass", callback_data=f"pass_{game_id}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=user_id,
        text="Now select your SECOND kill target:",
        reply_markup=reply_markup
    )

async def handle_double_kill_second(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the second target of a double kill."""
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id
    
    # Extract second_target_id and game_id
    parts = data.split("_")
    if len(parts) < 5:
        await context.bot.send_message(chat_id=user_id, text="Invalid double kill second target.")
        return
    
    second_target_id = int(parts[3])
    game_id = parts[4]
    
    logger.debug(f"Godfather selected second kill target: {second_target_id} in game {game_id}")
    
    # Get the first target from user_data
    first_target_id = context.user_data.get('double_kill_targets', {}).get('first')
    
    if first_target_id:
        # Record both kill actions
        try:
            cursor.execute("BEGIN TRANSACTION")
            # Record first kill
            cursor.execute(
                "INSERT OR REPLACE INTO Actions (game_id, user_id, phase, action, target_id) VALUES (?, ?, ?, ?, ?)",
                (game_id, user_id, "NIGHT", "kill", first_target_id)
            )
            
            # Record second kill with a special action to differentiate it
            cursor.execute(
                "INSERT OR REPLACE INTO Actions (game_id, user_id, phase, action, target_id) VALUES (?, ?, ?, ?, ?)",
                (game_id, user_id, "NIGHT", "kill", second_target_id)
            )
            
            cursor.execute("COMMIT")
            logger.debug(f"Recorded double kill targets: {first_target_id} and {second_target_id}")
            
            # Clean up user_data
            if 'double_kill_targets' in context.user_data:
                del context.user_data['double_kill_targets']
            if 'double_kill_night' in context.user_data:
                del context.user_data['double_kill_night']
            
            await context.bot.send_message(
                chat_id=user_id,
                text=f"You have selected your targets for the night. Your fury will be unleashed!"
            )
        except Exception as e:
            cursor.execute("ROLLBACK")
            logger.error(f"Error recording double kill: {e}")
            await context.bot.send_message(
                chat_id=user_id,
                text="There was an error recording your targets. Please try again or contact the moderator."
            )
    else:
        await context.bot.send_message(
            chat_id=user_id,
            text="Error: First target not found. Please try again or contact the moderator."
        )

async def perform_action(update: Update, context: ContextTypes.DEFAULT_TYPE, game_id: str, user_id: int, action_command: str, target_id: int):
    """Record the player's action in the Actions table."""
    cursor.execute("SELECT role FROM Roles WHERE game_id = ? AND user_id = ?", (game_id, user_id))
    role = cursor.fetchone()[0]
    phase = cursor.execute("SELECT current_phase FROM Games WHERE game_id = ?", (game_id,)).fetchone()[0]
    
    # Get role actions
    from src.roles import role_actions
    actions = role_actions.get(role, {}).get(phase, [])
    action = next((a for a in actions if a['command'] == action_command), None)
    
    if not action:
        await context.bot.send_message(chat_id=user_id, text="Invalid action.")
        return
    
    # Record action
    cursor.execute(
        "INSERT OR REPLACE INTO Actions (game_id, user_id, phase, action, target_id) VALUES (?, ?, ?, ?, ?)",
        (game_id, user_id, phase, action_command, target_id)
    )
    conn.commit()
    
    target_text = f"User {target_id}" if target_id else "no target"
    await context.bot.send_message(
        chat_id=user_id, 
        text=f"You chose to {action.get('name', action_command)} {target_text}."
    )