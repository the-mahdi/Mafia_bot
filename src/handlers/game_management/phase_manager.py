import json
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import logging
import random
from src.db import conn, cursor
from src.roles import role_actions, role_factions
from .game_state_machine import state_machine, GameState

logger = logging.getLogger("Mafia Bot PhaseManager")

async def start_night_phase(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str):
    """Start the night phase, sending action prompts to players."""
    logger.debug(f"Starting night phase for game {game_id}")
    
    # Update game phase
    state_machine.set_game_state(game_id, GameState.NIGHT)
    
    # Clear previous night actions
    cursor.execute("DELETE FROM Actions WHERE game_id = ? AND phase = 'night'", (game_id,))
    conn.commit()
    
    # Check if Mashoghe died recently, enabling double kill for God F
    double_kill_enabled = False
    cursor.execute("SELECT metadata FROM Games WHERE game_id = ?", (game_id,))
    game_metadata_row = cursor.fetchone()
    
    if game_metadata_row and game_metadata_row[0]:
        try:
            game_metadata = json.loads(game_metadata_row[0])
            double_kill_enabled = game_metadata.get('mafia_double_kill_enabled', False)
            
            # If this flag is used, reset it for future nights
            if double_kill_enabled:
                logger.info(f"Double kill for Godfather is enabled this night in game {game_id}")
                game_metadata['mafia_double_kill_enabled'] = False
                cursor.execute(
                    "UPDATE Games SET metadata = ? WHERE game_id = ?",
                    (json.dumps(game_metadata), game_id)
                )
                conn.commit()
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse game metadata for game {game_id}")
    
    # Fetch active players
    cursor.execute("SELECT user_id, role FROM Roles WHERE game_id = ? AND eliminated = 0", (game_id,))
    players = cursor.fetchall()
    
    for user_id, role in players:
        actions = role_actions.get(role, {}).get('night', [])
        interactive_actions = [action for action in actions if action.get('interactive') == 'button']
        
        # Special handling for God F during double kill night
        if role == "God F" and double_kill_enabled:
            await context.bot.send_message(
                chat_id=user_id,
                text="The Lover (Mashoghe) has been eliminated! Your fury allows you to kill TWO players tonight."
            )
            
            # Fetch target options - alive non-Mafia players
            cursor.execute("""
                SELECT r.user_id, u.username 
                FROM Roles r 
                JOIN Users u ON r.user_id = u.user_id 
                WHERE r.game_id = ? AND r.eliminated = 0 AND r.user_id != ?
            """, (game_id, user_id))
            
            potential_targets = cursor.fetchall()
            
            # Create a button grid for the first kill target
            keyboard = []
            for target_id, target_name in potential_targets:
                keyboard.append([InlineKeyboardButton(
                    f"{target_name}", 
                    callback_data=f"double_kill_first_{target_id}_{game_id}"
                )])
            
            keyboard.append([InlineKeyboardButton("Pass", callback_data=f"pass_{game_id}")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_message(
                chat_id=user_id,
                text="Select your FIRST kill target:",
                reply_markup=reply_markup
            )
            
            # Store in user_data that this is a double kill night
            if 'double_kill_night' not in context.user_data:
                context.user_data['double_kill_night'] = {}
            context.user_data['double_kill_night'][user_id] = game_id
            
            # Skip standard action prompting for God F
            continue
        
        if interactive_actions:
            keyboard = [
                [InlineKeyboardButton(action['description'], callback_data=f"{action['command']}_prompt_{game_id}")]
                for action in interactive_actions
            ]
            keyboard.append([InlineKeyboardButton("Pass", callback_data=f"pass_{game_id}")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(
                chat_id=user_id,
                text=f"Night begins! Choose your action for {role}:",
                reply_markup=reply_markup
            )
        else:
            await context.bot.send_message(
                chat_id=user_id,
                text="Night begins! You have no actions this phase."
            )
    
    # Notify moderator
    cursor.execute("SELECT moderator_id FROM Games WHERE game_id = ?", (game_id,))
    moderator_id = cursor.fetchone()[0]
    
    # Add timer for night phase (optional)
    night_duration_seconds = 60  # 1 minute for testing, adjust as needed
    job = context.job_queue.run_once(
        night_phase_timeout, 
        night_duration_seconds,
        data={'game_id': game_id, 'update': update, 'context': context}
    )
    
    # Store job in context.chat_data for potential cancellation
    if 'active_timers' not in context.chat_data:
        context.chat_data['active_timers'] = {}
    context.chat_data['active_timers'][f"{game_id}_night"] = job
    
    await context.bot.send_message(
        chat_id=moderator_id,
        text=f"Night phase started. Players have {night_duration_seconds} seconds to choose their actions."
    )

async def night_phase_timeout(context: ContextTypes.DEFAULT_TYPE):
    """Called when the night phase timer expires."""
    job_data = context.job.data
    game_id = job_data['game_id']
    update = job_data['update']
    
    logger.debug(f"Night phase timeout for game {game_id}")
    
    # Remove the timer reference
    if 'active_timers' in context.chat_data and f"{game_id}_night" in context.chat_data['active_timers']:
        del context.chat_data['active_timers'][f"{game_id}_night"]
    
    # Notify players that night is ending
    cursor.execute("SELECT user_id FROM Roles WHERE game_id = ? AND eliminated = 0", (game_id,))
    players = [row[0] for row in cursor.fetchall()]
    
    for user_id in players:
        await context.bot.send_message(
            chat_id=user_id,
            text="Time's up! Night phase is ending..."
        )
    
    # Transition to night resolve phase
    await state_machine.transition_to(update, context, game_id, GameState.NIGHT_RESOLVE)

async def resolve_night_actions(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str):
    """Resolve all night actions and transition to day phase."""
    logger.debug(f"Resolving night actions for game {game_id}")
    
    # Update state to NIGHT_RESOLVE
    state_machine.set_game_state(game_id, GameState.NIGHT_RESOLVE)
    
    # Fetch all night actions
    cursor.execute("SELECT user_id, action, target_id FROM Actions WHERE game_id = ? AND phase = 'night'", (game_id,))
    actions_data = cursor.fetchall()
    
    # No actions to process
    if not actions_data:
        logger.debug("No night actions recorded for this game")
        # Store empty eliminated list for DAY_ANNOUNCE phase
        if 'game_data' not in context.chat_data:
            context.chat_data['game_data'] = {}
        if game_id not in context.chat_data['game_data']:
            context.chat_data['game_data'][game_id] = {}
        context.chat_data['game_data'][game_id]['night_eliminated'] = []
        
        # Move to DAY_ANNOUNCE phase
        await state_machine.transition_to(update, context, game_id, GameState.DAY_ANNOUNCE)
        return
    
    # Prepare actions with priority
    prioritized_actions = []
    
    for user_id, action_command, target_id in actions_data:
        # Get user's role
        cursor.execute("SELECT role FROM Roles WHERE game_id = ? AND user_id = ?", (game_id, user_id))
        role_result = cursor.fetchone()
        if not role_result:
            logger.warning(f"Role not found for user {user_id} in game {game_id}")
            continue
        
        role = role_result[0]
        
        # Find the action definition in role_actions
        night_actions = role_actions.get(role, {}).get('night', [])
        action_def = next((a for a in night_actions if a.get('command') == action_command), None)
        
        if not action_def:
            logger.warning(f"Action definition not found for {action_command} of role {role}")
            continue
        
        # Get priority, default to 0 if not specified
        priority = action_def.get('priority', 0)
        
        # Add to list with priority
        prioritized_actions.append((user_id, role, action_command, target_id, action_def, priority))
    
    # Sort actions by priority (higher values first)
    prioritized_actions.sort(key=lambda x: x[5], reverse=True)
    
    logger.debug(f"Sorted {len(prioritized_actions)} night actions by priority")
    
    # Process effects
    kill_targets = set()
    healed_players = set()
    eliminated_players = []
    intoxicated_players = set()  # For Bartender role
    gun_distributions = {}  # For Gunsmith (Tof Dar) role
    ruyin_tan_immunity = {}  # Track Ruyin Tan (Bulletproof) players who have used their immunity
    mashoghe_died = False   # Track if Mashoghe died this night
    
    # First pass: Check for special conditions or pre-process actions
    # For example, check if Ruyin Tan players have used their immunity before
    cursor.execute("""
    SELECT user_id, metadata FROM Roles 
    WHERE game_id = ? AND role = 'Ruyin tan' AND eliminated = 0
    """, (game_id,))
    
    ruyin_tan_players = cursor.fetchall()
    for user_id, metadata in ruyin_tan_players:
        if metadata:
            try:
                metadata_dict = json.loads(metadata)
                # If immunity_used key is present, use that value, otherwise default to False
                ruyin_tan_immunity[user_id] = metadata_dict.get('immunity_used', False)
            except json.JSONDecodeError:
                # If metadata exists but is not valid JSON, set immunity to False (not used yet)
                ruyin_tan_immunity[user_id] = False
                # Fix invalid metadata
                cursor.execute(
                    "UPDATE Roles SET metadata = ? WHERE game_id = ? AND user_id = ?", 
                    (json.dumps({"immunity_used": False}), game_id, user_id)
                )
                logger.warning(f"Invalid metadata for Ruyin Tan player {user_id}. Reset to default.")
        else:
            # If no metadata exists, initialize it with immunity_used=False
            ruyin_tan_immunity[user_id] = False
            cursor.execute(
                "UPDATE Roles SET metadata = ? WHERE game_id = ? AND user_id = ?", 
                (json.dumps({"immunity_used": False}), game_id, user_id)
            )
            logger.debug(f"Initialized Ruyin Tan metadata for player {user_id}")
    
    # Process actions in priority order
    for user_id, role, action_command, target_id, action_def, priority in prioritized_actions:
        logger.debug(f"Processing action {action_command} from {role} with priority {priority}")
        
        # Skip actions from intoxicated players (Bartender effect)
        if user_id in intoxicated_players:
            logger.debug(f"Player {user_id} is intoxicated and their action {action_command} is skipped")
            await context.bot.send_message(
                chat_id=user_id,
                text="You were intoxicated last night and couldn't perform your action!"
            )
            continue
        
        if action_command == "kill":
            if target_id:
                kill_targets.add(target_id)
        elif action_command == "heal":
            if target_id:
                healed_players.add(target_id)
        elif action_command == "investigate":
            cursor.execute("SELECT role FROM Roles WHERE game_id = ? AND user_id = ?", (game_id, target_id))
            target_role = cursor.fetchone()[0]
            faction = role_actions[target_role]['faction']
            result = "Mafia" if faction == "Mafia" and target_role != "God F" else "Not Mafia"
            await context.bot.send_message(
                chat_id=user_id,
                text=f"Investigation result: User {target_id} is {result}."
            )
        elif action_command == "sniper_shot":
            if target_id:
                # Check if target is Villager or not
                cursor.execute("SELECT role FROM Roles WHERE game_id = ? AND user_id = ?", (game_id, target_id))
                target_role_result = cursor.fetchone()
                if not target_role_result:
                    continue
                
                target_role = target_role_result[0]
                target_faction = role_actions[target_role]['faction']
                
                if target_faction != "Villager":
                    # Target is not a villager, kill them if not healed
                    if target_id not in healed_players:
                        # Check if target is Ruyin tan (Bulletproof) with unused immunity
                        is_immune = False
                        if target_role == "Ruyin tan" and not ruyin_tan_immunity.get(target_id, True):
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
                            eliminated_players.append((target_id, username, "sniper"))
                            await context.bot.send_message(chat_id=target_id, text="You have been eliminated by the Sniper!")
                else:
                    # Target is a villager, kill both target and sniper
                    if target_id not in healed_players:
                        # Check if target is Ruyin tan with unused immunity
                        is_immune = False
                        if target_role == "Ruyin tan" and not ruyin_tan_immunity.get(target_id, True):
                            # Mark immunity as used
                            cursor.execute(
                                "UPDATE Roles SET metadata = ? WHERE game_id = ? AND user_id = ?", 
                                (json.dumps({"immunity_used": True}), game_id, target_id)
                            )
                            is_immune = True
                        
                        if not is_immune:
                            cursor.execute("SELECT username FROM Users WHERE user_id = ?", (target_id,))
                            username = cursor.fetchone()[0]
                            eliminated_players.append((target_id, username, "sniper"))
                            await context.bot.send_message(chat_id=target_id, text="You have been eliminated by the Sniper!")
                    
                    # Kill sniper too - they shot a villager
                    cursor.execute("SELECT username FROM Users WHERE user_id = ?", (user_id,))
                    username = cursor.fetchone()[0]
                    eliminated_players.append((user_id, username, "sniper_backfire"))
                    await context.bot.send_message(
                        chat_id=user_id, 
                        text="You have been eliminated because you shot a Villager!"
                    )
        elif action_command == "shoot":  # Cowboy action
            if target_id:
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
                            eliminated_players.append((user_id, username, "cowboy_self"))
                            await context.bot.send_message(
                                chat_id=user_id, 
                                text="You have left the game after using your Cowboy shot!"
                            )
                            continue  # Skip to next action
                
                # If not immune, proceed with normal elimination
                if not is_immune:
                    # Mark target for elimination
                    cursor.execute("SELECT username FROM Users WHERE user_id = ?", (target_id,))
                    username = cursor.fetchone()[0]
                    eliminated_players.append((target_id, username, "cowboy"))
                    await context.bot.send_message(chat_id=target_id, text="You have been eliminated by the Cowboy!")
                    
                    # Cowboy also gets eliminated after using their ability
                    cursor.execute("SELECT username FROM Users WHERE user_id = ?", (user_id,))
                    username = cursor.fetchone()[0]
                    eliminated_players.append((user_id, username, "cowboy_self"))
                    await context.bot.send_message(
                        chat_id=user_id, 
                        text="You have left the game after using your Cowboy shot!"
                    )
        elif action_command == "distribute_guns":  # Gunsmith (Tof Dar) action
            if target_id:
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
        elif action_command == "intoxicate":  # Bartender action
            if target_id:
                intoxicated_players.add(target_id)
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"You have successfully intoxicated your target."
                )
        
        # Process other actions here as needed
        # Add additional elif blocks for other role actions
    
    # Apply standard mafia kills (not handled by special roles)
    for target_id in kill_targets:
        if target_id not in healed_players:
            # Check if target is already eliminated (e.g., by sniper)
            cursor.execute("SELECT eliminated, role FROM Roles WHERE game_id = ? AND user_id = ?", (game_id, target_id))
            result = cursor.fetchone()
            if result and result[0] == 0:  # not yet eliminated
                role = result[1]
                
                # Check if target is Mashoghe - track if they're killed
                if role == "Mashoghe":
                    mashoghe_died = True
                    logger.debug(f"Mashoghe (user_id: {target_id}) was killed during this night.")
                
                # Check if target is Ruyin tan (Bulletproof) with unused immunity
                is_immune = False
                if role == "Ruyin tan" and not ruyin_tan_immunity.get(target_id, True):
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
                    eliminated_players.append((target_id, username, "mafia_kill"))
                    await context.bot.send_message(chat_id=target_id, text="You have been eliminated during the night!")
    
    # Now consolidate all night outcomes and apply them at once
    logger.debug(f"Consolidating night outcomes: {len(eliminated_players)} players eliminated")
    
    # Create a dictionary to deduplicate and track eliminations
    # This ensures each player is only eliminated once, with priority given to earliest elimination cause
    elimination_dict = {}
    for user_id, username, cause in eliminated_players:
        if user_id not in elimination_dict:
            elimination_dict[user_id] = (username, cause)
    
    # Apply all eliminations at once
    final_eliminated = []
    for user_id, (username, cause) in elimination_dict.items():
        # Check again if the player was Mashoghe
        cursor.execute("SELECT role FROM Roles WHERE game_id = ? AND user_id = ?", (game_id, user_id))
        role_result = cursor.fetchone()
        if role_result and role_result[0] == "Mashoghe":
            mashoghe_died = True
            logger.debug(f"Confirmed Mashoghe (user_id: {user_id}) was eliminated with cause: {cause}")
        
        # Update player elimination status using the new function
        await update_player_elimination_status(game_id, user_id, True, cause)
        # Save for announcement (without the cause)
        final_eliminated.append((user_id, username))
    
    # If Mashoghe died this night, set a game-level flag for mafia double kill next night
    if mashoghe_died:
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
    
    # Clear night actions
    cursor.execute("DELETE FROM Actions WHERE game_id = ? AND phase = 'night'", (game_id,))
    conn.commit()
    
    # Store the eliminated players in context for announcement in DAY_ANNOUNCE phase
    if 'game_data' not in context.chat_data:
        context.chat_data['game_data'] = {}
    if game_id not in context.chat_data['game_data']:
        context.chat_data['game_data'][game_id] = {}
    
    context.chat_data['game_data'][game_id]['night_eliminated'] = final_eliminated
    
    # Move to DAY_ANNOUNCE phase
    await state_machine.transition_to(update, context, game_id, GameState.DAY_ANNOUNCE)

async def announce_day_results(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str):
    """Announce the results of the night phase to all players."""
    logger.debug(f"Announcing day results for game {game_id}")
    
    # Get the list of eliminated players
    eliminated_players = []
    if ('game_data' in context.chat_data and 
        game_id in context.chat_data['game_data'] and 
        'night_eliminated' in context.chat_data['game_data'][game_id]):
        eliminated_players = context.chat_data['game_data'][game_id]['night_eliminated']
    
    # Get all alive players
    cursor.execute("SELECT user_id FROM Roles WHERE game_id = ? AND eliminated = 0", (game_id,))
    alive_players = [row[0] for row in cursor.fetchall()]
    
    # Build announcement message
    if eliminated_players:
        announcement = "🌅 Day breaks! Last night was eventful!\n\n"
        announcement += "The following players were eliminated during the night:\n"
        for _, username in eliminated_players:
            announcement += f"- {username}\n"
    else:
        announcement = "🌅 Day breaks! The night was quiet. No one was eliminated."
    
    # Send announcement to all alive players
    for user_id in alive_players:
        await context.bot.send_message(chat_id=user_id, text=announcement)
    
    # Also inform eliminated players from last night
    for user_id, _ in eliminated_players:
        await context.bot.send_message(
            chat_id=user_id, 
            text=announcement + "\n\nYou can still watch the game, but you cannot participate."
        )
    
    # Get the game chat ID (if available)
    cursor.execute("SELECT chat_id FROM Games WHERE game_id = ?", (game_id,))
    game_chat_result = cursor.fetchone()
    
    # If there's a game chat, announce the results there too
    if game_chat_result and game_chat_result[0]:
        game_chat_id = game_chat_result[0]
        try:
            await context.bot.send_message(chat_id=game_chat_id, text=announcement)
            logger.debug(f"Sent night results announcement to game chat {game_chat_id}")
        except Exception as e:
            logger.error(f"Failed to send night results to game chat: {e}")
    
    # Move to DAY_DISCUSS phase
    await state_machine.transition_to(update, context, game_id, GameState.DAY_DISCUSS)

async def start_day_phase(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str):
    """Start the day phase, sending action prompts and preparing for discussions."""
    logger.debug(f"Starting day discussion phase for game {game_id}")
    
    # Set state to DAY_DISCUSS
    state_machine.set_game_state(game_id, GameState.DAY_DISCUSS)
    
    # Clear previous day actions
    cursor.execute("DELETE FROM Actions WHERE game_id = ? AND phase = 'day'", (game_id,))
    conn.commit()
    
    # Fetch active players
    cursor.execute("SELECT user_id, role FROM Roles WHERE game_id = ? AND eliminated = 0", (game_id,))
    players = cursor.fetchall()
    
    for user_id, role in players:
        actions = role_actions.get(role, {}).get('day', [])
        interactive_actions = [action for action in actions if action.get('interactive') == 'button']
        
        if interactive_actions:
            keyboard = [
                [InlineKeyboardButton(action['description'], callback_data=f"{action['command']}_prompt_{game_id}")]
                for action in interactive_actions
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(
                chat_id=user_id,
                text=f"Day continues! Choose your action for {role}:",
                reply_markup=reply_markup
            )
        else:
            await context.bot.send_message(
                chat_id=user_id, 
                text="Day continues! Discuss with others and prepare for voting."
            )
    
    # Notify moderator
    cursor.execute("SELECT moderator_id FROM Games WHERE game_id = ?", (game_id,))
    moderator_id = cursor.fetchone()[0]
    
    # Add timer for day phase
    day_duration_seconds = 120  # 2 minutes for testing, adjust as needed
    job = context.job_queue.run_once(
        day_phase_timeout, 
        day_duration_seconds,
        data={'game_id': game_id, 'update': update, 'context': context}
    )
    
    # Store job in context.chat_data for potential cancellation
    if 'active_timers' not in context.chat_data:
        context.chat_data['active_timers'] = {}
    context.chat_data['active_timers'][f"{game_id}_day"] = job
    
    await context.bot.send_message(
        chat_id=moderator_id,
        text=f"Day discussion phase started. Players have {day_duration_seconds} seconds to discuss."
    )

async def day_phase_timeout(context: ContextTypes.DEFAULT_TYPE):
    """Called when the day phase timer expires."""
    job_data = context.job.data
    game_id = job_data['game_id']
    update = job_data['update']
    
    logger.debug(f"Day phase timeout for game {game_id}")
    
    # Remove the timer reference
    if 'active_timers' in context.chat_data and f"{game_id}_day" in context.chat_data['active_timers']:
        del context.chat_data['active_timers'][f"{game_id}_day"]
    
    # Notify players that day is ending and voting will begin
    cursor.execute("SELECT user_id FROM Roles WHERE game_id = ? AND eliminated = 0", (game_id,))
    players = [row[0] for row in cursor.fetchall()]
    
    for user_id in players:
        await context.bot.send_message(
            chat_id=user_id,
            text="Time's up! Discussion phase is ending and voting will begin shortly..."
        )
    
    # Transition to VOTING phase
    await state_machine.transition_to(update, context, game_id, GameState.VOTING)

async def start_voting_phase(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str):
    """Start the voting phase, initializing permissions and vote interface."""
    logger.debug(f"Starting voting phase for game {game_id}")
    
    # Set state to VOTING
    state_machine.set_game_state(game_id, GameState.VOTING)
    
    # Get moderator ID
    cursor.execute("SELECT moderator_id FROM Games WHERE game_id = ?", (game_id,))
    moderator_id = cursor.fetchone()[0]
    
    # Notify moderator
    await context.bot.send_message(
        chat_id=moderator_id,
        text="Voting phase is starting. Setting up permissions..."
    )
    
    # Import needed here to avoid circular imports
    from .voting import prompt_voting_permissions
    
    # Default to non-anonymous voting - moderator can change this in settings if needed
    await prompt_voting_permissions(update, context, game_id, anonymous=False)
    
    # Add timer for voting phase
    voting_duration_seconds = 180  # 3 minutes for testing, adjust as needed
    job = context.job_queue.run_once(
        voting_phase_timeout, 
        voting_duration_seconds,
        data={'game_id': game_id, 'update': update, 'context': context}
    )
    
    # Store job in context.chat_data for potential cancellation
    if 'active_timers' not in context.chat_data:
        context.chat_data['active_timers'] = {}
    context.chat_data['active_timers'][f"{game_id}_voting"] = job
    
    await context.bot.send_message(
        chat_id=moderator_id,
        text=f"Voting phase started. Players have {voting_duration_seconds} seconds to cast their votes."
    )

async def voting_phase_timeout(context: ContextTypes.DEFAULT_TYPE):
    """Called when the voting phase timer expires."""
    job_data = context.job.data
    game_id = job_data['game_id']
    update = job_data['update']
    
    logger.debug(f"Voting phase timeout for game {game_id}")
    
    # Remove the timer reference
    if 'active_timers' in context.chat_data and f"{game_id}_voting" in context.chat_data['active_timers']:
        del context.chat_data['active_timers'][f"{game_id}_voting"]
    
    # Notify players that voting is ending
    cursor.execute("SELECT user_id FROM Roles WHERE game_id = ? AND eliminated = 0", (game_id,))
    players = [row[0] for row in cursor.fetchall()]
    
    for user_id in players:
        await context.bot.send_message(
            chat_id=user_id,
            text="Time's up! Voting phase is ending and results will be calculated soon..."
        )
    
    # Transition to VOTE_RESOLVE phase
    await state_machine.transition_to(update, context, game_id, GameState.VOTE_RESOLVE)

async def resolve_voting_phase(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str):
    """Process voting results and determine which player(s) to eliminate."""
    logger.debug(f"Resolving voting phase for game {game_id}")
    
    # Set state to VOTE_RESOLVE
    state_machine.set_game_state(game_id, GameState.VOTE_RESOLVE)
    
    # Get moderator ID
    cursor.execute("SELECT moderator_id FROM Games WHERE game_id = ?", (game_id,))
    moderator_id = cursor.fetchone()[0]
    
    # Import needed here to avoid circular imports
    from .voting import process_voting_results, game_voting_data
    
    # Check if there's already an active voting session
    if game_id in game_voting_data:
        # Process the existing votes
        await process_voting_results(update, context, game_id)
    else:
        # No active voting - notify moderator
        await context.bot.send_message(
            chat_id=moderator_id,
            text="No active voting session found. Skipping vote resolution."
        )
    
    # Move to apply voting outcome
    await apply_voting_outcome(update, context, game_id)
    
    # After applying voting outcome, check win conditions
    await state_machine.transition_to(update, context, game_id, GameState.CHECK_WIN)

async def apply_voting_outcome(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str):
    """Apply the voting outcome by eliminating the player(s) with the most votes."""
    logger.debug(f"Applying voting outcome for game {game_id}")
    
    # If we've stored vote results in context, retrieve them
    vote_results = None
    if ('game_data' in context.chat_data and 
        game_id in context.chat_data['game_data'] and 
        'vote_results' in context.chat_data['game_data'][game_id]):
        vote_results = context.chat_data['game_data'][game_id]['vote_results']
    
    # If no results were stored, try to calculate them from the Actions table
    if not vote_results:
        # Count votes from the Actions table
        cursor.execute("""
        SELECT target_id, COUNT(*) as vote_count 
        FROM Actions 
        WHERE game_id = ? AND phase = 'day' AND action = 'vote'
        GROUP BY target_id
        ORDER BY vote_count DESC
        """, (game_id,))
        
        vote_count_rows = cursor.fetchall()
        
        if not vote_count_rows:
            # No votes recorded
            cursor.execute("SELECT moderator_id FROM Games WHERE game_id = ?", (game_id,))
            moderator_id = cursor.fetchone()[0]
            
            await context.bot.send_message(
                chat_id=moderator_id,
                text="No votes were recorded. No players will be eliminated this round."
            )
            return
        
        # Find the maximum vote count
        max_votes = vote_count_rows[0][1]
        
        # Players with the most votes
        eliminated_player_ids = [player_id for player_id, count in vote_count_rows if count == max_votes]
    else:
        # Use the stored results (expected format: [(player_id, vote_count), ...])
        if not vote_results:
            return
            
        # Find the maximum vote count
        max_votes = vote_results[0][1]
        
        # Players with the most votes
        eliminated_player_ids = [player_id for player_id, count in vote_results if count == max_votes]
    
    # Handle potential tie - for simplicity, eliminate all players with the most votes
    # In a more sophisticated system, you might add tie-breaking rules or revote logic here
    
    # Mark the identified players as eliminated
    eliminated_usernames = []
    for player_id in eliminated_player_ids:
        # Use the centralized function to update player elimination status
        username = await update_player_elimination_status(game_id, player_id, True, "vote")
        eliminated_usernames.append(username)
        
        # Notify the eliminated player
        await context.bot.send_message(
            chat_id=player_id,
            text="You have been eliminated by vote! You can still watch the game, but you cannot participate."
        )
    
    conn.commit()
    
    # Announce the results to all players
    if eliminated_usernames:
        if len(eliminated_usernames) == 1:
            announcement = f"📢 The votes have been counted! Player {eliminated_usernames[0]} has been eliminated."
        else:
            announcement = f"📢 The votes have been counted! Due to a tie, the following players have been eliminated: {', '.join(eliminated_usernames)}"
    else:
        announcement = "📢 The votes have been counted! No one has been eliminated this round."
    
    # Send announcement to all players
    cursor.execute("SELECT user_id FROM Roles WHERE game_id = ?", (game_id,))
    all_players = [row[0] for row in cursor.fetchall()]
    
    for user_id in all_players:
        await context.bot.send_message(chat_id=user_id, text=announcement)
    
    # Clear stored vote results if they exist
    if ('game_data' in context.chat_data and 
        game_id in context.chat_data['game_data'] and 
        'vote_results' in context.chat_data['game_data'][game_id]):
        del context.chat_data['game_data'][game_id]['vote_results']

async def resolve_day_actions(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str):
    """Resolve day actions (excluding voting, handled separately)."""
    logger.debug(f"Resolving day actions for game {game_id}")
    
    cursor.execute("SELECT user_id, action, target_id FROM Actions WHERE game_id = ? AND phase = 'day'", (game_id,))
    actions = cursor.fetchall()
    
    for user_id, action, target_id in actions:
        if action == "vote":
            # Voting is handled separately in voting.py
            continue
        # Add logic for other day actions as needed
    
    conn.commit()
    cursor.execute("DELETE FROM Actions WHERE game_id = ? AND phase = 'day' AND action != 'vote'", (game_id,))
    conn.commit()

# Check win conditions after night/day eliminations
async def check_win_condition(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str):
    """Check if any faction has won the game."""
    logger.debug(f"Checking win conditions for game {game_id}")
    
    # Count alive players by faction - improved query to fetch comprehensive game state
    cursor.execute("""
    SELECT 
        r.role,
        ro.faction,
        u.username,
        r.user_id,
        r.eliminated,
        r.metadata
    FROM Roles r
    JOIN Users u ON r.user_id = u.user_id
    JOIN (
        SELECT role, json_extract(value, '$.faction') as faction
        FROM (
            SELECT role, json_each(json_extract(value, '$.actions')) as value
            FROM json_each((SELECT json_extract(readfile('data/roles.json'), '$.roles')))
        )
        GROUP BY role
    ) ro ON r.role = ro.role
    WHERE r.game_id = ?
    ORDER BY r.eliminated, ro.faction, r.role
    """, (game_id,))
    
    all_players = cursor.fetchall()
    
    # Build comprehensive game state
    game_state = {
        'total_players': len(all_players),
        'alive_players': 0,
        'eliminated_players': 0,
        'factions': {},
        'players_by_faction': {},
        'players': []
    }
    
    # Process players
    for role, faction, username, user_id, eliminated, metadata in all_players:
        player_info = {
            'user_id': user_id,
            'username': username,
            'role': role,
            'faction': faction,
            'eliminated': bool(eliminated),
            'metadata': json.loads(metadata) if metadata else {}
        }
        
        game_state['players'].append(player_info)
        
        # Count alive/eliminated
        if eliminated:
            game_state['eliminated_players'] += 1
        else:
            game_state['alive_players'] += 1
            
            # Initialize faction counters if needed
            if faction not in game_state['factions']:
                game_state['factions'][faction] = 0
                game_state['players_by_faction'][faction] = []
            
            # Increment faction counter and add to faction list
            game_state['factions'][faction] += 1
            game_state['players_by_faction'][faction].append(player_info)
    
    # Log the detailed game state
    logger.debug(f"Game state for {game_id}: {game_state['alive_players']} alive players, " +
                f"factions: {game_state['factions']}")
    
    # Store game state in context for access by other functions
    if 'game_data' not in context.chat_data:
        context.chat_data['game_data'] = {}
    if game_id not in context.chat_data['game_data']:
        context.chat_data['game_data'][game_id] = {}
    
    context.chat_data['game_data'][game_id]['game_state'] = game_state
    
    # Check win conditions using the fetched game state
    mafia_count = game_state['factions'].get('Mafia', 0)
    villager_count = game_state['factions'].get('Villager', 0)
    independent_count = game_state['factions'].get('Independent', 0)
    
    winner = None
    win_reason = ""
    
    # Check win conditions
    # 1. Villagers win if no Mafia members remain
    if mafia_count == 0 and villager_count > 0:
        winner = "Villagers"
        win_reason = "All Mafia members have been eliminated!"
    
    # 2. Mafia wins if they equal or outnumber the Villagers
    elif mafia_count >= villager_count and mafia_count > 0:
        winner = "Mafia"
        win_reason = "The Mafia now equals or outnumbers the Villagers!"
    
    # 3. Check for Independent wins - specific for each independent role
    # Get all alive independent players
    independent_players = game_state['players_by_faction'].get('Independent', [])
    for player in independent_players:
        role = player['role']
        user_id = player['user_id']
        
        # Example: Serial Killer win condition (last player standing or only other Mafia remain)
        if role == "Serial Killer" and game_state['alive_players'] <= 2 and mafia_count == 0:
            winner = "Serial Killer"
            win_reason = f"The Serial Killer ({player['username']}) has eliminated all threats!"
        
        # Example: Jester win condition (if they were eliminated by vote)
        if role == "Jester":
            metadata = player['metadata']
            if player['eliminated'] and metadata.get('elimination_cause') == 'vote':
                winner = "Jester"
                win_reason = f"The Jester ({player['username']}) tricked everyone into voting them out!"
        
        # Add more independent role win conditions as needed
    
    if winner:
        # Game is over - update game status in the database
        game_end_time = int(datetime.datetime.now().timestamp())
        cursor.execute("""
            UPDATE Games 
            SET current_phase = ?, 
                winner = ?, 
                win_reason = ?,
                ended = 1,
                end_time = ?
            WHERE game_id = ?
        """, (GameState.GAME_OVER.name, winner, win_reason, game_end_time, game_id))
        conn.commit()
        
        logger.info(f"Game {game_id} ended with winner: {winner} - Reason: {win_reason}")
        
        # Cancel any active timers for this game
        if 'active_timers' in context.chat_data:
            for timer_key in list(context.chat_data['active_timers'].keys()):
                if timer_key.startswith(f"{game_id}_"):
                    job = context.chat_data['active_timers'].pop(timer_key)
                    job.schedule_removal()
                    logger.debug(f"Removed timer {timer_key} for ended game")
        
        # Announce winner
        cursor.execute("SELECT user_id FROM Roles WHERE game_id = ?", (game_id,))
        all_players_ids = [row[0] for row in cursor.fetchall()]
        
        # Get moderator ID and game chat ID for final announcement
        cursor.execute("SELECT moderator_id, chat_id FROM Games WHERE game_id = ?", (game_id,))
        moderator_data = cursor.fetchone()
        moderator_id = moderator_data[0]
        game_chat_id = moderator_data[1]
        
        # Construct win announcement with emoji for visual appeal
        win_announcement = f"🏆 Game Over! The {winner} have won the game! 🏆\n{win_reason}"
        
        # Send to moderator first
        await context.bot.send_message(
            chat_id=moderator_id,
            text=win_announcement
        )
        
        # Send to all players
        for user_id in all_players_ids:
            await context.bot.send_message(
                chat_id=user_id,
                text=win_announcement
            )
        
        # If there's a game chat, announce there too
        if game_chat_id:
            try:
                await context.bot.send_message(
                    chat_id=game_chat_id, 
                    text=win_announcement
                )
                logger.debug(f"Sent game end announcement to game chat {game_chat_id}")
            except Exception as e:
                logger.error(f"Failed to send game end announcement to game chat: {e}")
        
        # Reveal all roles - formatted nicely with emoji indicators
        reveal_message = "📜 Final role assignments:\n\n"
        
        # Group by faction for better readability
        factions = {}
        for player in game_state['players']:
            faction = player['faction']
            if faction not in factions:
                factions[faction] = []
            factions[faction].append(player)
        
        # Generate the reveal message by faction
        for faction, players in factions.items():
            reveal_message += f"**{faction}**:\n"
            for player in players:
                status = "🪦 Eliminated" if player['eliminated'] else "🔆 Alive"
                cause = ""
                if player['eliminated'] and player['metadata'].get('elimination_cause'):
                    cause = f" (by {player['metadata']['elimination_cause']})"
                reveal_message += f"- {player['username']}: {player['role']}{cause} - {status}\n"
            reveal_message += "\n"
        
        # Send the role reveal to all players
        for user_id in all_players_ids:
            await context.bot.send_message(
                chat_id=user_id,
                text=reveal_message
            )
        
        # Send a game summary with statistics to the moderator
        stats_message = "📊 Game Statistics:\n\n"
        stats_message += f"Total players: {game_state['total_players']}\n"
        stats_message += f"Winner: {winner}\n"
        stats_message += f"Win reason: {win_reason}\n\n"
        
        # Add faction statistics
        stats_message += "Faction distribution at game end:\n"
        for faction, count in game_state['factions'].items():
            stats_message += f"- {faction}: {count} alive\n"
        
        # Send statistics to moderator
        await context.bot.send_message(
            chat_id=moderator_id,
            text=stats_message
        )
        
        # Clean up any persistent game data
        # 1. Remove game-specific data from context
        if game_id in context.chat_data.get('game_data', {}):
            del context.chat_data['game_data'][game_id]
            logger.debug(f"Cleared game data from context for game {game_id}")
        
        # 2. Clear any temporary game data from database
        # Keep the core game record and roles for history, but clear actions
        cursor.execute("DELETE FROM Actions WHERE game_id = ?", (game_id,))
        conn.commit()
        logger.debug(f"Cleared actions for ended game {game_id}")
        
        # Return True to indicate game is over
        return True
    
    # Return False to indicate game continues
    return False

async def update_player_elimination_status(game_id: str, user_id: int, eliminated: bool = True, cause: str = None) -> str:
    """
    Update a player's elimination status in the Roles table.
    
    Args:
        game_id: The ID of the game
        user_id: The ID of the player to update
        eliminated: True to mark as eliminated, False to mark as active
        cause: Optional cause of elimination for tracking purposes
        
    Returns:
        The username of the player
    """
    logger.debug(f"Updating player {user_id} eliminated status to {eliminated} in game {game_id}")
    
    # Get the player's username
    cursor.execute("SELECT username FROM Users WHERE user_id = ?", (user_id,))
    username_result = cursor.fetchone()
    username = username_result[0] if username_result else "Unknown"
    
    # Update the eliminated status in the Roles table
    if cause:
        # If we have a cause, store it in the metadata
        cursor.execute("SELECT metadata FROM Roles WHERE game_id = ? AND user_id = ?", (game_id, user_id))
        metadata_row = cursor.fetchone()
        metadata = {}
        
        if metadata_row and metadata_row[0]:
            try:
                metadata = json.loads(metadata_row[0])
            except:
                metadata = {}
        
        metadata['elimination_cause'] = cause
        metadata['elimination_time'] = 'night' if state_machine.get_game_state(game_id) in [GameState.NIGHT, GameState.NIGHT_RESOLVE] else 'day'
        
        cursor.execute(
            "UPDATE Roles SET eliminated = ?, metadata = ? WHERE game_id = ? AND user_id = ?",
            (1 if eliminated else 0, json.dumps(metadata), game_id, user_id)
        )
    else:
        cursor.execute(
            "UPDATE Roles SET eliminated = ? WHERE game_id = ? AND user_id = ?",
            (1 if eliminated else 0, game_id, user_id)
        )
    
    conn.commit()
    return username

# Register phase handler callbacks with the state machine
def register_phase_handlers():
    """Register all phase handlers with the game state machine."""
    state_machine.register_callback(GameState.NIGHT, start_night_phase)
    state_machine.register_callback(GameState.NIGHT_RESOLVE, resolve_night_actions)
    state_machine.register_callback(GameState.DAY_ANNOUNCE, announce_day_results)
    state_machine.register_callback(GameState.DAY_DISCUSS, start_day_phase)
    state_machine.register_callback(GameState.VOTING, start_voting_phase)
    state_machine.register_callback(GameState.VOTE_RESOLVE, resolve_voting_phase)
    state_machine.register_callback(GameState.CHECK_WIN, check_win_condition)