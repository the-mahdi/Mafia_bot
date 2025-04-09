"""
Database query functions for game actions operations.
This module centralizes all database operations related to night and day actions.
"""

import logging
from src.database.connection import conn, cursor

logger = logging.getLogger("Mafia Bot Database.ActionQueries")

def record_action(game_id, user_id, phase, action, target_id=None):
    """
    Record a player's action for a specific phase.
    Replaces any existing action for that player in that phase.
    
    Args:
        game_id (str): The game identifier
        user_id (int): The player performing the action
        phase (str): The game phase ('night' or 'day')
        action (str): The action command/type
        target_id (int, optional): The target player's ID, if any
    """
    # Delete any existing action for this player in this phase
    cursor.execute("""
    DELETE FROM Actions 
    WHERE game_id = ? AND user_id = ? AND phase = ?
    """, (game_id, user_id, phase))
    
    # Insert the new action
    cursor.execute("""
    INSERT INTO Actions (game_id, user_id, phase, action, target_id)
    VALUES (?, ?, ?, ?, ?)
    """, (game_id, user_id, phase, action, target_id))
    
    conn.commit()
    logger.debug(f"Recorded action for game {game_id}, user {user_id}, phase {phase}: {action} -> {target_id}")

def get_player_action(game_id, user_id, phase):
    """
    Get a player's action for a specific phase.
    
    Args:
        game_id (str): The game identifier
        user_id (int): The player ID
        phase (str): The game phase ('night' or 'day')
        
    Returns:
        tuple: (action, target_id) or None if no action found
    """
    cursor.execute("""
    SELECT action, target_id FROM Actions
    WHERE game_id = ? AND user_id = ? AND phase = ?
    """, (game_id, user_id, phase))
    
    result = cursor.fetchone()
    return result if result else None

def get_phase_actions(game_id, phase):
    """
    Get all actions for a specific phase in a game.
    
    Args:
        game_id (str): The game identifier
        phase (str): The game phase ('night' or 'day')
        
    Returns:
        list: List of tuples (user_id, action, target_id)
    """
    cursor.execute("""
    SELECT user_id, action, target_id FROM Actions
    WHERE game_id = ? AND phase = ?
    """, (game_id, phase))
    
    return cursor.fetchall()

def get_actions_by_type(game_id, phase, action_type):
    """
    Get all actions of a specific type for a phase in a game.
    
    Args:
        game_id (str): The game identifier
        phase (str): The game phase ('night' or 'day')
        action_type (str): The type of action to filter by
        
    Returns:
        list: List of tuples (user_id, target_id)
    """
    cursor.execute("""
    SELECT user_id, target_id FROM Actions
    WHERE game_id = ? AND phase = ? AND action = ?
    """, (game_id, phase, action_type))
    
    return cursor.fetchall()

def get_actions_targeting_player(game_id, phase, target_id):
    """
    Get all actions targeting a specific player in a phase.
    
    Args:
        game_id (str): The game identifier
        phase (str): The game phase ('night' or 'day')
        target_id (int): The ID of the targeted player
        
    Returns:
        list: List of tuples (user_id, action)
    """
    cursor.execute("""
    SELECT user_id, action FROM Actions
    WHERE game_id = ? AND phase = ? AND target_id = ?
    """, (game_id, phase, target_id))
    
    return cursor.fetchall()

def get_detailed_phase_actions(game_id, phase):
    """
    Get detailed information about all actions in a phase, including player names.
    
    Args:
        game_id (str): The game identifier
        phase (str): The game phase ('night' or 'day')
        
    Returns:
        list: List of tuples (user_id, username, action, target_id, target_username)
    """
    cursor.execute("""
    SELECT a.user_id, u1.username, a.action, a.target_id, u2.username
    FROM Actions a
    JOIN Users u1 ON a.user_id = u1.user_id
    LEFT JOIN Users u2 ON a.target_id = u2.user_id
    WHERE a.game_id = ? AND a.phase = ?
    """, (game_id, phase))
    
    return cursor.fetchall()

def clear_phase_actions(game_id, phase):
    """
    Clear all actions for a specific phase in a game.
    
    Args:
        game_id (str): The game identifier
        phase (str): The game phase ('night' or 'day')
    """
    cursor.execute("""
    DELETE FROM Actions 
    WHERE game_id = ? AND phase = ?
    """, (game_id, phase))
    
    conn.commit()
    logger.debug(f"Cleared all {phase} actions for game {game_id}")

def clear_all_actions(game_id):
    """
    Clear all actions for a game (both phases).
    
    Args:
        game_id (str): The game identifier
    """
    cursor.execute("""
    DELETE FROM Actions 
    WHERE game_id = ?
    """, (game_id,))
    
    conn.commit()
    logger.debug(f"Cleared all actions for game {game_id}")

def check_player_action_exists(game_id, user_id, phase):
    """
    Check if a player has recorded an action for a specific phase.
    
    Args:
        game_id (str): The game identifier
        user_id (int): The player ID
        phase (str): The game phase ('night' or 'day')
        
    Returns:
        bool: True if an action exists, False otherwise
    """
    cursor.execute("""
    SELECT 1 FROM Actions
    WHERE game_id = ? AND user_id = ? AND phase = ?
    LIMIT 1
    """, (game_id, user_id, phase))
    
    return cursor.fetchone() is not None

def count_pending_actions(game_id, phase, eligible_players):
    """
    Count how many players still need to submit actions for a phase.
    
    Args:
        game_id (str): The game identifier
        phase (str): The game phase ('night' or 'day')
        eligible_players (list): List of player IDs who are eligible to perform actions
        
    Returns:
        int: Number of players who haven't submitted actions yet
    """
    # Convert list to tuple for SQL IN clause
    if not eligible_players:
        return 0
        
    placeholders = ','.join('?' for _ in eligible_players)
    
    cursor.execute(f"""
    SELECT COUNT(DISTINCT user_id) FROM Actions
    WHERE game_id = ? AND phase = ? AND user_id IN ({placeholders})
    """, (game_id, phase, *eligible_players))
    
    actions_submitted = cursor.fetchone()[0]
    return len(eligible_players) - actions_submitted

def get_player_role_action(game_id, user_id, phase, player_role):
    """
    Get a player's action combined with their role information.
    
    Args:
        game_id (str): The game identifier
        user_id (int): The player ID
        phase (str): The game phase ('night' or 'day')
        player_role (str): The player's role
        
    Returns:
        dict: Dictionary with role, action, and target information
    """
    action_data = get_player_action(game_id, user_id, phase)
    if not action_data:
        return {
            'user_id': user_id,
            'role': player_role,
            'action': None,
            'target_id': None
        }
    
    return {
        'user_id': user_id,
        'role': player_role,
        'action': action_data[0],
        'target_id': action_data[1]
    }

# Functions for Complex Actions (using extended schema)

def record_complex_action(game_id, user_id, phase, action, parameters=None, expires_at=None):
    """
    Record a complex action that may have multiple parameters or targets.
    
    Args:
        game_id (str): The game identifier
        user_id (int): The player performing the action
        phase (str): The game phase ('night' or 'day')
        action (str): The action command/type
        parameters (dict, optional): Additional parameters as JSON
        expires_at (str, optional): Timestamp when the action expires
        
    Returns:
        int: The ID of the newly created complex action
    """
    import json
    
    params_json = json.dumps(parameters) if parameters else '{}'
    
    cursor.execute("""
    INSERT INTO ComplexActions (game_id, user_id, phase, action, parameters, expires_at)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (game_id, user_id, phase, action, params_json, expires_at))
    
    conn.commit()
    action_id = cursor.lastrowid
    logger.debug(f"Recorded complex action ID {action_id} for game {game_id}, user {user_id}, phase {phase}: {action}")
    
    return action_id

def add_action_target(action_id, target_id, order=0):
    """
    Add a target to a complex action.
    
    Args:
        action_id (int): The complex action ID
        target_id (int): The target player ID
        order (int, optional): The order of this target (for multi-target actions)
    """
    cursor.execute("""
    INSERT INTO ActionTargets (action_id, target_id, target_order)
    VALUES (?, ?, ?)
    """, (action_id, target_id, order))
    
    conn.commit()
    logger.debug(f"Added target {target_id} (order {order}) to complex action {action_id}")

def get_complex_action(action_id):
    """
    Get details of a complex action by its ID.
    
    Args:
        action_id (int): The complex action ID
        
    Returns:
        dict: Action details including targets, or None if not found
    """
    import json
    
    cursor.execute("""
    SELECT game_id, user_id, phase, action, parameters, created_at, expires_at, resolved
    FROM ComplexActions
    WHERE action_id = ?
    """, (action_id,))
    
    action_data = cursor.fetchone()
    if not action_data:
        return None
        
    # Get targets for this action
    cursor.execute("""
    SELECT target_id, target_order
    FROM ActionTargets
    WHERE action_id = ?
    ORDER BY target_order
    """, (action_id,))
    
    targets = cursor.fetchall()
    
    return {
        'action_id': action_id,
        'game_id': action_data[0],
        'user_id': action_data[1],
        'phase': action_data[2],
        'action': action_data[3],
        'parameters': json.loads(action_data[4]) if action_data[4] else {},
        'created_at': action_data[5],
        'expires_at': action_data[6],
        'resolved': bool(action_data[7]),
        'targets': [(t[0], t[1]) for t in targets]  # (target_id, order)
    }

def get_pending_complex_actions(game_id, phase=None):
    """
    Get all pending complex actions for a game, optionally filtered by phase.
    
    Args:
        game_id (str): The game identifier
        phase (str, optional): The game phase to filter by
        
    Returns:
        list: List of dictionaries with action details
    """
    import json
    
    if phase:
        cursor.execute("""
        SELECT action_id FROM ComplexActions
        WHERE game_id = ? AND phase = ? AND resolved = 0
        ORDER BY created_at
        """, (game_id, phase))
    else:
        cursor.execute("""
        SELECT action_id FROM ComplexActions
        WHERE game_id = ? AND resolved = 0
        ORDER BY phase, created_at
        """, (game_id,))
    
    action_ids = [row[0] for row in cursor.fetchall()]
    return [get_complex_action(action_id) for action_id in action_ids]

def mark_complex_action_resolved(action_id, resolved=True):
    """
    Mark a complex action as resolved.
    
    Args:
        action_id (int): The complex action ID
        resolved (bool, optional): Whether the action is resolved (default: True)
    """
    resolved_int = 1 if resolved else 0
    cursor.execute("""
    UPDATE ComplexActions
    SET resolved = ?
    WHERE action_id = ?
    """, (resolved_int, action_id))
    
    conn.commit()
    logger.debug(f"Marked complex action {action_id} as {'resolved' if resolved else 'unresolved'}")

def delete_expired_complex_actions():
    """
    Delete all expired complex actions.
    Should be called regularly during game maintenance.
    
    Returns:
        int: Number of expired actions deleted
    """
    import datetime
    
    current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # First get IDs to delete associated targets
    cursor.execute("""
    SELECT action_id FROM ComplexActions
    WHERE expires_at IS NOT NULL AND expires_at < ?
    """, (current_time,))
    
    expired_ids = [row[0] for row in cursor.fetchall()]
    
    # Delete associated targets
    if expired_ids:
        placeholders = ','.join('?' for _ in expired_ids)
        cursor.execute(f"""
        DELETE FROM ActionTargets
        WHERE action_id IN ({placeholders})
        """, expired_ids)
    
    # Delete the expired actions
    cursor.execute("""
    DELETE FROM ComplexActions
    WHERE expires_at IS NOT NULL AND expires_at < ?
    """, (current_time,))
    
    deleted_count = cursor.rowcount
    conn.commit()
    
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} expired complex actions")
    
    return deleted_count

def get_role_state(game_id, user_id, state_key):
    """
    Get a role state value for a player.
    
    Args:
        game_id (str): The game identifier
        user_id (int): The player ID
        state_key (str): The state key to retrieve
        
    Returns:
        str: The state value or None if not found
    """
    cursor.execute("""
    SELECT state_value FROM RoleStates
    WHERE game_id = ? AND user_id = ? AND state_key = ?
    """, (game_id, user_id, state_key))
    
    result = cursor.fetchone()
    return result[0] if result else None

def set_role_state(game_id, user_id, state_key, state_value, expires_at=None):
    """
    Set or update a role state for a player.
    
    Args:
        game_id (str): The game identifier
        user_id (int): The player ID
        state_key (str): The state key to set
        state_value (str): The state value to set
        expires_at (str, optional): Timestamp when this state expires
    """
    cursor.execute("""
    INSERT OR REPLACE INTO RoleStates (game_id, user_id, state_key, state_value, expires_at)
    VALUES (?, ?, ?, ?, ?)
    """, (game_id, user_id, state_key, state_value, expires_at))
    
    conn.commit()
    logger.debug(f"Set role state '{state_key}' to '{state_value}' for player {user_id} in game {game_id}")

def delete_role_state(game_id, user_id, state_key):
    """
    Delete a role state for a player.
    
    Args:
        game_id (str): The game identifier
        user_id (int): The player ID
        state_key (str): The state key to delete
    """
    cursor.execute("""
    DELETE FROM RoleStates
    WHERE game_id = ? AND user_id = ? AND state_key = ?
    """, (game_id, user_id, state_key))
    
    conn.commit()
    logger.debug(f"Deleted role state '{state_key}' for player {user_id} in game {game_id}")

def delete_expired_role_states():
    """
    Delete all expired role states.
    Should be called regularly during game maintenance.
    
    Returns:
        int: Number of expired states deleted
    """
    import datetime
    
    current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute("""
    DELETE FROM RoleStates
    WHERE expires_at IS NOT NULL AND expires_at < ?
    """, (current_time,))
    
    deleted_count = cursor.rowcount
    conn.commit()
    
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} expired role states")
    
    return deleted_count