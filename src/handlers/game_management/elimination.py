
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import logging
from src.db import conn, cursor
from src.handlers.game_management.voting import process_voting_results, game_voting_data

logger = logging.getLogger("Mafia Bot GameManagement.Elimination")

async def eliminate_player(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str) -> None:
    logger.debug("Initiating player elimination process.")
    
    # Fetch active (non-eliminated) players
    cursor.execute("""
        SELECT Roles.user_id, Users.username
        FROM Roles
        JOIN Users ON Roles.user_id = Users.user_id
        WHERE Roles.game_id = ? AND Roles.eliminated = 0
    """, (game_id,))
    players = cursor.fetchall()
    
    if not players:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No active players to eliminate.")
        return
    
    # Create elimination buttons for each player
    keyboard = []
    for user_id, username in players:
        keyboard.append([InlineKeyboardButton(username, callback_data=f"eliminate_confirm_{user_id}")])
    
    # Add a back button
    keyboard.append([InlineKeyboardButton("Back to Manage Games", callback_data="manage_games")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Select a player to eliminate:", reply_markup=reply_markup)

async def handle_elimination_confirmation(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str, target_user_id: int) -> None:
    logger.debug(f"Handling elimination confirmation for user ID {target_user_id} in game ID {game_id}.")
    
    # Fetch the username of the target user
    cursor.execute("SELECT username FROM Users WHERE user_id = ?", (target_user_id,))
    result = cursor.fetchone()
    if not result:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="User not found.")
        return
    username = result[0]
    
    # Ask for confirmation
    keyboard = [
        [InlineKeyboardButton("Yes, Eliminate", callback_data=f"eliminate_yes_{target_user_id}")],
        [InlineKeyboardButton("Cancel", callback_data=f"eliminate_cancel_{target_user_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Are you sure you want to eliminate {username}?", reply_markup=reply_markup)

async def confirm_elimination(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str, target_user_id: int) -> None:
    logger.debug(f"Confirming elimination for user ID {target_user_id} in game ID {game_id}.")
    
    # Mark the player as eliminated in the database
    cursor.execute("""
        UPDATE Roles
        SET eliminated = 1
        WHERE game_id = ? AND user_id = ?
    """, (game_id, target_user_id))
    conn.commit()
    
    # Fetch the username of the eliminated player
    cursor.execute("SELECT username FROM Users WHERE user_id = ?", (target_user_id,))
    result = cursor.fetchone()
    username = result[0] if result else "Unknown"
    
    # Notify the moderator
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"{username} has been eliminated from the game.")
    
    # Notify the eliminated player
    try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text="You have been eliminated from the game. Better luck next time!"
        )
    except Exception as e:
        logger.error(f"Failed to notify user {target_user_id} about elimination: {e}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Failed to notify {username} about their elimination.")

    # Remove the eliminated player from any ongoing voting session
    if game_id in game_voting_data:
        if target_user_id in game_voting_data[game_id]['voters']:
            game_voting_data[game_id]['voters'].remove(target_user_id)
        if target_user_id in game_voting_data[game_id]['player_votes']:
            del game_voting_data[game_id]['player_votes'][target_user_id]
        # Optionally, re-check if all voters have voted after removal
        if not game_voting_data[game_id]['voters']:
            await process_voting_results(update, context, game_id)

async def cancel_elimination(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str, target_user_id: int) -> None:
    logger.debug(f"Elimination of user ID {target_user_id} in game ID {game_id} has been canceled.")
    
    # Fetch the username of the target user
    cursor.execute("SELECT username FROM Users WHERE user_id = ?", (target_user_id,))
    result = cursor.fetchone()
    username = result[0] if result else "Unknown"
    
    # Notify the moderator
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Elimination of {username} has been canceled.")
