# TODOs: Project Modularization Plan

## 1. Introduction

This document outlines the plan to significantly modularize the Mafia Bot project. The primary goals are:

1.  **Improve Maintainability:** Make the codebase easier to understand, modify, and debug.
2.  **Enhance Scalability:** Prepare the architecture for a large increase in roles (~80 more planned) and potentially more complex game mechanics.
3.  **Reduce File Size:** Break down large files like `button_handler.py` and `phase_manager.py` into smaller, focused modules.
4.  **Increase Testability:** Smaller, independent modules are easier to unit test.
5.  **Promote Reusability:** Well-defined modules can be reused more effectively.

## 2. Guiding Principles

*   **Single Responsibility Principle (SRP):** Each module or class should have one primary reason to change.
*   **Separation of Concerns:** Different aspects of the application (e.g., Telegram interaction, game logic, database access, role definitions) should be handled by distinct modules.
*   **Dependency Inversion:** High-level modules should not depend on low-level modules directly; both should depend on abstractions (e.g., using interfaces or dependency injection if needed, though simpler function/module separation might suffice initially).
*   **Clear Interfaces:** Modules should interact through well-defined functions or methods.

## 3. Proposed Target Directory Structure

This structure aims to separate concerns more effectively:
Use code with caution.
Markdown
mafia_bot/
├── main.py # Entry point, minimal setup
├── logs/ # Log files
├── db/
│ └── mafia_game.db # SQLite database file
├── data/
│ ├── roles.json # Core role definitions (consider splitting later if huge)
│ ├── role_templates.json # Role templates
│ └── token.txt # Bot token, API keys
├── src/
│ ├── init.py
│ ├── core/ # Core bot setup and utilities
│ │ ├── init.py
│ │ ├── application.py # Bot application setup (from main.py)
│ │ ├── logging_config.py # Logging setup (from main.py)
│ │ ├── error_handler.py # Central error handler (from main.py)
│ │ └── config.py # Configuration loading (current src/config.py)
│ ├── database/ # Database interaction layer
│ │ ├── init.py
│ │ ├── connection.py # Connection setup, PRAGMAs (from src/db.py)
│ │ ├── schema.py # Table creation/migration logic (from src/db.py)
│ │ ├── game_queries.py # Functions to query/update Games table
│ │ ├── user_queries.py # Functions to query/update Users table
│ │ ├── role_queries.py # Functions to query/update Roles, GameRoles tables
│ │ ├── action_queries.py # Functions to query/update Actions table
│ │ └── vote_queries.py # Functions to query/update VotingSessions, VoterPermissions, Votes tables
│ ├── handlers/ # Telegram command and callback handlers (more granular)
│ │ ├── init.py
│ │ ├── start.py # /start command handler (from src/handlers/start_handler.py)
│ │ ├── text_input.py # Handles general text input (passcode, name, template name) (from src/handlers/passcode_handler.py)
│ │ ├── menu_callbacks.py # Handles main menu buttons (create, join, etc.) (from src/handlers/button_handler.py)
│ │ ├── role_setup_callbacks.py # Handles role selection (+/-), confirm, template selection (from src/handlers/button_handler.py)
│ │ ├── game_management_callbacks.py # Handles manage game menu (start, eliminate, revive, inquiry) (from src/handlers/button_handler.py)
│ │ ├── voting_callbacks.py # Handles voting buttons (vote_, confirm_, permission toggles) (from src/handlers/button_handler.py)
│ │ ├── action_callbacks.py # Handles night/day action buttons (prompt, action_target_*) (from src/handlers/button_handler.py)
│ │ └── admin_callbacks.py # Handles maintainer confirmation buttons (from src/handlers/button_handler.py)
│ ├── game/ # Core game logic (moved from src/handlers/game_management)
│ │ ├── init.py
│ │ ├── state_machine.py # Game state management (current src/handlers/game_management/game_state_machine.py)
│ │ ├── phase_manager.py # Orchestrates phase transitions, delegates action resolution (refactored src/handlers/game_management/phase_manager.py)
│ │ ├── actions/ # Role-specific action logic
│ │ │ ├── init.py
│ │ │ ├── action_resolver.py # Central function to resolve actions based on priority, calling specific role actions
│ │ │ ├── mafia_actions.py # Logic for Mafia kill, God F double kill
│ │ │ ├── doctor_actions.py # Logic for healing
│ │ │ ├── investigator_actions.py # Logic for investigation
│ │ │ ├── sniper_actions.py # Logic for sniper shot
│ │ │ ├── cowboy_actions.py # Logic for cowboy shot
│ │ │ ├── gunsmith_actions.py # Logic for gun distribution
│ │ │ ├── bartender_actions.py # Logic for intoxication
│ │ │ ├── ... (add files for other complex roles/factions as needed) ...
│ │ │ └── base_action.py # (Optional) Base class or common functions for actions
│ │ ├── roles/ # Role-specific logic (e.g., win conditions, passive effects)
│ │ │ ├── init.py
│ │ │ ├── role_manager.py # Loads and provides access to role data (refactored src/roles.py)
│ │ │ ├── win_conditions.py # Logic to check win conditions (refactored from phase_manager.py/check_win_condition)
│ │ │ ├── ... (add files for roles with complex passive logic or state if needed) ...
│ │ ├── setup/ # Game setup logic
│ │ │ ├── init.py
│ │ │ ├── create.py # Game creation (from src/handlers/game_management/create_game.py)
│ │ │ ├── join.py # Player joining (from src/handlers/game_management/join_game.py)
│ │ │ ├── role_assignment.py # Role selection UI and assignment logic (from src/handlers/game_management/roles_setup.py)
│ │ │ └── start.py # Starting the game, sending roles (from src/handlers/game_management/start_game.py)
│ │ ├── player_management.py # Eliminate/revive logic (current src/handlers/game_management/player_management.py)
│ │ ├── voting.py # Voting logic (current src/handlers/game_management/voting.py)
│ │ ├── inquiry.py # Inquiry logic (current src/handlers/game_management/inquiry.py)
│ │ └── utils.py # Game-specific utilities (e.g., shuffling - from base.py)
│ └── utils/ # General utilities (non-domain specific)
│ ├── init.py
│ ├── path.py # resource_path function (from src/utils.py)
│ ├── context.py # clear_user_data function (from src/utils.py)
│ └── formatting.py # generate_voting_summary, escape_markdown (from src/utils.py and imports)
└── requirements.txt # Project dependencies
## 4. Detailed TODOs

### Phase 1: Restructure and Basic Separation

*   **[✓] Create New Directory Structure:**
    *   Create the `src/core`, `src/database`, `src/game`, `src/game/actions`, `src/game/roles`, `src/game/setup`, `src/utils` directories.
    *   Create `__init__.py` files in all new Python package directories.
*   **[✓] Move Core Bot Logic:**
    *   Move logging setup from `main.py` to `src/core/logging_config.py`.
    *   Move error handler from `main.py` to `src/core/error_handler.py`.
    *   Move application building and handler registration from `main.py` to `src/core/application.py`.
    *   Update `main.py` to import and call setup functions from `src/core`. `main.py` should become very lean.
    *   Move `src/config.py` to `src/core/config.py`. Update imports.
*   **[✓] Move Utilities:**
    *   Move `resource_path` from `src/utils.py` to `src/utils/path.py`.
    *   Move `clear_user_data` from `src/utils.py` to `src/utils/context.py`.
    *   Move `generate_voting_summary` from `src/utils.py` to `src/utils/formatting.py`. Add `escape_markdown` helper here too.
    *   Update all imports referencing these utilities. Delete the old `src/utils.py`.
*   **[✓] Separate Database Logic:**
    *   Create `src/database/connection.py`: Move `sqlite3.connect`, `conn`, `cursor` creation, and `PRAGMA` statements here. Export `conn` and `cursor` (or preferably, functions to get them).
    *   Create `src/database/schema.py`: Move `initialize_database` function here. It should import the connection from `connection.py`.
    *   Update `main.py` (or `src/core/application.py`) to call the schema initialization function.
    *   Update all files currently importing `conn`, `cursor` from `src/db.py` to import from `src/database/connection.py`. Delete the old `src/db.py`.
*   **[✓] Move Game Management Logic:**
    *   Move `src/handlers/game_management/*` files to the corresponding locations under `src/game/` or `src/game/setup/` as per the proposed structure.
        *   `base.py` -> `src/game/utils.py` (for shuffling, player count, templates) ✓
        *   `create_game.py` -> `src/game/setup/create.py`
        *   `join_game.py` -> `src/game/setup/join.py`
        *   `roles_setup.py` -> `src/game/setup/role_assignment.py`
        *   `start_game.py` -> `src/game/setup/start.py`
        *   `player_management.py` -> `src/game/player_management.py`
        *   `voting.py` -> `src/game/voting.py`
        *   `inquiry.py` -> `src/game/inquiry.py`
        *   `game_state_machine.py` -> `src/game/state_machine.py`
        *   `phase_manager.py` -> `src/game/phase_manager.py` (will be heavily refactored later)
    *   Update all imports within these moved files and in the handlers that use them. Delete the old `src/handlers/game_management/` directory.
*   **[✓] Move Role Loading Logic:**
    *   Move `src/roles.py` to `src/game/roles/role_manager.py`.
    *   Refactor `role_manager.py`: Instead of global variables (`roles`, `available_roles`, etc.), create a `RoleManager` class or functions to load and provide access to role data (descriptions, factions, actions). This prepares for potentially more complex loading later. Update imports.

### Phase 2: Handler Decomposition

*   **[✓] Split `button_handler.py`:**
    *   Create `src/handlers/menu_callbacks.py`: Move logic for `create_game`, `join_game`, `set_roles`, `select_template`, `manage_games`, `back_to_menu`, `keep_name`, `change_name`.
    *   Create `src/handlers/role_setup_callbacks.py`: Move logic for `increase_*`, `decrease_*`, `prev_page`, `next_page`, `reset_roles`, `confirm_roles`, `confirm_roles_and_save_template`, `template_*`.
    *   Create `src/handlers/game_management_callbacks.py`: Move logic for `start_game_manage_games`, `eliminate_player`, `revive_player`, `inquiry_summary`, `inquiry_detailed`, `eliminate_confirm_*`, `eliminate_yes_*`, `eliminate_cancel_*`, `revive_confirm_*`, `revive_yes_*`, `revive_cancel_*`. (Note: `announce_voting` buttons might fit better in `voting_callbacks.py`).
    *   Create `src/handlers/voting_callbacks.py`: Move logic for `announce_voting`, `announce_anonymous_voting`, `vote_*`, `confirm_votes`, `final_confirm_vote_*`, `cancel_vote_*`, `toggle_can_vote_*`, `toggle_can_be_voted_*`, `confirm_permissions`.
    *   Create `src/handlers/action_callbacks.py`: Move logic for night/day action prompts (`*_prompt_*`) and target selections (`action_target_*`), including the `double_kill_*` logic. Move the `perform_action` helper function here or into `src/game/actions/action_resolver.py`.
    *   Create `src/handlers/admin_callbacks.py`: Move logic for `maintainer_confirm_*`, `maintainer_reject_*`.
    *   Update `src/core/application.py`: Register *all* these new callback handlers, potentially using more specific `pattern` arguments in `CallbackQueryHandler`.
    *   Delete the old `src/handlers/button_handler.py`.
*   **[✓] Split `passcode_handler.py`:**
    *   Rename to `src/handlers/text_input.py`.
    *   Ensure it clearly handles different states (`awaiting_name`, `join_game`, `awaiting_template_name_confirmation`) based on `context.user_data['action']`.
    *   Move the template confirmation logic (`handle_template_confirmation`, `save_template_as_pending`) to `src/game/setup/role_assignment.py`.
    *   Update handler registration in `src/core/application.py`.
*   **[✓] Refactor `start_handler.py`:**
    *   Rename to `src/handlers/start.py`. Update registration. Ensure it only handles the `/start` command and displays the initial menu.

### Phase 3: Game Logic Decomposition

*   **[ ] Refactor `phase_manager.py` (`src/game/phase_manager.py`):**
    *   **Goal:** This file should orchestrate phase transitions (calling `state_machine`) and delegate action resolution, not contain the logic for every single action.
    *   Create `src/game/actions/action_resolver.py`. This module will contain the core `resolve_night_actions` (or similar) logic.
    *   `action_resolver.py` should:
        *   Fetch all actions for the phase from the database (using `action_queries.py`).
        *   Get role definitions (using `role_manager.py`) to determine action priorities.
        *   Sort actions by priority.
        *   Iterate through sorted actions and *delegate* execution to specific functions based on the action command (e.g., call `mafia_actions.kill()`, `doctor_actions.heal()`). Maintain game state relevant to resolution (e.g., `healed_players`, `kill_targets`, `protected_players`).
        *   Handle interactions (e.g., heal cancels kill).
        *   Apply final outcomes (eliminations, status effects) by updating the database (using `role_queries.py`, `player_management.py`).
    *   Create individual action files in `src/game/actions/` (e.g., `mafia_actions.py`, `doctor_actions.py`, etc.) for each role or group of roles with actions. These files will contain the specific logic for *how* an action affects the game state or targets.
    *   Modify `src/game/phase_manager.py` to call the main function in `action_resolver.py` during the `NIGHT_RESOLVE` state transition. Remove the detailed action logic from `phase_manager.py`.
    *   Move `check_win_condition` logic from `phase_manager.py` to `src/game/roles/win_conditions.py`. `phase_manager.py` (or the state machine callback) will call this.
    *   Move `update_player_elimination_status` to `src/game/player_management.py`.
*   **[ ] Refactor `voting.py` (`src/game/voting.py`):**
    *   Ensure all database interactions use the new `vote_queries.py` functions.
    *   Review the use of `game_voting_cache`. Ensure essential state is always persisted to the DB and the cache is used primarily for UI state during an active operation.
    *   Consider creating a `VotingManager` class if the logic becomes very complex.
*   **[✓] Refactor Role System (`src/game/roles/`):**
    *   Enhance `src/game/roles/role_manager.py`: Load roles from `roles.json`. Provide functions like `get_role_data(role_name)`, `get_role_actions(role_name, phase)`, `get_role_faction(role_name)`, `get_action_priority(role_name, action_command)`.
    *   Define a more structured `data/roles.json`:
        *   Clearly define `faction`, `description`.
        *   Structure `actions` per phase (`night`, `day`).
        *   For each action, include: `command` (unique identifier), `description` (for buttons), `priority` (integer, higher executes first), `targets` (number of targets: 0, 1, 2, 'all', 'faction'), `target_filter` (e.g., 'alive', 'not_self', 'not_mafia', 'faction:Villager'), `interactive` ('button' or 'passive'), `self_target` (boolean), `effect` (description of what it does - maybe link to function in `src/game/actions/`?).
        *   Add fields for passive abilities, win conditions (if simple), interaction rules.

### Phase 4: Database Abstraction & Refinement

*   **[ ] Implement Database Query Modules:**
    *   Create `src/database/game_queries.py`, `user_queries.py`, `role_queries.py`, `action_queries.py`, `vote_queries.py`.
    *   Move *all* SQL queries from other modules into these files as distinct functions (e.g., `create_new_game(moderator_id)`, `get_game_by_passcode(passcode)`, `get_players_in_game(game_id)`, `add_player_to_game(game_id, user_id)`, `set_player_role(game_id, user_id, role)`, `record_action(...)`, `get_night_actions(game_id)`, `update_player_eliminated(...)`, etc.).
    *   Functions should take necessary arguments and return processed data (e.g., list of dicts, single value).
    *   Refactor all modules (`handlers/*`, `game/*`) to import and use these query functions instead of directly accessing `cursor.execute`. This centralizes SQL and makes schema changes easier.
*   **[ ] Review Database Schema:**
    *   With ~80 new roles, consider if the current schema is sufficient.
    *   Will roles need persistent state beyond `eliminated`? (e.g., number of uses left, specific targets tracked). The `Roles.metadata` JSON column is flexible but can become hard to query. Consider dedicated columns or tables for common role states if necessary.
    *   Is the `Actions` table sufficient for complex multi-target actions or actions with delayed effects?
*   **[ ] Refine State Management:**
    *   Review the use of `context.user_data` and `context.chat_data`. Ensure data is cleared appropriately (`clear_user_data`) to prevent state leakage between interactions.
    *   Document what keys are expected in `user_data` for different states (`action`, `game_id`, `current_page`, etc.).
    *   Ensure the `GameStateMachine` (`src/game/state_machine.py`) is the single source of truth for the *current game phase*. Handlers and game logic should query the state machine, not rely on potentially stale `user_data`.

### Phase 5: Testing and Documentation

*   **[ ] Implement Unit Tests:**
    *   Start adding unit tests for the new, smaller modules, especially:
        *   Database query functions (`src/database/*_queries.py`).
        *   Role-specific action logic (`src/game/actions/*`).
        *   Utility functions (`src/utils/*`).
        *   State machine transitions (`src/game/state_machine.py`).
    *   Use `unittest` or `pytest`. Mock database connections and Telegram API calls where necessary.
*   **[ ] Add Integration Tests:**
    *   Test the interaction between handlers, game logic, and the database for key flows (e.g., creating a game, joining, setting roles, a full night/day cycle, voting).
*   **[ ] Improve Code Documentation:**
    *   Add docstrings to all new modules, classes, and functions explaining their purpose, arguments, and return values.
    *   Add comments to complex logic sections.
*   **[ ] Update README:**
    *   Reflect the new project structure.
    *   Explain how to run the bot and any setup required.

## 5. Prioritization and Approach

1.  **Phase 1 (Foundation):** Focus on creating the new structure and moving files without major logic changes. This sets the stage.
2.  **Phase 2 (Handlers):** Decompose the monolithic handlers (`button_handler`, `passcode_handler`). This is crucial for managing complexity.
3.  **Phase 4 (Database Abstraction):** Implement the query modules. This should be done *before* heavily refactoring game logic, as it provides a stable interface to the data.
4.  **Phase 3 (Game Logic):** Refactor `phase_manager` and implement the `src/game/actions/` structure. Define the `roles.json` structure. This is where the core complexity of adding new roles lies.
5.  **Phase 5 (Testing & Docs):** Integrate testing and documentation throughout the process, but dedicate specific effort after major refactoring phases.

**Note:** Perform these changes incrementally. Use version control (Git) extensively, committing after each logical step. Test frequently after changes.

## 6. Conclusion

This modularization effort is a significant undertaking but essential for the long-term health and scalability of the Mafia Bot project, especially with the planned addition of many new roles. By following these steps, the codebase will become cleaner, more organized, easier to extend, and less prone to errors.