"""
Game state helper functions for working with the GameStateMachine.

This module provides helper functions for interacting with the game state machine
to ensure it's the single source of truth for game phase information.
"""

import logging
from typing import Optional, Any, Dict, List
from telegram.ext import ContextTypes

# Import the state machine - this assumes it's already been moved to src/game/state_machine.py
# as specified in the modularization plan
from src.handlers.game_management.game_state_machine import state_machine, GameState

logger = logging.getLogger("Mafia Bot State Helpers")

def get_current_phase(game_id: str) -> GameState:
    """
    Get the current game phase using the GameStateMachine.
    
    Args:
        game_id: The ID of the game to get the phase for
        
    Returns:
        The current GameState for the specified game
    """
    return state_machine.get_game_state(game_id)

def is_game_in_phase(game_id: str, phase: GameState) -> bool:
    """
    Check if a game is currently in a specific phase.
    
    Args:
        game_id: The ID of the game to check
        phase: The GameState to check against
        
    Returns:
        True if the game is in the specified phase, False otherwise
    """
    return state_machine.get_game_state(game_id) == phase

def is_game_in_phases(game_id: str, phases: List[GameState]) -> bool:
    """
    Check if a game is currently in any of the specified phases.
    
    Args:
        game_id: The ID of the game to check
        phases: List of GameStates to check against
        
    Returns:
        True if the game is in any of the specified phases, False otherwise
    """
    return state_machine.get_game_state(game_id) in phases

def get_phase_description(phase: GameState) -> str:
    """
    Get a human-readable description of a game phase.
    
    Args:
        phase: The GameState to describe
        
    Returns:
        A string describing the phase
    """
    descriptions = {
        GameState.PRE_GAME: "Pre-Game Setup",
        GameState.NIGHT: "Night (Action Selection)",
        GameState.NIGHT_RESOLVE: "Night (Resolving Actions)",
        GameState.DAY_ANNOUNCE: "Day (Announcing Results)",
        GameState.DAY_DISCUSS: "Day (Discussion)",
        GameState.VOTING: "Day (Voting)",
        GameState.VOTE_RESOLVE: "Day (Resolving Votes)",
        GameState.CHECK_WIN: "Checking Win Conditions",
        GameState.GAME_OVER: "Game Over"
    }
    return descriptions.get(phase, f"Unknown Phase ({phase.name})")

def validate_action_for_phase(game_id: str, action_type: str, allowed_phases: List[GameState]) -> bool:
    """
    Validates if an action is allowed in the current game phase.
    
    Args:
        game_id: The ID of the game to check
        action_type: The type of action being performed (for logging)
        allowed_phases: List of GameStates where the action is allowed
        
    Returns:
        True if the action is allowed in the current phase, False otherwise
    """
    current_phase = state_machine.get_game_state(game_id)
    is_allowed = current_phase in allowed_phases
    
    if not is_allowed:
        logger.warning(
            f"Action '{action_type}' attempted in game {game_id} during {current_phase.name} phase, "
            f"but is only allowed in: {', '.join([p.name for p in allowed_phases])}"
        )
    
    return is_allowed

async def ensure_game_context(update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
    """
    Ensures that a valid game context exists in user_data.
    
    This is a helper function to standardize how we check for and validate
    that a user is in a valid game context before processing commands.
    
    Args:
        update: The update object from Telegram
        context: The context object from Telegram
        
    Returns:
        The game_id if valid, None otherwise (and sends an error message)
    """
    from telegram import Update
    
    # Check if user has a game_id
    game_id = context.user_data.get('game_id')
    if not game_id:
        await update.callback_query.answer("No active game found. Please join or create a game first.")
        return None
    
    # Verify game exists in state machine
    try:
        state_machine.get_game_state(game_id)
        return game_id
    except Exception as e:
        logger.error(f"Error retrieving game state for game {game_id}: {e}")
        await update.callback_query.answer("Error: Game not found. Please start a new game.")
        return None