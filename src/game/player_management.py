from telegram.ext import ContextTypes
import logging
import json
from src.db import conn, cursor
from src.handlers.game_management.game_state_machine import GameState, state_machine

logger = logging.getLogger("Mafia Bot GameManagement.PlayerManagement")

async def update_player_elimination_status(game_id: str, user_id: int, eliminated: bool = True, cause: str = None) -> str:
    """
    Update a player's elimination status in the Roles table.
    
    Args:
        game_id: The ID of the game
        user_id: The ID of the player to update
        eliminated: True to mark as eliminated, False to mark as active
        cause: Optional cause of elimination for tracking purposes
        
    Returns:
        The username of the player
    """
    logger.debug(f"Updating player {user_id} eliminated status to {eliminated} in game {game_id}")
    
    # Get the player's username
    cursor.execute("SELECT username FROM Users WHERE user_id = ?", (user_id,))
    username_result = cursor.fetchone()
    username = username_result[0] if username_result else "Unknown"
    
    # Update the eliminated status in the Roles table
    if cause:
        # If we have a cause, store it in the metadata
        cursor.execute("SELECT metadata FROM Roles WHERE game_id = ? AND user_id = ?", (game_id, user_id))
        metadata_row = cursor.fetchone()
        metadata = {}
        
        if metadata_row and metadata_row[0]:
            try:
                metadata = json.loads(metadata_row[0])
            except:
                metadata = {}
        
        metadata['elimination_cause'] = cause
        metadata['elimination_time'] = 'night' if state_machine.get_game_state(game_id) in [GameState.NIGHT, GameState.NIGHT_RESOLVE] else 'day'
        
        cursor.execute(
            "UPDATE Roles SET eliminated = ?, metadata = ? WHERE game_id = ? AND user_id = ?",
            (1 if eliminated else 0, json.dumps(metadata), game_id, user_id)
        )
    else:
        cursor.execute(
            "UPDATE Roles SET eliminated = ? WHERE game_id = ? AND user_id = ?",
            (1 if eliminated else 0, game_id, user_id)
        )
    
    conn.commit()
    return username