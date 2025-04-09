"""
Module for handling Bartender role actions in the Mafia game.
The Bartender can intoxicate other players, potentially causing them to miss their night actions.
"""

import logging
import random
from src.database.connection import conn, cursor
from src.database.role_queries import get_player_role
from src.database.action_queries import get_player_action, get_actions_targeting_player

logger = logging.getLogger("Mafia Bot Actions.Bartender")

async def process_intoxication(game_id, phase, bartender_action):
    """
    Process the Bartender's intoxication action.
    When a player is intoxicated, there's a chance they will not perform their night action.
    
    Args:
        game_id (str): The game identifier
        phase (str): The game phase ('night')
        bartender_action (dict): The bartender's action data {user_id, target_id}
        
    Returns:
        dict: Results of the action with affected players and messages
    """
    if not bartender_action or not bartender_action.get('target_id'):
        logger.debug(f"No valid bartender action found for game {game_id}")
        return {"success": False, "message": "No valid bartender action"}
    
    bartender_id = bartender_action.get('user_id')
    target_id = bartender_action.get('target_id')
    
    # Get target's role
    target_role = get_player_role(game_id, target_id)
    if not target_role:
        logger.warning(f"Target {target_id} not found in game {game_id}")
        return {"success": False, "message": "Target not found"}
    
    # Check if target is immune to intoxication
    # Some roles might be immune to intoxication (like Godfather)
    if _is_immune_to_intoxication(target_role):
        logger.debug(f"Target {target_id} ({target_role}) is immune to intoxication")
        return {
            "success": True,
            "effective": False,
            "message": f"Player is immune to intoxication",
            "notifications": {
                bartender_id: "You attempted to intoxicate a player, but they seem resistant to your drinks!"
            }
        }
    
    # Check if the target has a scheduled action for this phase
    target_action = get_player_action(game_id, target_id, phase)
    if not target_action:
        logger.debug(f"Target {target_id} has no action in phase {phase}")
        return {
            "success": True,
            "effective": False,
            "message": f"Target had no action to block",
            "notifications": {
                bartender_id: "You served drinks to a player, but they weren't planning any actions anyway."
            }
        }
    
    # Apply intoxication effect - 75% chance of blocking the action
    intoxication_success = random.random() < 0.75
    
    if intoxication_success:
        # Record the intoxication in RoleStates table
        cursor.execute("""
        INSERT OR REPLACE INTO RoleStates (game_id, user_id, state_key, state_value)
        VALUES (?, ?, 'intoxicated', 'true')
        """, (game_id, target_id))
        conn.commit()
        
        logger.info(f"Player {target_id} was successfully intoxicated in game {game_id}")
        
        # Return the result
        return {
            "success": True,
            "effective": True,
            "action_blocked": True,
            "affected_player": target_id,
            "message": "Successfully intoxicated player - their action may fail",
            "notifications": {
                bartender_id: f"You successfully intoxicated a player. They might be too drunk to perform their action!",
                target_id: "You feel strangely disoriented after drinking at the town bar..."
            }
        }
    else:
        logger.debug(f"Intoxication attempt on {target_id} failed (RNG)")
        return {
            "success": True,
            "effective": False,
            "message": "Player resisted intoxication",
            "notifications": {
                bartender_id: "Your target seems to hold their liquor well. The intoxication had no effect."
            }
        }

def check_intoxication_effect(game_id, user_id):
    """
    Check if a player is too intoxicated to perform their action.
    
    Args:
        game_id (str): The game identifier
        user_id (int): The player ID
        
    Returns:
        bool: True if the player is too intoxicated to act, False otherwise
    """
    # Check if player is marked as intoxicated
    cursor.execute("""
    SELECT 1 FROM RoleStates 
    WHERE game_id = ? AND user_id = ? AND state_key = 'intoxicated' AND state_value = 'true'
    LIMIT 1
    """, (game_id, user_id))
    
    is_intoxicated = cursor.fetchone() is not None
    
    # If intoxicated, there's a 75% chance they're too drunk to act
    if is_intoxicated:
        too_drunk = random.random() < 0.75
        
        # Clear the intoxication state after checking (one-night effect)
        cursor.execute("""
        DELETE FROM RoleStates 
        WHERE game_id = ? AND user_id = ? AND state_key = 'intoxicated'
        """, (game_id, user_id))
        conn.commit()
        
        return too_drunk
    
    return False

def _is_immune_to_intoxication(role):
    """
    Check if a role is immune to intoxication effects.
    
    Args:
        role (str): The role name
        
    Returns:
        bool: True if the role is immune, False otherwise
    """
    # List of roles that can't be intoxicated
    immune_roles = [
        "Godfather",  # The Godfather is too powerful to be affected
        "Teetotaler", # This role specifically doesn't drink
        "Bartender"   # The Bartender knows his own tricks
    ]
    
    return role in immune_roles