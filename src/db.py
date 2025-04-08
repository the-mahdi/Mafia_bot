import sqlite3
from src.utils import resource_path
import logging
import os

logger = logging.getLogger("Mafia Bot DB")

conn = sqlite3.connect(resource_path(os.path.join('db', 'mafia_game.db')), check_same_thread=False)
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

    # Check if Games table exists and migrate if necessary
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Games'")
    games_table_exists = cursor.fetchone()

    if games_table_exists:
        # Create a new table with the updated schema
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS Games_new (
            game_id TEXT PRIMARY KEY,
            passcode TEXT UNIQUE,
            moderator_id INTEGER,
            started INTEGER DEFAULT 0,
            randomness_method TEXT DEFAULT 'fallback (local random)',
            current_phase TEXT DEFAULT 'off',
            FOREIGN KEY (moderator_id) REFERENCES Users(user_id)
        )
        ''')

        # Copy data from the old table to the new table
        cursor.execute("""
        INSERT INTO Games_new (game_id, passcode, moderator_id, started, randomness_method)
        SELECT game_id, passcode, moderator_id, started, randomness_method FROM Games
        """)

        # Drop the old table
        cursor.execute("DROP TABLE Games")
        # Rename the new table
        cursor.execute("ALTER TABLE Games_new RENAME TO Games")
        logger.debug("Games table migrated with current_phase column.")
    else:
        # Create Games table with current_phase if it doesn’t exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS Games (
            game_id TEXT PRIMARY KEY,
            passcode TEXT UNIQUE,
            moderator_id INTEGER,
            started INTEGER DEFAULT 0,
            randomness_method TEXT DEFAULT 'fallback (local random)',
            current_phase TEXT DEFAULT 'off',
            FOREIGN KEY (moderator_id) REFERENCES Users(user_id)
        )
        ''')
        logger.debug("Games table created with current_phase.")

    # Create Roles table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Roles (
        game_id TEXT,
        user_id INTEGER,
        role TEXT,
        eliminated INTEGER DEFAULT 0,
        FOREIGN KEY (game_id) REFERENCES Games(game_id),
        FOREIGN KEY (user_id) REFERENCES Users(user_id),
        PRIMARY KEY (game_id, user_id)
    )
    ''')

    # Create GameRoles table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS GameRoles (
        game_id TEXT,
        role TEXT,
        count INTEGER,
        FOREIGN KEY (game_id) REFERENCES Games(game_id),
        PRIMARY KEY (game_id, role)
    )
    ''')

    # Create Actions table for night/day actions
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Actions (
        game_id TEXT,
        user_id INTEGER,
        phase TEXT,  -- 'night' or 'day'
        action TEXT,
        target_id INTEGER,
        FOREIGN KEY (game_id) REFERENCES Games(game_id),
        FOREIGN KEY (user_id) REFERENCES Users(user_id),
        PRIMARY KEY (game_id, user_id, phase)
    )
    ''')

    # Ensure 'eliminated' column exists in Roles
    cursor.execute("PRAGMA table_info(Roles)")
    columns = [info[1] for info in cursor.fetchall()]
    if 'eliminated' not in columns:
        cursor.execute("ALTER TABLE Roles ADD COLUMN eliminated INTEGER DEFAULT 0")
        logger.debug("Added 'eliminated' column to Roles table.")

    # Ensure 'randomness_method' column exists in Games
    cursor.execute("PRAGMA table_info(Games)")
    columns = [info[1] for info in cursor.fetchall()]
    if 'randomness_method' not in columns:
        cursor.execute("ALTER TABLE Games ADD COLUMN randomness_method TEXT DEFAULT 'fallback (local random)'")
        logger.debug("Added 'randomness_method' column to Games table.")

    # Ensure 'current_phase' column exists in Games
    if 'current_phase' not in columns:
        cursor.execute("ALTER TABLE Games ADD COLUMN current_phase TEXT DEFAULT 'off'")
        logger.debug("Added 'current_phase' column to Games table.")

    conn.commit()
    logger.debug("Database initialized successfully.")