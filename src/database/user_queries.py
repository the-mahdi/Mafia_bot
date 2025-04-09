"""
Database query functions for user operations.
This module centralizes all database operations related to user management.
"""

import logging
from src.database.connection import conn, cursor

logger = logging.getLogger("Mafia Bot Database.UserQueries")

def get_user_by_id(user_id):
    """Get user information by user ID."""
    cursor.execute("SELECT user_id, username, last_updated FROM Users WHERE user_id = ?", (user_id,))
    return cursor.fetchone()

def get_username(user_id):
    """Get username for a given user ID."""
    cursor.execute("SELECT username FROM Users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    return result[0] if result else None

def user_exists(user_id):
    """Check if a user exists in the database."""
    cursor.execute("SELECT 1 FROM Users WHERE user_id = ?", (user_id,))
    return cursor.fetchone() is not None

def create_user(user_id, username):
    """Create a new user in the database."""
    cursor.execute(
        "INSERT INTO Users (user_id, username) VALUES (?, ?)", 
        (user_id, username)
    )
    conn.commit()
    logger.debug(f"Created new user: {user_id} ({username})")

def update_username(user_id, username):
    """Update username for an existing user."""
    cursor.execute(
        "UPDATE Users SET username = ?, last_updated = CURRENT_TIMESTAMP WHERE user_id = ?", 
        (username, user_id)
    )
    conn.commit()
    logger.debug(f"Updated username for user {user_id} to {username}")

def upsert_user(user_id, username):
    """Insert a new user or update an existing one."""
    if user_exists(user_id):
        update_username(user_id, username)
    else:
        create_user(user_id, username)
    return username

def get_users_in_game(game_id, only_active=False):
    """Get all users in a specific game, optionally filtering to only active (non-eliminated) players."""
    if only_active:
        cursor.execute("""
        SELECT Users.user_id, Users.username 
        FROM Users 
        JOIN Roles ON Users.user_id = Roles.user_id 
        WHERE Roles.game_id = ? AND Roles.eliminated = 0
        """, (game_id,))
    else:
        cursor.execute("""
        SELECT Users.user_id, Users.username 
        FROM Users 
        JOIN Roles ON Users.user_id = Roles.user_id 
        WHERE Roles.game_id = ?
        """, (game_id,))
    return cursor.fetchall()

def get_all_users():
    """Get all users from the database."""
    cursor.execute("SELECT user_id, username, last_updated FROM Users")
    return cursor.fetchall()

def delete_user(user_id):
    """Delete a user from the database. Use with caution as it may violate foreign key constraints."""
    cursor.execute("DELETE FROM Users WHERE user_id = ?", (user_id,))
    conn.commit()
    logger.debug(f"Deleted user: {user_id}")