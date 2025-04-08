import sqlite3
import os
import logging
from src.utils.path import resource_path

logger = logging.getLogger("Mafia Bot DB")

# Create the database connection
conn = sqlite3.connect(resource_path(os.path.join('db', 'mafia_game.db')), check_same_thread=False)
cursor = conn.cursor()

# Set pragmas
conn.execute("PRAGMA journal_mode=WAL;")

def get_connection():
    """Return the database connection object."""
    return conn

def get_cursor():
    """Return the database cursor object."""
    return cursor