import sqlite3
from utils import resource_path
import logging

logger = logging.getLogger("Mafia Bot DB")

conn = sqlite3.connect(resource_path('mafia_game.db'), check_same_thread=False)
cursor = conn.cursor()

def initialize_database():
    logger.debug("Initializing the database and creating tables if they don't exist.")

    # Enable WAL mode for better concurrency
    conn.execute("PRAGMA journal_mode=WAL;")

    # Create Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create Games table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Games (
            game_id INTEGER PRIMARY KEY AUTOINCREMENT,
            passcode TEXT UNIQUE,
            moderator_id INTEGER,
            started INTEGER DEFAULT 0,
            randomness_method TEXT DEFAULT 'fallback (local random)',
            FOREIGN KEY (moderator_id) REFERENCES Users(user_id)
        )
    ''')

    # Create Roles table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Roles (
            game_id INTEGER,
            user_id INTEGER,
            role TEXT,
            FOREIGN KEY (game_id) REFERENCES Games(game_id),
            FOREIGN KEY (user_id) REFERENCES Users(user_id),
            PRIMARY KEY (game_id, user_id)
        )
    ''')

    # Create GameRoles table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS GameRoles (
            game_id INTEGER,
            role TEXT,
            count INTEGER,
            FOREIGN KEY (game_id) REFERENCES Games(game_id),
            PRIMARY KEY (game_id, role)
        )
    ''')

    conn.commit()
    logger.debug("Database initialized successfully.")

    # Ensure randomness_method column exists
    cursor.execute("PRAGMA table_info(Games)")
    columns = [info[1] for info in cursor.fetchall()]
    if 'randomness_method' not in columns:
        cursor.execute("ALTER TABLE Games ADD COLUMN randomness_method TEXT DEFAULT 'fallback (local random)'")
        conn.commit()
        logger.debug("Added 'randomness_method' column to Games table.")
