from .db_connection import cursor
import logging

logger = logging.getLogger("Mafia Bot DB Queries")

def get_user_by_id(user_id):
    """Retrieves a user by their ID."""
    if not cursor:
        logger.error("Database cursor is not available.")
        return None

    cursor.execute("SELECT * FROM Users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if user:
        logger.debug(f"Retrieved user with ID {user_id}.")
    else:
        logger.debug(f"No user found with ID {user_id}.")
    return user