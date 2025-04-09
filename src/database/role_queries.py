"""
Database query functions for role operations.
This module centralizes all database operations related to roles and player roles.
"""

import logging
from src.database.connection import conn, cursor

logger = logging.getLogger("Mafia Bot Database.RoleQueries")

def get_players_with_roles(game_id):
    """Get all players (with their roles and elimination status) for a specific game."""
    cursor.execute("""
        SELECT Roles.user_id, Roles.role, Roles.eliminated
        FROM Roles
        WHERE Roles.game_id = ?
    """, (game_id,))
    return cursor.fetchall()

def get_player_role(game_id, user_id):
    """Get the role of a specific player in a game."""
    cursor.execute("""
        SELECT role, eliminated
        FROM Roles
        WHERE game_id = ? AND user_id = ?
    """, (game_id, user_id))
    return cursor.fetchone()

def get_active_players(game_id):
    """Get all active (non-eliminated) players in a game."""
    cursor.execute("""
        SELECT user_id, role
        FROM Roles
        WHERE game_id = ? AND eliminated = 0
    """, (game_id,))
    return cursor.fetchall()

def get_eliminated_players(game_id):
    """Get all eliminated players in a game."""
    cursor.execute("""
        SELECT user_id, role
        FROM Roles
        WHERE game_id = ? AND eliminated = 1
    """, (game_id,))
    return cursor.fetchall()

def set_player_role(game_id, user_id, role):
    """Assign a role to a player in a game."""
    cursor.execute("""
        INSERT OR REPLACE INTO Roles (game_id, user_id, role, eliminated)
        VALUES (?, ?, ?, 0)
    """, (game_id, user_id, role))
    conn.commit()
    logger.debug(f"Set role for player {user_id} in game {game_id} to {role}")

def eliminate_player(game_id, user_id):
    """Mark a player as eliminated in a game."""
    cursor.execute("""
        UPDATE Roles
        SET eliminated = 1
        WHERE game_id = ? AND user_id = ?
    """, (game_id, user_id))
    conn.commit()
    logger.debug(f"Eliminated player {user_id} in game {game_id}")

def revive_player(game_id, user_id):
    """Revive a previously eliminated player in a game."""
    cursor.execute("""
        UPDATE Roles
        SET eliminated = 0
        WHERE game_id = ? AND user_id = ?
    """, (game_id, user_id))
    conn.commit()
    logger.debug(f"Revived player {user_id} in game {game_id}")