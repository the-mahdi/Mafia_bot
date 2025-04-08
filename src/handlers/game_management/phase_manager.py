from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import logging
from src.db import conn, cursor
from src.roles import role_actions

logger = logging.getLogger("Mafia Bot PhaseManager")

async def start_night_phase(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str):
    """Start the night phase, sending action prompts to players."""
    logger.debug(f"Starting night phase for game {game_id}")
    
    # Update game phase
    cursor.execute("UPDATE Games SET current_phase = 'night' WHERE game_id = ?", (game_id,))
    # Clear previous night actions
    cursor.execute("DELETE FROM Actions WHERE game_id = ? AND phase = 'night'", (game_id,))
    conn.commit()
    
    # Fetch active players
    cursor.execute("SELECT user_id, role FROM Roles WHERE game_id = ? AND eliminated = 0", (game_id,))
    players = cursor.fetchall()
    
    for user_id, role in players:
        actions = role_actions.get(role, {}).get('night', [])
        interactive_actions = [action for action in actions if action.get('interactive') == 'button']
        
        if interactive_actions:
            keyboard = [
                [InlineKeyboardButton(action['description'], callback_data=f"{action['command']}_prompt_{game_id}")]
                for action in interactive_actions
            ]
            keyboard.append([InlineKeyboardButton("Pass", callback_data=f"pass_{game_id}")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(
                chat_id=user_id,
                text=f"Night begins! Choose your action for {role}:",
                reply_markup=reply_markup
            )
        else:
            await context.bot.send_message(
                chat_id=user_id,
                text="Night begins! You have no actions this phase."
            )
    
    # Notify moderator
    cursor.execute("SELECT moderator_id FROM Games WHERE game_id = ?", (game_id,))
    moderator_id = cursor.fetchone()[0]
    await context.bot.send_message(
        chat_id=moderator_id,
        text="Night phase started. Players are choosing their actions."
    )

async def resolve_night_actions(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str):
    """Resolve all night actions and transition to day phase."""
    logger.debug(f"Resolving night actions for game {game_id}")
    
    # Fetch all night actions
    cursor.execute("SELECT user_id, action, target_id FROM Actions WHERE game_id = ? AND phase = 'night'", (game_id,))
    actions = cursor.fetchall()
    
    kill_targets = set()
    healed_players = set()
    
    # Process actions (basic implementation for kill and heal)
    for user_id, action, target_id in actions:
        if action == "kill":
            if target_id:
                kill_targets.add(target_id)
        elif action == "heal":
            if target_id:
                healed_players.add(target_id)
        elif action == "investigate":
            cursor.execute("SELECT role FROM Roles WHERE game_id = ? AND user_id = ?", (game_id, target_id))
            target_role = cursor.fetchone()[0]
            faction = role_actions[target_role]['faction']
            result = "Mafia" if faction == "Mafia" and target_role != "God F" else "Not Mafia"
            await context.bot.send_message(
                chat_id=user_id,
                text=f"Investigation result: User {target_id} is {result}."
            )
    
    # Apply kills, considering heals
    for target_id in kill_targets:
        if target_id not in healed_players:
            cursor.execute("UPDATE Roles SET eliminated = 1 WHERE game_id = ? AND user_id = ?", (game_id, target_id))
            cursor.execute("SELECT username FROM Users WHERE user_id = ?", (target_id,))
            username = cursor.fetchone()[0]
            await context.bot.send_message(chat_id=target_id, text="You have been eliminated!")
    
    conn.commit()
    
    # Clear night actions
    cursor.execute("DELETE FROM Actions WHERE game_id = ? AND phase = 'night'", (game_id,))
    conn.commit()
    
    # Notify players of eliminations
    cursor.execute("SELECT user_id FROM Roles WHERE game_id = ? AND eliminated = 0", (game_id,))
    alive_players = [row[0] for row in cursor.fetchall()]
    for user_id in alive_players:
        await context.bot.send_message(chat_id=user_id, text="Night has ended. Check the game status.")
    
    # Proceed to day phase
    await start_day_phase(update, context, game_id)

async def start_day_phase(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str):
    """Start the day phase, sending action prompts and preparing for voting."""
    logger.debug(f"Starting day phase for game {game_id}")
    
    cursor.execute("UPDATE Games SET current_phase = 'day' WHERE game_id = ?", (game_id,))
    cursor.execute("DELETE FROM Actions WHERE game_id = ? AND phase = 'day'", (game_id,))
    conn.commit()
    
    # Fetch active players
    cursor.execute("SELECT user_id, role FROM Roles WHERE game_id = ? AND eliminated = 0", (game_id,))
    players = cursor.fetchall()
    
    for user_id, role in players:
        actions = role_actions.get(role, {}).get('day', [])
        interactive_actions = [action for action in actions if action.get('interactive') == 'button']
        
        if interactive_actions:
            keyboard = [
                [InlineKeyboardButton(action['description'], callback_data=f"{action['command']}_prompt_{game_id}")]
                for action in interactive_actions
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(
                chat_id=user_id,
                text=f"Day begins! Choose your action for {role}:",
                reply_markup=reply_markup
            )
        else:
            await context.bot.send_message(chat_id=user_id, text="Day begins! Discuss and prepare for voting.")
    
    # Notify moderator
    cursor.execute("SELECT moderator_id FROM Games WHERE game_id = ?", (game_id,))
    moderator_id = cursor.fetchone()[0]
    await context.bot.send_message(
        chat_id=moderator_id,
        text="Day phase started. Players can discuss and vote."
    )

async def resolve_day_actions(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str):
    """Resolve day actions (excluding voting, handled separately)."""
    logger.debug(f"Resolving day actions for game {game_id}")
    
    cursor.execute("SELECT user_id, action, target_id FROM Actions WHERE game_id = ? AND phase = 'day'", (game_id,))
    actions = cursor.fetchall()
    
    for user_id, action, target_id in actions:
        if action == "vote":
            # Voting is handled separately in voting.py
            continue
        # Add logic for other day actions as needed
    
    conn.commit()
    cursor.execute("DELETE FROM Actions WHERE game_id = ? AND phase = 'day'", (game_id,))
    conn.commit()