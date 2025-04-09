"""
Context management utilities for the Mafia Bot.
This module contains functions for managing user and chat data in the Telegram context.
"""

from typing import Dict, Any, Optional
import logging

logger = logging.getLogger("Mafia Bot Context")

# Define standard keys that are used in user_data
USER_DATA_KEYS = {
    # Core user identification
    'username': 'User's display name in the game',
    'user_id': 'Telegram user ID',
    
    # Game session tracking
    'game_id': 'Current game the user is participating in',
    'action': 'Current action the user is performing (awaiting_name, join_game, etc.)',
    
    # UI state
    'current_page': 'Current page in paginated interfaces (role selection)',
    
    # Game state
    'double_kill_night': 'Tracks double kill information for God Father role',
    'role': 'User's assigned role in the current game',
    'is_alive': 'Whether the user is alive in the current game',
    'target_selection': 'Temporary storage for target selection in actions',
}

def clear_user_data(context, keep_username=True, keep_keys=None) -> None:
    """
    Clears user data stored in context.user_data to prevent stale state.
    
    Args:
        context: The context object containing user_data
        keep_username: Whether to keep the username in user_data (default: True)
        keep_keys: Optional list of additional keys to preserve
    """
    # Create a backup of keys we want to keep
    preserved_data = {}
    
    # Store username if we want to keep it
    if keep_username and "username" in context.user_data:
        preserved_data["username"] = context.user_data.get("username")
    
    # Store any additional keys requested
    if keep_keys:
        for key in keep_keys:
            if key in context.user_data:
                preserved_data[key] = context.user_data.get(key)
    
    # Log what's being cleared for debugging
    removed_keys = set(context.user_data.keys()) - set(preserved_data.keys())
    if removed_keys:
        user_id = context.user_data.get("user_id", "unknown")
        logger.debug(f"Clearing user data for user {user_id}. Removed keys: {removed_keys}")
    
    # Clear all user data
    context.user_data.clear()
    
    # Restore preserved keys
    for key, value in preserved_data.items():
        context.user_data[key] = value

def get_game_data(context, game_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Get game-specific data from chat_data for the specified game.
    
    Args:
        context: The context object containing chat_data
        game_id: The game ID to get data for. If None, uses the game_id from user_data
        
    Returns:
        A dictionary containing the game data, or an empty dict if not found
    """
    if game_id is None:
        game_id = context.user_data.get('game_id')
        if not game_id:
            return {}
    
    games_data = context.chat_data.get('games', {})
    return games_data.get(game_id, {})

def set_game_data(context, game_data: Dict[str, Any], game_id: Optional[str] = None) -> None:
    """
    Set game-specific data in chat_data for the specified game.
    
    Args:
        context: The context object containing chat_data
        game_data: The game data to store
        game_id: The game ID to set data for. If None, uses the game_id from user_data
    """
    if game_id is None:
        game_id = context.user_data.get('game_id')
        if not game_id:
            return
    
    if 'games' not in context.chat_data:
        context.chat_data['games'] = {}
    
    context.chat_data['games'][game_id] = game_data