"""
Game joining logic module.
Handles the process of users joining an existing game.
"""

import logging
from telegram.ext import ContextTypes
from src.database.game_queries import get_game_by_passcode, get_moderator_id
from src.database.user_queries import upsert_user
from src.database.role_queries import set_player_role
from src.utils.context import clear_user_data

logger = logging.getLogger("Mafia Bot GameSetup.Join")

async def join_game(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, passcode: str) -> None:
    """
    Handle a user's attempt to join a game using a passcode.
    
    Args:
        update: The telegram update object
        context: The telegram context object
        passcode: The game passcode entered by the user
    
    Returns:
        None
    """
    logger.debug("User attempting to join a game.")
    user_id = update.effective_user.id
    username = context.user_data.get("username", f"User{user_id}")
    
    # Clear user data but keep username before joining a new game
    clear_user_data(context)
    context.user_data["username"] = username

    # Check if game exists and has not started
    game = get_game_by_passcode(passcode)
    if not game:
        message = "Invalid passcode. Please try again."
        await context.bot.send_message(chat_id=update.effective_chat.id, text=message)
        return
    
    game_id, _, moderator_id, state, _ = game  # Unpack the game information
    
    # Check if game has already started
    if state != 'SETUP':
        logger.debug(f"Attempt to join game in non-SETUP state: {game_id}, state: {state}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Cannot join. The game has already started.")
        return
    
    # Store game_id in user_data
    context.user_data['game_id'] = game_id
    logger.debug(f"User joined game. game_id stored in user_data: {game_id}")

    # Update or insert user information
    upsert_user(user_id, username)
    
    # Add player to the game's roles table with NULL role (will be assigned later)
    set_player_role(game_id, user_id, None)
    
    # Send success message to the user
    message = "Joined the game successfully!"
    await context.bot.send_message(chat_id=update.effective_chat.id, text=message)
    logger.debug(f"User {username} (ID: {user_id}) joined game {game_id}")

    # Notify moderator if the joining user is not the moderator
    if moderator_id != user_id:
        try:
            await context.bot.send_message(chat_id=moderator_id, text=f"User {username} (ID: {user_id}) has joined the game!")
        except Exception as e:
            logger.error(f"Failed to notify moderator {moderator_id}: {e}")