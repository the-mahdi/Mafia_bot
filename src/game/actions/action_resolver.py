import json
import logging
import random
from collections import defaultdict, namedtuple
from typing import Dict, List, Set, Tuple, Any, Optional

from telegram.ext import ContextTypes
from src.database.connection import conn, cursor

# Role manager imports
from src.game.roles.role_manager import (
    get_action_priority, 
    get_role_faction,
    get_action_by_command
)

# Import role-specific action handlers
from src.game.actions.role_actions.doctor_actions import handle_heal_action
from src.game.actions.role_actions.sniper_actions import handle_sniper_shot
from src.game.actions.role_actions.cowboy_actions import handle_cowboy_shot
from src.game.actions.role_actions.mafia_actions import (
    handle_mafia_kill, 
    handle_double_kill, 
    handle_joker_action, 
    handle_doctor_lec_save,
    handle_natasha_silence,
    apply_mafia_kills
)
from src.game.actions.role_actions.investigator_actions import handle_investigation_action

logger = logging.getLogger("Mafia Bot ActionResolver")

# Define a namedtuple for action data
Action = namedtuple('Action', ['user_id', 'role', 'action_command', 'target_id', 'action_def', 'priority'])

# Game state to track during action resolution
class GameState:
    def __init__(self):
        self.kill_targets = set()
        self.healed_players = set()
        self.eliminated_players = []
        self.intoxicated_players = set()
        self.gun_distributions = {}
        self.ruyin_tan_immunity = {}
        self.mashoghe_died = False

async def fetch_night_actions(game_id: str) -> List[Tuple[str, str, str]]:
    """Fetch all night actions for a game from the database."""
    cursor.execute("SELECT user_id, action, target_id FROM Actions WHERE game_id = ? AND phase = 'night'", (game_id,))
    return cursor.fetchall()

def prioritize_actions(actions_data: List[Tuple[str, str, str]]) -> List[Action]:
    """Sort actions by their priority (higher values execute first)."""
    prioritized_actions = []
    
    for user_id, action_command, target_id in actions_data:
        # Get user's role
        cursor.execute("SELECT role FROM Roles WHERE game_id = ? AND user_id = ?", (game_id, user_id))
        role_result = cursor.fetchone()
        if not role_result:
            logger.warning(f"Role not found for user {user_id} in game {game_id}")
            continue
        
        role = role_result[0]
        
        # Get the action definition
        action_def = get_action_by_command(role, action_command)
        if not action_def:
            logger.warning(f"Action definition not found for {action_command} of role {role}")
            continue
        
        # Get priority, default to 0 if not specified
        priority = action_def.get('priority', 0)
        
        # Add to list with priority
        prioritized_actions.append(Action(user_id, role, action_command, target_id, action_def, priority))
    
    # Sort actions by priority (higher values first)
    return sorted(prioritized_actions, key=lambda x: x.priority, reverse=True)

async def initialize_game_state(game_id: str) -> GameState:
    """Initialize game state with pre-existing conditions."""
    state = GameState()
    
    # Check for Ruyin Tan (Bulletproof) players immunity status
    cursor.execute("""
    SELECT user_id, metadata FROM Roles 
    WHERE game_id = ? AND role = 'Ruyin tan' AND eliminated = 0
    """, (game_id,))
    
    ruyin_tan_players = cursor.fetchall()
    for user_id, metadata in ruyin_tan_players:
        if metadata:
            try:
                metadata_dict = json.loads(metadata)
                state.ruyin_tan_immunity[user_id] = metadata_dict.get('immunity_used', False)
            except json.JSONDecodeError:
                # If metadata exists but is not valid JSON, set immunity to False (not used yet)
                state.ruyin_tan_immunity[user_id] = False
                # Fix invalid metadata
                cursor.execute(
                    "UPDATE Roles SET metadata = ? WHERE game_id = ? AND user_id = ?", 
                    (json.dumps({"immunity_used": False}), game_id, user_id)
                )
                logger.warning(f"Invalid metadata for Ruyin Tan player {user_id}. Reset to default.")
        else:
            # If no metadata exists, initialize it with immunity_used=False
            state.ruyin_tan_immunity[user_id] = False
            cursor.execute(
                "UPDATE Roles SET metadata = ? WHERE game_id = ? AND user_id = ?", 
                (json.dumps({"immunity_used": False}), game_id, user_id)
            )
            logger.debug(f"Initialized Ruyin Tan metadata for player {user_id}")
    
    return state

async def handle_kill_action(user_id: str, target_id: str, game_state: GameState, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle standard Mafia kill action."""
    if target_id:
        game_state.kill_targets.add(target_id)

async def handle_sniper_shot_action(game_id: str, user_id: str, target_id: str, game_state: GameState, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle Sniper shot action."""
    if not target_id:
        return
        
    # Check if target is Villager or not
    cursor.execute("SELECT role FROM Roles WHERE game_id = ? AND user_id = ?", (game_id, target_id))
    target_role_result = cursor.fetchone()
    if not target_role_result:
        return
    
    target_role = target_role_result[0]
    target_faction = get_role_faction(target_role)
    
    if target_faction != "Villager":
        # Target is not a villager, kill them if not healed
        if target_id not in game_state.healed_players:
            # Check if target is Ruyin tan (Bulletproof) with unused immunity
            is_immune = False
            if target_role == "Ruyin tan" and not game_state.ruyin_tan_immunity.get(target_id, True):
                # Mark immunity as used
                cursor.execute(
                    "UPDATE Roles SET metadata = ? WHERE game_id = ? AND user_id = ?", 
                    (json.dumps({"immunity_used": True}), game_id, target_id)
                )
                is_immune = True
                await context.bot.send_message(
                    chat_id=target_id, 
                    text="You were targeted by the Sniper, but your bulletproof vest saved you! (This works only once)"
                )
            
            if not is_immune:
                cursor.execute("SELECT username FROM Users WHERE user_id = ?", (target_id,))
                username = cursor.fetchone()[0]
                game_state.eliminated_players.append((target_id, username, "sniper"))
                await context.bot.send_message(chat_id=target_id, text="You have been eliminated by the Sniper!")
    else:
        # Target is a villager, kill both target and sniper
        if target_id not in game_state.healed_players:
            # Check if target is Ruyin tan with unused immunity
            is_immune = False
            if target_role == "Ruyin tan" and not game_state.ruyin_tan_immunity.get(target_id, True):
                # Mark immunity as used
                cursor.execute(
                    "UPDATE Roles SET metadata = ? WHERE game_id = ? AND user_id = ?", 
                    (json.dumps({"immunity_used": True}), game_id, target_id)
                )
                is_immune = True
            
            if not is_immune:
                cursor.execute("SELECT username FROM Users WHERE user_id = ?", (target_id,))
                username = cursor.fetchone()[0]
                game_state.eliminated_players.append((target_id, username, "sniper"))
                await context.bot.send_message(chat_id=target_id, text="You have been eliminated by the Sniper!")
        
        # Kill sniper too - they shot a villager
        cursor.execute("SELECT username FROM Users WHERE user_id = ?", (user_id,))
        username = cursor.fetchone()[0]
        game_state.eliminated_players.append((user_id, username, "sniper_backfire"))
        await context.bot.send_message(
            chat_id=user_id, 
            text="You have been eliminated because you shot a Villager!"
        )

async def handle_cowboy_shot_action(game_id: str, user_id: str, target_id: str, game_state: GameState, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle Cowboy shot action."""
    if not target_id:
        return
        
    # Check if target is Ruyin tan (Bulletproof) with unused immunity
    is_immune = False
    
    # Get target's role
    cursor.execute("SELECT role, metadata FROM Roles WHERE game_id = ? AND user_id = ?", (game_id, target_id))
    target_result = cursor.fetchone()
    if target_result:
        target_role, target_metadata = target_result
        
        # Check for Bulletproof immunity
        if target_role == "Ruyin tan":
            # Parse metadata to check if immunity was already used
            immunity_used = True  # Default to true (no immunity) if can't determine
            if target_metadata:
                try:
                    metadata_dict = json.loads(target_metadata)
                    immunity_used = metadata_dict.get('immunity_used', False)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid metadata for Ruyin Tan player {target_id}")
            
            if not immunity_used:
                # Mark immunity as used
                cursor.execute(
                    "UPDATE Roles SET metadata = ? WHERE game_id = ? AND user_id = ?", 
                    (json.dumps({"immunity_used": True}), game_id, target_id)
                )
                is_immune = True
                await context.bot.send_message(
                    chat_id=target_id, 
                    text="You were targeted by the Cowboy, but your bulletproof vest saved you! (This works only once)"
                )
                
                # Notify the Cowboy that their shot was blocked
                await context.bot.send_message(
                    chat_id=user_id,
                    text="Your target was wearing a bulletproof vest! Your shot was ineffective."
                )
                
                # Cowboy still gets eliminated after using their ability
                cursor.execute("SELECT username FROM Users WHERE user_id = ?", (user_id,))
                username = cursor.fetchone()[0]
                game_state.eliminated_players.append((user_id, username, "cowboy_self"))
                await context.bot.send_message(
                    chat_id=user_id, 
                    text="You have left the game after using your Cowboy shot!"
                )
                return  # Skip to next action
    
    # If not immune, proceed with normal elimination
    if not is_immune:
        # Mark target for elimination
        cursor.execute("SELECT username FROM Users WHERE user_id = ?", (target_id,))
        username = cursor.fetchone()[0]
        game_state.eliminated_players.append((target_id, username, "cowboy"))
        await context.bot.send_message(chat_id=target_id, text="You have been eliminated by the Cowboy!")
        
        # Cowboy also gets eliminated after using their ability
        cursor.execute("SELECT username FROM Users WHERE user_id = ?", (user_id,))
        username = cursor.fetchone()[0]
        game_state.eliminated_players.append((user_id, username, "cowboy_self"))
        await context.bot.send_message(
            chat_id=user_id, 
            text="You have left the game after using your Cowboy shot!"
        )

async def handle_distribute_guns_action(game_id: str, user_id: str, target_id: str, game_state: GameState, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle Gunsmith (Tof Dar) distribute guns action."""
    if not target_id:
        return
        
    # For this action, we need to get both targets and determine which gets real/fake guns
    cursor.execute("""
    SELECT target_id FROM Actions 
    WHERE game_id = ? AND phase = 'night' AND action = 'distribute_guns' AND user_id = ?
    """, (game_id, user_id))
    gun_targets = [row[0] for row in cursor.fetchall()]
    
    if len(gun_targets) == 2:
        # Randomly decide which target gets the real gun
        real_gun_target = random.choice(gun_targets)
        
        # Store gun distribution in database
        for target in gun_targets:
            has_real_gun = target == real_gun_target
            
            # Check if player already has guns tracked
            cursor.execute("""
            SELECT metadata FROM Roles WHERE game_id = ? AND user_id = ?
            """, (game_id, target))
            
            metadata_row = cursor.fetchone()
            metadata = {}
            
            if metadata_row and metadata_row[0]:
                try:
                    metadata = json.loads(metadata_row[0])
                except:
                    metadata = {}
            
            # Update gun information
            if 'guns' not in metadata:
                metadata['guns'] = []
            
            metadata['guns'].append({
                'real': has_real_gun,
                'night': len(metadata['guns']) + 1,  # Track the night number for this gun
                'used': False
            })
            
            cursor.execute("""
            UPDATE Roles SET metadata = ? WHERE game_id = ? AND user_id = ?
            """, (json.dumps(metadata), game_id, target))
            
            # Notify players
            message = "The Gunsmith has given you a gun. "
            message += "You'll be able to use it during the day phase."
            
            await context.bot.send_message(
                chat_id=target,
                text=message
            )
        
        # Notify the Gunsmith
        await context.bot.send_message(
            chat_id=user_id,
            text=f"You have distributed guns to the selected players."
        )

async def handle_intoxicate_action(user_id: str, target_id: str, game_state: GameState, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle Bartender intoxicate action."""
    if target_id:
        game_state.intoxicated_players.add(target_id)
        await context.bot.send_message(
            chat_id=user_id,
            text=f"You have successfully intoxicated your target."
        )

async def apply_mafia_kills(game_id: str, game_state: GameState, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Apply standard mafia kills that weren't handled by special actions."""
    for target_id in game_state.kill_targets:
        if target_id not in game_state.healed_players:
            # Check if target is already eliminated (e.g., by sniper)
            cursor.execute("SELECT eliminated, role FROM Roles WHERE game_id = ? AND user_id = ?", (game_id, target_id))
            result = cursor.fetchone()
            if result and result[0] == 0:  # not yet eliminated
                role = result[1]
                
                # Check if target is Mashoghe - track if they're killed
                if role == "Mashoghe":
                    game_state.mashoghe_died = True
                    logger.debug(f"Mashoghe (user_id: {target_id}) was killed during this night.")
                
                # Check if target is Ruyin tan (Bulletproof) with unused immunity
                is_immune = False
                if role == "Ruyin tan" and not game_state.ruyin_tan_immunity.get(target_id, True):
                    # Mark immunity as used
                    cursor.execute(
                        "UPDATE Roles SET metadata = ? WHERE game_id = ? AND user_id = ?", 
                        (json.dumps({"immunity_used": True}), game_id, target_id)
                    )
                    is_immune = True
                    await context.bot.send_message(
                        chat_id=target_id, 
                        text="You were targeted by the Mafia, but your bulletproof vest saved you! (This works only once)"
                    )
                
                # Check if target is ToughGuy (can survive one attack)
                if role == "ToughGuy" and not is_immune:
                    # Check if already hit once
                    cursor.execute("SELECT metadata FROM Roles WHERE game_id = ? AND user_id = ?", (game_id, target_id))
                    metadata_row = cursor.fetchone()
                    metadata = {}
                    
                    if metadata_row and metadata_row[0]:
                        try:
                            metadata = json.loads(metadata_row[0])
                        except:
                            metadata = {}
                    
                    hit_before = metadata.get('hit_before', False)
                    
                    if not hit_before:
                        # First hit - survive but mark as hit
                        metadata['hit_before'] = True
                        cursor.execute(
                            "UPDATE Roles SET metadata = ? WHERE game_id = ? AND user_id = ?", 
                            (json.dumps(metadata), game_id, target_id)
                        )
                        await context.bot.send_message(
                            chat_id=target_id, 
                            text="You were attacked but survived due to your toughness! A second attack will be fatal."
                        )
                        is_immune = True
                
                if not is_immune:
                    cursor.execute("SELECT username FROM Users WHERE user_id = ?", (target_id,))
                    username = cursor.fetchone()[0]
                    game_state.eliminated_players.append((target_id, username, "mafia_kill"))
                    await context.bot.send_message(chat_id=target_id, text="You have been eliminated during the night!")

async def consolidate_eliminations(game_id: str, game_state: GameState, context: ContextTypes.DEFAULT_TYPE) -> List[Tuple[str, str]]:
    """Process all eliminations and apply them at once, returning a list of eliminated players."""
    from src.game.player_management import update_player_elimination_status
    
    logger.debug(f"Consolidating night outcomes: {len(game_state.eliminated_players)} players targeted for elimination")
    
    # Create a dictionary to deduplicate and track eliminations
    # This ensures each player is only eliminated once, with priority given to earliest elimination cause
    elimination_dict = {}
    for user_id, username, cause in game_state.eliminated_players:
        if user_id not in elimination_dict:
            elimination_dict[user_id] = (username, cause)
    
    # Apply all eliminations at once
    final_eliminated = []
    for user_id, (username, cause) in elimination_dict.items():
        # Check again if the player was Mashoghe
        cursor.execute("SELECT role FROM Roles WHERE game_id = ? AND user_id = ?", (game_id, user_id))
        role_result = cursor.fetchone()
        if role_result and role_result[0] == "Mashoghe":
            game_state.mashoghe_died = True
            logger.debug(f"Confirmed Mashoghe (user_id: {user_id}) was eliminated with cause: {cause}")
        
        # Update player elimination status using the centralized function
        await update_player_elimination_status(game_id, user_id, True, cause)
        # Save for announcement (without the cause)
        final_eliminated.append((user_id, username))
    
    return final_eliminated

async def handle_mashoghe_death(game_id: str, game_state: GameState, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle special game effects if Mashoghe died this night."""
    if not game_state.mashoghe_died:
        return
        
    logger.info(f"Mashoghe died in game {game_id}, enabling double kill for mafia next night")
    
    # Get the Games table metadata
    cursor.execute("SELECT metadata FROM Games WHERE game_id = ?", (game_id,))
    game_metadata_row = cursor.fetchone()
    game_metadata = {}
    
    if game_metadata_row and game_metadata_row[0]:
        try:
            game_metadata = json.loads(game_metadata_row[0])
        except json.JSONDecodeError:
            logger.warning(f"Invalid metadata for game {game_id}, initializing as empty")
            game_metadata = {}
    
    # Set the flag for double kill next night
    game_metadata['mafia_double_kill_enabled'] = True
    # Store the night number when this happened for potential future reference
    current_night = game_metadata.get('current_night', 1)
    game_metadata['mashoghe_died_night'] = current_night
    
    # Update the database
    cursor.execute(
        "UPDATE Games SET metadata = ? WHERE game_id = ?", 
        (json.dumps(game_metadata), game_id)
    )
    conn.commit()
    
    # Find God F player to notify them about the double kill ability
    cursor.execute("SELECT user_id FROM Roles WHERE game_id = ? AND role = 'God F' AND eliminated = 0", (game_id,))
    god_f_player = cursor.fetchone()
    if god_f_player:
        await context.bot.send_message(
            chat_id=god_f_player[0],
            text="The Lover (Mashoghe) has been eliminated! Your fury grows - you can kill TWO players on the next night. You will be given the opportunity to select two targets at the start of the next night phase."
        )

async def resolve_night_actions(game_id: str, update: Any, context: ContextTypes.DEFAULT_TYPE) -> List[Tuple[str, str]]:
    """
    Resolve all night actions for a game.
    
    Returns a list of (user_id, username) tuples of eliminated players.
    """
    logger.debug(f"Resolving night actions for game {game_id}")
    
    # Fetch all night actions
    actions_data = await fetch_night_actions(game_id)
    
    # No actions to process
    if not actions_data:
        logger.debug("No night actions recorded for this game")
        return []
    
    # Prepare actions with priority
    prioritized_actions = prioritize_actions(actions_data)
    logger.debug(f"Sorted {len(prioritized_actions)} night actions by priority")
    
    # Initialize game state
    game_state = await initialize_game_state(game_id)
    
    # Process actions in priority order
    for action in prioritized_actions:
        logger.debug(f"Processing action {action.action_command} from {action.role} with priority {action.priority}")
        
        # Skip actions from intoxicated players (Bartender effect)
        if action.user_id in game_state.intoxicated_players:
            logger.debug(f"Player {action.user_id} is intoxicated and their action {action.action_command} is skipped")
            await context.bot.send_message(
                chat_id=action.user_id,
                text="You were intoxicated last night and couldn't perform your action!"
            )
            continue
        
        # Delegate action handling to the appropriate function based on action command
        if action.action_command == "kill":
            await handle_kill_action(action.user_id, action.target_id, game_state, context)
        elif action.action_command == "heal":
            # Use the dedicated doctor action handler
            await handle_heal_action(action.user_id, action.target_id, game_state.healed_players, context)
        elif action.action_command == "investigate":
            # Use the dedicated investigator action handler
            await handle_investigation_action(action.user_id, action.target_id, game_id, context)
        elif action.action_command == "sniper_shot":
            # Use the dedicated sniper action handler
            await handle_sniper_shot(action.user_id, action.target_id, game_id, game_state.eliminated_players, context, game_state.healed_players)
        elif action.action_command == "shoot":  # Cowboy action
            # Use the dedicated cowboy action handler
            await handle_cowboy_shot(action.user_id, action.target_id, game_id, game_state.eliminated_players, context, game_state.healed_players)
        elif action.action_command == "distribute_guns":  # Gunsmith action
            await handle_distribute_guns_action(game_id, action.user_id, action.target_id, game_state, context)
        elif action.action_command == "intoxicate":  # Bartender action
            await handle_intoxicate_action(action.user_id, action.target_id, game_state, context)
        # Add more action handlers as needed
    
    # Apply standard mafia kills (not handled by special roles)
    await apply_mafia_kills(game_id, game_state, context)
    
    # Consolidate eliminations
    final_eliminated = await consolidate_eliminations(game_id, game_state, context)
    
    # Handle special case: Mashoghe death
    await handle_mashoghe_death(game_id, game_state, context)
    
    # Clear night actions from database
    cursor.execute("DELETE FROM Actions WHERE game_id = ? AND phase = 'night'", (game_id,))
    conn.commit()
    
    return final_eliminated