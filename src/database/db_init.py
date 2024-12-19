from .db_connection import conn, cursor
import logging
from .migrations import migrate_games_table

logger = logging.getLogger("Mafia Bot DB Init")

def initialize_database():
    """Initializes the database, creates tables, and performs migrations if necessary."""
    if not conn or not cursor:
        logger.error("Database connection or cursor is not available.")
        return

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
        migrate_games_table(conn, cursor)
    else:
        # Create Games table with TEXT PRIMARY KEY if it doesn't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS Games (
            game_id TEXT PRIMARY KEY,
            passcode TEXT UNIQUE,
            moderator_id INTEGER,
            started INTEGER DEFAULT 0,
            randomness_method TEXT DEFAULT 'fallback (local random)',
            FOREIGN KEY (moderator_id) REFERENCES Users(user_id)
        )
        ''')
        logger.debug("Games table created with TEXT PRIMARY KEY for game_id.")

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

    # Ensure the 'eliminated' column exists in Roles table
    cursor.execute("PRAGMA table_info(Roles)")
    columns = [info[1] for info in cursor.fetchall()]
    if 'eliminated' not in columns:
        cursor.execute("ALTER TABLE Roles ADD COLUMN eliminated INTEGER DEFAULT 0")
        logger.debug("Added 'eliminated' column to Roles table.")

    # Ensure the 'randomness_method' column exists in Games table
    cursor.execute("PRAGMA table_info(Games)")
    columns = [info[1] for info in cursor.fetchall()]
    if 'randomness_method' not in columns:
        cursor.execute("ALTER TABLE Games ADD COLUMN randomness_method TEXT DEFAULT 'fallback (local random)'")
        logger.debug("Added 'randomness_method' column to Games table.")

    conn.commit()
    logger.debug("Database initialized successfully.")