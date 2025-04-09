"""
Database query functions for game operations.
This module centralizes all database operations related to game management.
"""

import logging
from src.database.connection import conn, cursor

logger = logging.getLogger("Mafia Bot Database.GameQueries")

def get_game_by_id(game_id):
    """Get game information by game ID."""
    cursor.execute("""
        SELECT game_id, passcode, moderator_id, state, created_at
        FROM Games
        WHERE game_id = ?
    """, (game_id,))
    return cursor.fetchone()

def get_game_by_passcode(passcode):
    """Get game information by passcode."""
    cursor.execute("""
        SELECT game_id, passcode, moderator_id, state, created_at
        FROM Games
        WHERE passcode = ?
    """, (passcode,))
    return cursor.fetchone()

def get_active_games():
    """Get all active games (not ended)."""
    cursor.execute("""
        SELECT game_id, passcode, moderator_id, state, created_at
        FROM Games
        WHERE state NOT IN ('ENDED', 'CANCELLED')
    """)
    return cursor.fetchall()

def create_game(moderator_id, passcode, state='SETUP'):
    """Create a new game."""
    cursor.execute("""
        INSERT INTO Games (moderator_id, passcode, state) 
        VALUES (?, ?, ?)
    """, (moderator_id, passcode, state))
    conn.commit()
    game_id = cursor.lastrowid
    logger.debug(f"Created new game with ID {game_id}, passcode {passcode}")
    return game_id

def get_moderator_id(game_id):
    """Get the moderator ID for a specific game."""
    cursor.execute("SELECT moderator_id FROM Games WHERE game_id = ?", (game_id,))
    result = cursor.fetchone()
    return result[0] if result else None

def update_game_state(game_id, state):
    """Update the state of a game."""
    cursor.execute("""
        UPDATE Games
        SET state = ?
        WHERE game_id = ?
    """, (state, game_id))
    conn.commit()
    logger.debug(f"Updated game {game_id} state to {state}")

def delete_game(game_id):
    """Delete a game from the database. Use with caution as it may violate foreign key constraints."""
    cursor.execute("DELETE FROM Games WHERE game_id = ?", (game_id,))
    conn.commit()
    logger.debug(f"Deleted game: {game_id}")