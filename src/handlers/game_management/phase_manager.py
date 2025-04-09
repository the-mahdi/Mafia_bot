import json
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import logging
import random
from src.db import conn, cursor
from src.roles import role_actions, role_factions
from .game_state_machine import state_machine, GameState
from src.game.player_management import update_player_elimination_status

logger = logging.getLogger("Mafia Bot PhaseManager")

async def start_night_phase(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str):
    """Start the night phase, sending action prompts to players."""
    logger.debug(f"Starting night phase for game {game_id}")
    
    # Update game phase
    try:
        state_machine.set_game_state(game_id, GameState.NIGHT)
    except Exception as e:
        logger.error(f"Failed to set game state for {game_id}: {e}")
        await _notify_moderator_error(context, game_id, "Failed to transition to night phase")
        return
    
    # Clear previous night actions
    try:
        cursor.execute("DELETE FROM Actions WHERE game_id = ? AND phase = 'night'", (game_id,))
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to clear night actions for {game_id}: {e}")
        conn.rollback()
        await _notify_moderator_error(context, game_id, "Failed to clear previous night actions")
    
    # Send phase transition message to all players
    cursor.execute("SELECT user_id FROM Roles WHERE game_id = ?", (game_id,))
    all_players = [row[0] for row in cursor.fetchall()]
    
    phase_message = (
        "🌙 *NIGHT PHASE HAS BEGUN* 🌙\n\n"
        "The village falls silent as darkness descends. Now is the time when secret actions occur...\n\n"
        "• If you have a night ability, you'll see action buttons below\n"
        "• You have limited time to choose your actions\n"
        "• Choose wisely - your decisions may determine who survives until dawn"
    )
    
    for user_id in all_players:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=phase_message,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to send phase message to {user_id}: {e}")
    
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
        try:
            actions = role_actions.get(role, {}).get('night', [])
            interactive_actions = [action for action in actions if action.get('interactive') == 'button']
        except Exception as e:
            logger.error(f"Failed to get actions for {role} in {game_id}: {e}")
            await context.bot.send_message(
                chat_id=user_id,
                text="⚠️ Error preparing your night actions. Please contact the moderator."
            )
            continue
        
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
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"Night begins! Choose your action for {role}:",
                    reply_markup=reply_markup
                )
            except Exception as e:
                logger.error(f"Failed to send action menu to {user_id}: {e}")
                await _notify_moderator_error(context, game_id, f"Failed to send menu to player {user_id}")
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
    
    try:
        await context.bot.send_message(
            chat_id=moderator_id,
            text=f"Night phase started. Players have {night_duration_seconds} seconds to choose their actions."
        )
    except Exception as e:
        logger.error(f"Failed to notify moderator {moderator_id}: {e}")
        # Fallback to logging since moderator channel is unavailable
        logger.critical("CRITICAL: Moderator notification channel failed")

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
    
    night_end_message = (
        "⏰ *NIGHT PHASE IS ENDING* ⏰\n\n"
        "The night is coming to a close. All actions are being finalized...\n"
        "Results will be revealed when day breaks."
    )
    
    for user_id in players:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=night_end_message,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to send night end message to {user_id}: {e}")
    
    # Transition to night resolve phase
    await state_machine.transition_to(update, context, game_id, GameState.NIGHT_RESOLVE)

async def resolve_night_actions(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str):
    """Resolve all night actions and transition to day phase."""
    logger.debug(f"Resolving night actions for game {game_id}")
    
    # Update state to NIGHT_RESOLVE
    state_machine.set_game_state(game_id, GameState.NIGHT_RESOLVE)
    
    # Import action resolver
    from src.game.actions.action_resolver import resolve_night_actions as resolve_actions
    
    # Delegate action resolution to the action resolver module
    final_eliminated, private_results = await resolve_actions(game_id, update, context)
    
    # Send private results to players
    for user_id, message in private_results:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🔒 Private Night Results:\n{message}"
            )
        except Exception as e:
            logger.error(f"Failed to send private results to {user_id}: {e}")
    
    # Clear processed night actions
    cursor.execute("DELETE FROM Actions WHERE game_id = ? AND phase = 'night'", (game_id,))
    conn.commit()
    logger.info(f"Cleared night actions for game {game_id}")
    
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
        announcement = "🌅 *DAY HAS BROKEN* 🌅\n\n"
        announcement += "As the sun rises over the village, the residents discover the night's events...\n\n"
        announcement += "*The following players were eliminated during the night:*\n"
        for _, username in eliminated_players:
            announcement += f"• {username}\n"
        announcement += "\nThe villagers must now discuss and decide who might be responsible."
    else:
        announcement = "🌅 *DAY HAS BROKEN* 🌅\n\n"
        announcement += "As the sun rises over the village, all seems quiet. Everyone has survived the night.\n\n"
        announcement += "The villagers must now gather to discuss their suspicions. Who among you cannot be trusted?"
    
    # Send announcement to all alive players
    for user_id in alive_players:
        try:
            await context.bot.send_message(
                chat_id=user_id, 
                text=announcement,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to send day announcement to {user_id}: {e}")
    
    # Also inform eliminated players from last night
    for user_id, _ in eliminated_players:
        try:
            await context.bot.send_message(
                chat_id=user_id, 
                text=announcement + "\n\n*You have been eliminated!* You can still watch the game, but you cannot participate.",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to send day announcement to eliminated player {user_id}: {e}")
    
    # Get the game chat ID (if available)
    cursor.execute("SELECT chat_id FROM Games WHERE game_id = ?", (game_id,))
    game_chat_result = cursor.fetchone()
    
    # If there's a game chat, announce the results there too
    if game_chat_result and game_chat_result[0]:
        game_chat_id = game_chat_result[0]
        try:
            await context.bot.send_message(
                chat_id=game_chat_id, 
                text=announcement,
                parse_mode="Markdown"
            )
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
    
    # Send phase transition message to all alive players
    cursor.execute("SELECT user_id FROM Roles WHERE game_id = ? AND eliminated = 0", (game_id,))
    alive_players = [row[0] for row in cursor.fetchall()]
    
    day_phase_message = (
        "☀️ *DAY DISCUSSION PHASE* ☀️\n\n"
        "It's time to discuss what happened during the night and share your suspicions.\n\n"
        "• Engage with other players to uncover hidden motives\n"
        "• Watch for inconsistencies in players' stories\n"
        "• Think carefully about who to vote for later\n"
        "• You have limited time before voting begins"
    )
    
    for user_id in alive_players:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=day_phase_message,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to send day phase message to {user_id}: {e}")
    
    # Fetch active players
    try:
        cursor.execute("SELECT user_id, role FROM Roles WHERE game_id = ? AND eliminated = 0", (game_id,))
        players = cursor.fetchall()
    except Exception as e:
        logger.error(f"Failed to fetch active players for {game_id}: {e}")
        await _notify_moderator_error(context, game_id, "Failed to retrieve player list")
        return
    
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
                text=f"You have special day actions available as {role}:",
                reply_markup=reply_markup
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
    
    day_end_message = (
        "⏰ *DISCUSSION TIME IS OVER* ⏰\n\n"
        "The time for debate has ended. Now the village must make a decision.\n"
        "Prepare to cast your vote on who should be eliminated!"
    )
    
    for user_id in players:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=day_end_message,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to send day end message to {user_id}: {e}")
    
    # Transition to VOTING phase
    await state_machine.transition_to(update, context, game_id, GameState.VOTING)

async def start_voting_phase(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str):
    """Start the voting phase, initializing permissions and vote interface."""
    logger.debug(f"Starting voting phase for game {game_id}")
    
    # Set state to VOTING
    state_machine.set_game_state(game_id, GameState.VOTING)
    
    # Send phase transition message to all alive players
    cursor.execute("SELECT user_id FROM Roles WHERE game_id = ? AND eliminated = 0", (game_id,))
    alive_players = [row[0] for row in cursor.fetchall()]
    
    voting_phase_message = (
        "🗳️ *VOTING PHASE HAS BEGUN* 🗳️\n\n"
        "The time for discussion is over. Now you must decide who to eliminate.\n\n"
        "• Each player gets one vote\n"
        "• Choose carefully - the player with the most votes will be eliminated\n"
        "• You have limited time to cast your vote\n"
        "• You cannot change your vote once submitted"
    )
    
    for user_id in alive_players:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=voting_phase_message,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to send voting phase message to {user_id}: {e}")
    
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
    
    voting_end_message = (
        "⏰ *VOTING HAS CONCLUDED* ⏰\n\n"
        "The time for casting votes has ended. The results are being tallied...\n"
        "Soon we'll discover who the village has chosen to eliminate."
    )
    
    for user_id in players:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=voting_end_message,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to send voting end message to {user_id}: {e}")
    
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
    """Checks win conditions by delegating to the win_conditions module"""
    from src.game.roles.win_conditions import check_win_condition as check_win
    return await check_win(update, context, game_id)

# Register phase handler callbacks with the state machine
async def _notify_moderator_error(context: ContextTypes.DEFAULT_TYPE, game_id: str, message: str):
    """Notify moderator about critical errors"""
    try:
        cursor.execute("SELECT moderator_id FROM Games WHERE game_id = ?", (game_id,))
        moderator_id = cursor.fetchone()[0]
        await context.bot.send_message(
            chat_id=moderator_id,
            text=f"🚨 SYSTEM ERROR: {message}"
        )
    except Exception as e:
        logger.critical(f"Failed to send error notification to moderator: {e}")

def register_phase_handlers():
    """Register all phase handlers with the game state machine."""
    state_machine.register_callback(GameState.NIGHT, start_night_phase)
    state_machine.register_callback(GameState.NIGHT_RESOLVE, resolve_night_actions)
    state_machine.register_callback(GameState.DAY_ANNOUNCE, announce_day_results)
    state_machine.register_callback(GameState.DAY_DISCUSS, start_day_phase)
    state_machine.register_callback(GameState.VOTING, start_voting_phase)
    state_machine.register_callback(GameState.VOTE_RESOLVE, resolve_voting_phase)
    state_machine.register_callback(GameState.CHECK_WIN, check_win_condition)