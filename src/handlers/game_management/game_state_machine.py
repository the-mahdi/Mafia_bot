from enum import Enum, auto
import logging
from src.db import conn, cursor
from telegram.ext import ContextTypes

logger = logging.getLogger("Mafia Bot GameStateMachine")

class GameState(Enum):
    """Enum representing all possible game states in the Mafia game."""
    PRE_GAME = auto()
    NIGHT = auto()
    NIGHT_RESOLVE = auto()
    DAY_ANNOUNCE = auto()
    DAY_DISCUSS = auto()
    VOTING = auto()
    VOTE_RESOLVE = auto()
    CHECK_WIN = auto()
    GAME_OVER = auto()

class GameStateMachine:
    """
    Manages the flow and transitions between different phases of the Mafia game.
    Ensures proper state tracking and consistent phase transitions.
    """
    
    def __init__(self):
        self.current_state = {}  # Dictionary mapping game_id to current state
        self.callbacks = {}  # Dictionary mapping states to handler functions

    def get_game_state(self, game_id: str) -> GameState:
        """Get the current state for a specific game."""
        if game_id in self.current_state:
            return self.current_state[game_id]
        
        # Load state from DB if not in memory
        cursor.execute("SELECT current_phase FROM Games WHERE game_id = ?", (game_id,))
        row = cursor.fetchone()
        if row and row[0]:
            try:
                state = GameState[row[0]]
                self.current_state[game_id] = state
                return state
            except KeyError:
                # Handle legacy phase names by mapping them to new states
                phase_mapping = {
                    'off': GameState.PRE_GAME,
                    'night': GameState.NIGHT,
                    'day': GameState.DAY_DISCUSS,
                }
                state = phase_mapping.get(row[0], GameState.PRE_GAME)
                self.current_state[game_id] = state
                return state
        
        # Default to PRE_GAME if no state found
        self.current_state[game_id] = GameState.PRE_GAME
        return GameState.PRE_GAME

    def set_game_state(self, game_id: str, state: GameState) -> None:
        """Set the state for a specific game and update the database."""
        self.current_state[game_id] = state
        
        # Update state in the database
        cursor.execute("UPDATE Games SET current_phase = ? WHERE game_id = ?", 
                     (state.name, game_id))
        conn.commit()
        logger.info(f"Game {game_id} state changed to {state.name}")

    def register_callback(self, state: GameState, callback):
        """Register a callback function to be called when a game enters a specific state."""
        self.callbacks[state] = callback
        return self  # Allow method chaining

    async def transition_to(self, update, context: ContextTypes.DEFAULT_TYPE, game_id: str, state: GameState) -> None:
        """
        Transition a game to a new state and execute the corresponding callback if registered.
        """
        prev_state = self.get_game_state(game_id)
        self.set_game_state(game_id, state)
        
        logger.info(f"Game {game_id} transitioned from {prev_state.name} to {state.name}")
        
        # Execute callback for the new state if registered
        if state in self.callbacks:
            await self.callbacks[state](update, context, game_id)
    
    async def next_state(self, update, context: ContextTypes.DEFAULT_TYPE, game_id: str) -> None:
        """
        Advance the game to the next state based on the standard game flow.
        """
        current = self.get_game_state(game_id)
        
        # Define the standard game flow transitions
        next_states = {
            GameState.PRE_GAME: GameState.NIGHT,
            GameState.NIGHT: GameState.NIGHT_RESOLVE,
            GameState.NIGHT_RESOLVE: GameState.DAY_ANNOUNCE,
            GameState.DAY_ANNOUNCE: GameState.DAY_DISCUSS,
            GameState.DAY_DISCUSS: GameState.VOTING,
            GameState.VOTING: GameState.VOTE_RESOLVE,
            GameState.VOTE_RESOLVE: GameState.CHECK_WIN,
            GameState.CHECK_WIN: GameState.NIGHT,  # If game continues, go back to night
            GameState.GAME_OVER: GameState.PRE_GAME  # Reset for a new game
        }
        
        if current in next_states:
            next_state = next_states[current]
            
            # Special case: if CHECK_WIN determines the game is over, go to GAME_OVER instead of NIGHT
            if current == GameState.CHECK_WIN:
                # Check if someone has won (implementation needed)
                cursor.execute("""
                SELECT 
                    SUM(CASE WHEN r.role IN (SELECT role FROM Roles WHERE game_id = ? AND role IN 
                        (SELECT role FROM roles WHERE faction = 'Mafia')) THEN 1 ELSE 0 END) as mafia_count,
                    SUM(CASE WHEN r.role IN (SELECT role FROM Roles WHERE game_id = ? AND role IN 
                        (SELECT role FROM roles WHERE faction = 'Villager')) THEN 1 ELSE 0 END) as villager_count
                FROM Roles r
                WHERE r.game_id = ? AND r.eliminated = 0
                """, (game_id, game_id, game_id))
                
                counts = cursor.fetchone()
                if counts:
                    mafia_count, villager_count = counts
                    
                    # Game over conditions
                    if mafia_count >= villager_count:  # Mafia wins
                        next_state = GameState.GAME_OVER
                    elif mafia_count == 0:  # Villagers win
                        next_state = GameState.GAME_OVER
            
            await self.transition_to(update, context, game_id, next_state)
        else:
            logger.warning(f"No transition defined for state {current.name} in game {game_id}")

# Create a singleton instance
state_machine = GameStateMachine()