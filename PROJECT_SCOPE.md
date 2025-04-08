# Project Scope: Mafia Bot

This document outlines the scope and functionalities of the Mafia Bot project, detailing the purpose and responsibilities of each file within the application.

## File: `main.py`

*   **Entry Point:** Serves as the main execution point for the bot.
*   **Initialization:**
    *   Sets up application-wide logging (console and file output) with custom filtering.
    *   Initializes the SQLite database connection and schema using `src.db.initialize_database`.
    *   Creates the `telegram.ext.Application` instance using the bot token from `src.config`.
*   **Handler Registration:** Registers all necessary handlers for commands (`/start`), button callbacks, text messages (passcodes/names), and errors.
*   **Error Handling:** Defines a global error handler (`error_handler`) to catch exceptions during update processing and notify the user/log the error.
*   **Bot Execution:** Starts the bot's polling mechanism to listen for incoming updates from Telegram.

## File: `data/roles.json`

*   **Data Storage:** Contains the core definitions for all available Mafia game roles in JSON format.
*   **Role Attributes:** For each role, it defines:
    *   `faction`: The team the role belongs to (e.g., "Villager", "Mafia").
    *   `description`: A textual explanation of the role's purpose and abilities.
    *   `actions`: A dictionary defining actions available during `night` and `day` phases, including:
        *   `name`: The action's display name.
        *   `description`: Explanation of the action.
        *   `targets`: Number of players the action targets.
        *   `command`: Internal identifier for the action callback.
        *   `interactive`: How the action is triggered (e.g., "button", "none").
        *   `self_target` (optional): Whether the player can target themselves.
        *   `priority` (optional): Order of action resolution.

## File: `src/config.py`

*   **Configuration Loading:** Reads essential configuration parameters from the `data/token.txt` file.
*   **Parameter Extraction:** Expects and extracts:
    *   `TOKEN`: The Telegram Bot API token.
    *   `RANDOM_ORG_API_KEY`: API key for Random.org (used for role shuffling).
    *   `MAINTAINER_ID`: The Telegram User ID of the bot maintainer (for template approvals).
*   **Error Handling:** Handles cases where `token.txt` is missing or does not contain the required number of lines.
*   **Resource Pathing:** Uses `src.utils.resource_path` to ensure compatibility when run directly or as a packaged executable (e.g., via PyInstaller).
*   **Exports:** Makes the loaded configuration values available as constants (`TOKEN`, `RANDOM_ORG_API_KEY`, `MAINTAINER_ID`).

## File: `src/db.py`

*   **Database Connection:** Establishes and manages the connection to the SQLite database (`db/mafia_game.db`). Allows concurrent access (`check_same_thread=False`, `PRAGMA journal_mode=WAL`).
*   **Schema Initialization (`initialize_database`):**
    *   Creates necessary tables if they don't exist:
        *   `Users`: Stores user IDs and usernames.
        *   `Games`: Stores game details (ID, passcode, moderator, state, phase, randomness method).
        *   `Roles`: Maps users to roles within a specific game, tracks elimination status.
        *   `GameRoles`: Stores the count of each role selected for a specific game.
        *   `Actions`: Records actions taken by players during night/day phases.
    *   Handles schema migrations (e.g., adding new columns like `eliminated`, `randomness_method`, `current_phase` to existing tables).
*   **Exports:** Provides the database connection (`conn`) and cursor (`cursor`) objects for use throughout the application.

## File: `src/roles.py`

*   **Role Data Loading:** Loads the role definitions from `data/roles.json` using `load_roles`.
*   **Template Management:**
    *   Loads approved role templates and pending templates from `data/role_templates.json` using `load_role_templates`.
    *   Saves updated template data back to `data/role_templates.json` using `save_role_templates`.
*   **Error Handling:** Handles file not found and JSON decoding errors for role and template files.
*   **Data Processing & Export:** Processes the loaded role data and exports convenient structures:
    *   `roles`: The complete dictionary of role data.
    *   `available_roles`: A list of all role names.
    *   `role_descriptions`: A dictionary mapping role names to their descriptions.
    *   `role_factions`: A dictionary mapping role names to their factions.
    *   `role_actions`: A dictionary mapping role names to their action definitions.
    *   `role_templates`, `pending_templates`: Dictionaries containing the loaded role templates.

## File: `src/utils.py`

*   **Resource Pathing (`resource_path`):** Provides a utility function to determine the correct absolute path to resource files (like data files, database), ensuring compatibility in both development and packaged (PyInstaller) environments.
*   **Voting Summary (`generate_voting_summary`):** Generates a formatted Markdown string summarizing the current voting status, listing players who have and have not voted.

## File: `src/__init__.py`

*   **Package Marker:** An empty file that designates the `src` directory as a Python package, allowing modules within it to be imported using dot notation (e.g., `from src.db import ...`).

## File: `src/handlers/button_handler.py`

*   **Callback Query Handling:** Manages all interactions initiated by users clicking inline keyboard buttons (`CallbackQueryHandler`).
*   **Action Routing (`handle_button`):** Acts as the central dispatcher for button presses, determining the action based on the `callback_data` associated with the button.
*   **Functionality:** Implements the logic triggered by various buttons, including:
    *   Main menu navigation (`back_to_menu`).
    *   Game creation (`create_game`).
    *   Game joining (`join_game`, name confirmation: `keep_name`, `change_name`).
    *   Role selection interface (pagination: `prev_page`, `next_page`; modification: `increase_`, `decrease_`; `reset_roles`).
    *   Role confirmation and assignment (`confirm_roles`).
    *   Role template selection (`select_template`, `template_`).
    *   Saving role setups as templates (`confirm_roles_and_save_template`).
    *   Maintainer approval/rejection of templates (`maintainer_confirm_`, `maintainer_reject_`).
    *   Game management menu display (`manage_games`).
    *   Moderator actions: Player elimination (`eliminate_player`, `eliminate_confirm_`, `eliminate_yes_`, `eliminate_cancel_`), Player revival (`revive_player`, `revive_confirm_`, `revive_yes_`, `revive_cancel_`), Announcing votes (`announce_voting`, `announce_anonymous_voting`), Game inquiries (`inquiry_summary`, `inquiry_detailed`).
    *   Voting process (`vote_`, `confirm_votes`, `final_confirm_vote_`, `cancel_vote_`).
    *   Voting permission setup (`toggle_can_vote_`, `toggle_can_be_voted_`, `confirm_permissions`).
    *   Handling night/day action prompts and target selection.
*   **State Management:** Uses `context.user_data` to maintain user-specific state (e.g., current game ID, current page in role selection).
*   **Concurrency Control:** Uses an `asyncio.Lock` (`game_locks`) to prevent race conditions when multiple users modify role counts simultaneously.
*   **Action Recording (`perform_action`):** Records player actions (heal, investigate, etc.) into the `Actions` database table.

## File: `src/handlers/passcode_handler.py`

*   **Text Message Handling:** Processes incoming text messages that are *not* commands (`MessageHandler`).
*   **State-Based Processing (`handle_passcode`):** Determines the expected input based on the user's current state stored in `context.user_data['action']`.
*   **Functionality:** Handles specific text inputs:
    *   Receiving and storing/updating player names (`awaiting_name`, `change_name`).
    *   Receiving passcodes to join games (`join_game`).
    *   Receiving names for new role templates (`awaiting_template_name_confirmation`).
*   **Template Saving Workflow:**
    *   `handle_template_confirmation`: Initiates the process after a name is received.
    *   `save_template_as_pending`: Saves the template details to `pending_templates` in `role_templates.json`, notifies the maintainer via Telegram message with confirmation/rejection buttons.
*   **Validation (`is_valid_passcode`):** Includes a basic check for passcode format (UUID).

## File: `src/handlers/start_handler.py`

*   **Command Handling:** Responds to the `/start` command (`CommandHandler`).
*   **Main Menu (`start`):** Sends the initial welcome message and displays the main menu as inline keyboard buttons (Create Game, Join Game, Set Roles, etc.), providing the primary user interface entry point.

## File: `src/handlers/__init__.py`

*   **Package Interface:** Defines the public API for the `handlers` package using `__all__`.
*   **Re-exporting:** Imports and makes key handlers and functions from its submodules (`button_handler`, `passcode_handler`, `start_handler`) directly accessible when importing from `src.handlers`.

## File: `src/handlers/game_management/base.py`

*   **Core Utilities:** Provides fundamental functions used across game management modules.
*   **Random Shuffling (`get_random_shuffle`):** Attempts to shuffle lists using the Random.org API for true randomness, with a fallback to Python's `random.sample` if the API fails or is unavailable. Records which method was used.
*   **Player Count (`get_player_count`):** Queries the database to find the number of players currently associated with a specific game ID.
*   **Template Retrieval (`get_templates_for_player_count`):** Fetches pre-defined role templates suitable for a given number of players from the loaded `role_templates`.
*   **Constants/Locks:** Defines shared constants (`ROLES_PER_PAGE`) and synchronization primitives (`role_counts_lock`).

## File: `src/handlers/game_management/create_game.py`

*   **Game Creation Logic (`create_game`):**
    *   Handles the process of creating a new game instance.
    *   Generates a unique game ID and a unique passcode (using UUIDs).
    *   Inserts the new game record into the `Games` database table, linking it to the moderator.
    *   Initializes role counts to zero for the new game in the `GameRoles` table.
    *   Stores the new `game_id` in the moderator's `context.user_data`.
    *   Sends the generated passcode back to the moderator.

## File: `src/handlers/game_management/inquiry.py`

*   **Game State Reporting:** Provides functions for players to inquire about the game's state.
*   **Faction Summary (`send_inquiry_summary`):** Calculates and sends a message to all players and the moderator summarizing the number of active and eliminated players belonging to each *faction* (e.g., Villager, Mafia).
*   **Detailed Summary (`send_detailed_inquiry_summary`):** Calculates and sends a more detailed message listing the count of each specific *role* within each faction for both active and eliminated players.

## File: `src/handlers/game_management/join_game.py`

*   **Game Joining Logic (`join_game`):**
    *   Handles a player's attempt to join a game using a passcode.
    *   Validates the passcode against the `Games` table.
    *   Prevents joining if the game has already started.
    *   Adds or updates the player's information in the `Users` table.
    *   Associates the player with the game in the `Roles` table (initially without a specific role assigned).
    *   Stores the `game_id` in the player's `context.user_data`.
    *   Notifies the game moderator that a new player has joined.

## File: `src/handlers/game_management/phase_manager.py`

*   **Game Flow Control:** Manages the transitions between different game phases (Night, Day).
*   **Night Phase (`start_night_phase`, `resolve_night_actions`):**
    *   Updates the game state to 'night'.
    *   Sends action prompts (buttons) to players based on their roles' night actions.
    *   Collects and resolves night actions (e.g., kills, heals, investigations) based on recorded data in the `Actions` table.
    *   Applies action outcomes (e.g., player elimination).
    *   Transitions to the day phase.
*   **Day Phase (`start_day_phase`, `resolve_day_actions`):**
    *   Updates the game state to 'day'.
    *   Sends action prompts for day actions (if any).
    *   Resolves day actions (excluding voting, which is handled separately).
    *   Prepares for the voting phase.

## File: `src/handlers/game_management/player_management.py`

*   **Moderator Player Control:** Implements moderator abilities to manually alter player status.
*   **Elimination (`eliminate_player`, `handle_elimination_confirmation`, `confirm_elimination`, `cancel_elimination`):** Provides the interface and logic for a moderator to select an active player, confirm the choice, and mark them as eliminated in the database. Notifies relevant parties. Removes the player from active voting sessions.
*   **Revival (`revive_player`, `handle_revive_confirmation`, `confirm_revive`, `cancel_revive`):** Provides the interface and logic for a moderator to select an eliminated player, confirm the choice, and mark them as active (not eliminated) again in the database. Notifies relevant parties.

## File: `src/handlers/game_management/roles_setup.py`

*   **Role Configuration Interface:** Manages the process for the moderator to define the roles for a game.
*   **Display (`show_role_buttons`):** Presents a paginated interface with buttons for each available role, allowing the moderator to increase/decrease the count for each role. Includes navigation, reset, confirm, and save template buttons.
*   **Confirmation and Assignment (`confirm_and_set_roles`):**
    *   Validates that the total number of selected roles matches the number of players in the game.
    *   Generates the list of roles based on the selected counts.
    *   Randomly shuffles the roles and the list of players (using Random.org if possible, falling back to local `random`).
    *   Assigns the shuffled roles to the shuffled players and updates the `Roles` table in the database.
    *   Records the randomness method used (`Random.org` or `fallback`) in the `Games` table.
    *   Sends a summary of the roles in the game (counts and descriptions) to all players.

## File: `src/handlers/game_management/start_game.py`

*   **Game Initiation:** Handles the final steps to begin a configured game.
*   **Start Logic (`start_game`):**
    *   Performs checks (moderator authorization, game not already started, roles assigned).
    *   Sends a private message to each player revealing their assigned role, role description, faction, and the randomness methodology used for assignment.
    *   Sends a summary of all assigned roles to the moderator.
    *   Updates the game status to 'started' in the `Games` database table.
    *   Initiates the first game phase (typically Night).
*   **Start Latest (`start_latest_game`):** Allows the moderator to quickly start the most recently created game that hasn't begun yet.

## File: `src/handlers/game_management/voting.py`

*   **Voting Process Management:** Orchestrates the entire voting phase of the game.
*   **In-Memory State:** Uses `game_voting_data` dictionary to store temporary voting state for active games (votes, voters, player lists, settings).
*   **Permission Setup (`prompt_voting_permissions`, `show_voting_permissions`, `handle_voting_permission_toggle`, `confirm_permissions`):** Provides an interface for the moderator to configure which players can vote and which can be voted on before the voting starts.
*   **Voting Initiation (`announce_voting`, `announce_anonymous_voting` - potentially superseded by permission flow):** Starts a voting session, setting it as public or anonymous.
*   **Vote Casting (`handle_vote`):** Processes a player clicking a vote button, toggling their vote for a target. Updates the inline keyboard to reflect selections.
*   **Vote Confirmation (`confirm_votes`, `final_confirm_vote`, `cancel_vote`):** Implements a two-step confirmation process for players to finalize their votes or cancel and re-select.
*   **Moderator Summary (`send_voting_summary`):** Sends and updates a message to the moderator showing the real-time status of who has voted and who hasn't.
*   **Result Processing (`process_voting_results`):**
    *   Calculates the final vote counts once all eligible players have confirmed.
    *   Sends a summary of vote counts to all players and the moderator.
    *   Sends a detailed report (who voted for whom) to the moderator (and players if voting was not anonymous).
    *   Cleans up the voting data for the completed session.

## File: `src/handlers/game_management/__init__.py`

*   **Package Interface:** Defines the public API for the `game_management` sub-package using `__all__`.
*   **Re-exporting:** Imports and makes key functions from its modules (like `create_game`, `join_game`, `start_game`, `eliminate_player`, `announce_voting`, etc.) directly accessible when importing from `src.handlers.game_management`.

---

## Potential Issues and Areas for Improvement

*   **State Management (Voting):** The `game_voting_data` dictionary in `src/handlers/game_management/voting.py` stores voting session state in memory. If the bot restarts, any ongoing voting sessions will be lost. Consider persisting voting state (e.g., current votes, who can vote/be voted on) in the database for greater resilience.
*   **State Management (General):** Extensive use of `context.user_data` (e.g., `game_id`, `action`, `current_page`) is standard but requires careful management to ensure state is cleared or updated correctly after actions are completed or cancelled to avoid unexpected behavior.
*   **Maintainability (`button_handler.py`):** The `handle_button` function is very long with many `elif` branches. This can become difficult to read and maintain. Consider refactoring by:
    *   Breaking down logic into smaller, more focused helper functions.
    *   Using a dictionary to map `callback_data` prefixes or patterns to specific handler functions for better organization.
*   **Database Initialization (`db.py`):** The schema migration logic (for `Games` table) and column addition checks run every time the bot starts. While functional, this could be optimized by checking `PRAGMA table_info` *before* attempting migrations or column additions to avoid unnecessary operations if the schema is already up-to-date.
*   **Action Resolution (`phase_manager.py`):** The `resolve_night_actions` function needs a robust implementation for handling action priorities (e.g., Doctor heal before Mafia kill, Sniper priority) as defined in `roles.json`. The current implementation sketch doesn't explicitly show priority handling.
*   **Configuration Security (`config.py`):** Storing secrets like the bot token and API key in a plain text file (`token.txt`) is convenient but not secure for production environments. Consider using environment variables or a dedicated secrets management solution.
*   **Error Handling (Granularity):** While the global error handler in `main.py` catches unexpected errors, some specific operations (like database writes, API calls, sending messages) within handlers could benefit from more specific `try...except` blocks to provide more context-aware feedback to the user or moderator upon failure.
*   **Callback Data Structure (`button_handler.py`):** Relying on splitting `callback_data` strings with underscores (e.g., `vote_`, `eliminate_confirm_`, action prompts) can be brittle if the format changes. Using a more structured format like JSON within the `callback_data` (mindful of Telegram's length limits) could be more robust.
*   **Concurrency (`db.py`):** While `check_same_thread=False` and `WAL` mode help, ensure complex operations involving multiple database reads/writes that need to be atomic are properly wrapped in transactions (`conn.commit()`, `conn.rollback()`). The role assignment in `roles_setup.py` uses a transaction correctly.
*   **Resource Management:** Explicitly closing the database connection on shutdown might be considered, although Python's garbage collection and process exit usually handle this for simple scripts.
*   **Live Data Reloading (`roles.py`):** Role templates (`role_templates`, `pending_templates`) are loaded at startup. If the `role_templates.json` file is modified externally while the bot runs, changes won't be reflected without a restart. This is likely acceptable but worth noting.