import sqlite3
from utils import resource_path
import logging

logger = logging.getLogger("Mafia Bot DB Connection")

def get_db_connection():
    """Establishes and returns a database connection."""
    try:
        conn = sqlite3.connect(resource_path('mafia_game.db'), check_same_thread=False)
        logger.debug("Database connection established.")
        return conn
    except sqlite3.Error as e:
        logger.error(f"Error connecting to database: {e}")
        return None

# Get the connection when the module is imported
conn = get_db_connection()
if conn:
    cursor = conn.cursor()
else:
    logger.error("Failed to get a database connection.")
    cursor = None  # Or handle the error as appropriate for your application