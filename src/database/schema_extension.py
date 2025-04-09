"""
Schema extensions for supporting complex roles and actions in the Mafia game.
This module extends the base schema.py with additional tables needed for the ~80 new roles
and more complex game mechanics planned for the future.
"""

import logging
from src.database.connection import conn, cursor
from src.database.schema import initialize_database

logger = logging.getLogger("Mafia Bot DB Extensions")

def initialize_extended_schema():
    """
    Initialize additional database tables required for complex roles and game mechanics.
    This should be called after the basic schema initialization.
    """
    logger.debug("Initializing extended database schema for complex roles and actions.")
    
    # Create RoleStates table for persistent role state tracking
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS RoleStates (
        game_id TEXT,
        user_id INTEGER,
        state_key TEXT,  -- e.g., 'uses_remaining', 'protected_until', 'intoxicated'
        state_value TEXT, -- JSON or simple value
        expires_at TIMESTAMP,  -- NULL for permanent states
        FOREIGN KEY (game_id, user_id) REFERENCES Roles(game_id, user_id),
        PRIMARY KEY (game_id, user_id, state_key)
    )
    ''')
    
    # Create ComplexActions table for actions with multiple targets or delayed effects
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS ComplexActions (
        action_id INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id TEXT,
        user_id INTEGER,
        phase TEXT,  -- 'night' or 'day' or specific phase name
        action TEXT,
        parameters TEXT,  -- JSON with additional parameters
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP,  -- For delayed actions
        resolved INTEGER DEFAULT 0,  -- 0=pending, 1=resolved
        FOREIGN KEY (game_id) REFERENCES Games(game_id),
        FOREIGN KEY (user_id) REFERENCES Users(user_id)
    )
    ''')
    
    # Create ActionTargets table for linking actions to multiple targets
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS ActionTargets (
        action_id INTEGER,
        target_id INTEGER,
        target_order INTEGER DEFAULT 0,  -- For ordered targeting
        FOREIGN KEY (action_id) REFERENCES ComplexActions(action_id),
        FOREIGN KEY (target_id) REFERENCES Users(user_id),
        PRIMARY KEY (action_id, target_id)
    )
    ''')
    
    # Create RoleInteractions table for tracking special interactions between roles
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS RoleInteractions (
        game_id TEXT,
        role1 TEXT,
        role2 TEXT,
        interaction_type TEXT,  -- e.g., 'blocks', 'enhances', 'reveals'
        interaction_params TEXT,  -- JSON with additional parameters
        FOREIGN KEY (game_id) REFERENCES Games(game_id),
        PRIMARY KEY (game_id, role1, role2, interaction_type)
    )
    ''')
    
    # Add metadata column to Roles table if not exists
    cursor.execute("PRAGMA table_info(Roles)")
    columns = [info[1] for info in cursor.fetchall()]
    if 'metadata' not in columns:
        cursor.execute("ALTER TABLE Roles ADD COLUMN metadata TEXT DEFAULT '{}'") # JSON
        logger.debug("Added 'metadata' column to Roles table for flexible role data.")
    
    # Modify Actions table to include priority and status
    cursor.execute("PRAGMA table_info(Actions)")
    columns = [info[1] for info in cursor.fetchall()]
    
    if 'priority' not in columns:
        cursor.execute("ALTER TABLE Actions ADD COLUMN priority INTEGER DEFAULT 0")
        logger.debug("Added 'priority' column to Actions table.")
        
    if 'status' not in columns:
        cursor.execute("ALTER TABLE Actions ADD COLUMN status TEXT DEFAULT 'pending'")
        logger.debug("Added 'status' column to Actions table.")
    
    # Creating index for faster queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_role_states ON RoleStates (game_id, user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_complex_actions ON ComplexActions (game_id, phase, resolved)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_action_targets ON ActionTargets (action_id)")
    
    conn.commit()
    logger.debug("Extended database schema initialized successfully.")

def setup_database():
    """
    Complete database setup function that initializes both basic and extended schema.
    """
    initialize_database()
    initialize_extended_schema()
    logger.info("Complete database schema (basic + extended) initialized successfully.")