import logging

logger = logging.getLogger("Mafia Bot DB Migrations")

def migrate_games_table(conn, cursor):
    """Migrates the Games table to use TEXT PRIMARY KEY for game_id."""
    logger.debug("Migrating Games table to use TEXT PRIMARY KEY for game_id.")

    # Create a new table with the correct schema
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Games_new (
        game_id TEXT PRIMARY KEY,
        passcode TEXT UNIQUE,
        moderator_id INTEGER,
        started INTEGER DEFAULT 0,
        randomness_method TEXT DEFAULT 'fallback (local random)',
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

    # Rename the new table to the old table name
    cursor.execute("ALTER TABLE Games_new RENAME TO Games")

    logger.debug("Games table migrated successfully.")
    conn.commit()