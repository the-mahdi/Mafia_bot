from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import logging
from src.db import conn, cursor
from src.utils import generate_voting_summary
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger("Mafia Bot GameManagement.Voting")

# Initialize a dictionary to store voting data for each game
game_voting_data = {}

async def announce_voting(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.debug("Announcing Voting.")
    user_id = update.effective_user.id
    game_id = context.user_data.get('game_id')
    logger.debug(f"Announcing voting for game_id: {game_id}")

    if not game_id:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No game selected.")
        return

    # Check if the user is the moderator
    cursor.execute("SELECT moderator_id FROM Games WHERE game_id = ?", (game_id,))
    result = cursor.fetchone()
    if not result or result[0] != user_id:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="You are not authorized to announce voting.")
        return

    # Fetch active (non-eliminated) players in the game
    cursor.execute("""
    SELECT Roles.user_id, Users.username
    FROM Roles
    JOIN Users ON Roles.user_id = Users.user_id
    WHERE Roles.game_id = ? AND Roles.eliminated = 0
    """, (game_id,))
    players = cursor.fetchall()
    player_ids = [player[0] for player in players]
    player_names = {user_id: username for user_id, username in players}

    # Initialize voting data with 'anonymous' flag set to False
    game_voting_data[game_id] = {
        'votes': {},  # Will store individual votes for each voter
        'voters': set(player_ids),  # Initialize voters as the set of active player IDs
        'player_ids': player_ids,
        'player_names': player_names,  # Store player names
        'summary_message_id': None,  # Initialize summary message ID
        'anonymous': False  # Flag to indicate anonymous voting
    }

    # Send voting message to each player
    for player_id, player_username in players:
        keyboard = []
        for target_id, target_username in players:
            button_text = f"{target_username} ❌"  # Voting button
            callback_data = f"vote_{target_id}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

        keyboard.append([InlineKeyboardButton("Confirm Votes", callback_data=f"confirm_votes")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await context.bot.send_message(
                chat_id=player_id,
                text=f"📢 **Voting Session:**\nVote for a player to eliminate:",
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Failed to send voting message to user {player_id}: {e}")

    # Send initial voting summary to the moderator
    await send_voting_summary(context, game_id)

async def announce_anonymous_voting(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.debug("Announcing Anonymous Voting.")
    user_id = update.effective_user.id
    game_id = context.user_data.get('game_id')
    logger.debug(f"Announcing anonymous voting for game_id: {game_id}")

    if not game_id:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No game selected.")
        return

    # Check if the user is the moderator
    cursor.execute("SELECT moderator_id FROM Games WHERE game_id = ?", (game_id,))
    result = cursor.fetchone()
    if not result or result[0] != user_id:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="You are not authorized to announce anonymous voting.")
        return

    # Fetch active (non-eliminated) players in the game
    cursor.execute("""
    SELECT Roles.user_id, Users.username
    FROM Roles
    JOIN Users ON Roles.user_id = Users.user_id
    WHERE Roles.game_id = ? AND Roles.eliminated = 0
    """, (game_id,))
    players = cursor.fetchall()
    player_ids = [player[0] for player in players]
    player_names = {user_id: username for user_id, username in players}

    # Initialize voting data with 'anonymous' flag set to True
    game_voting_data[game_id] = {
        'votes': {},  # Will store individual votes for each voter
        'voters': set(player_ids),  # Initialize voters as the set of active player IDs
        'player_ids': player_ids,
        'player_names': player_names,  # Store player names
        'summary_message_id': None,  # Initialize summary message ID
        'anonymous': True  # Flag to indicate anonymous voting
    }

    # Send voting message to each player
    for player_id, player_username in players:
        keyboard = []
        for target_id, target_username in players:
            button_text = f"{target_username} ❌"  # Voting button
            callback_data = f"vote_{target_id}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

        keyboard.append([InlineKeyboardButton("Confirm Votes", callback_data=f"confirm_votes")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await context.bot.send_message(
                chat_id=player_id,
                text=f"📢 **Anonymous Voting Session:**\nVote for a player to eliminate:",
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Failed to send voting message to user {player_id}: {e}")

    # Send initial voting summary to the moderator
    await send_voting_summary(context, game_id)


async def send_voting_summary(context: ContextTypes.DEFAULT_TYPE, game_id: str) -> None:
    """Sends or updates the voting summary message to the moderator."""
    logger.debug(f"Sending voting summary for game ID {game_id}.")

    if game_id not in game_voting_data:
        logger.error(f"Game ID {game_id} not found in voting data.")
        return

    # Fetch moderator ID
    cursor.execute("SELECT moderator_id FROM Games WHERE game_id = ?", (game_id,))
    result = cursor.fetchone()
    if not result:
        logger.error(f"Game ID {game_id} not found when fetching moderator.")
        return
    moderator_id = result[0]

    voted_players = [
        game_voting_data[game_id]['player_names'][voter_id]
        for voter_id in game_voting_data[game_id]['player_ids']
        if voter_id not in game_voting_data[game_id]['voters']
    ]
    not_voted_players = [
        game_voting_data[game_id]['player_names'][voter_id]
        for voter_id in game_voting_data[game_id]['voters']
    ]

    summary_message = generate_voting_summary(voted_players, not_voted_players)

    # Check if a summary message already exists for this game
    if game_voting_data[game_id]['summary_message_id']:
        try:
            # Edit the existing message
            await context.bot.edit_message_text(
                chat_id=moderator_id,
                message_id=game_voting_data[game_id]['summary_message_id'],
                text=summary_message,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Failed to edit voting summary message: {e}")
            # Optionally, send a new message if editing fails
            message = await context.bot.send_message(
                chat_id=moderator_id,
                text=summary_message,
                parse_mode='Markdown'
            )
            game_voting_data[game_id]['summary_message_id'] = message.message_id
    else:
        # Send a new message
        message = await context.bot.send_message(
            chat_id=moderator_id,
            text=summary_message,
            parse_mode='Markdown'
        )
        game_voting_data[game_id]['summary_message_id'] = message.message_id

async def handle_vote(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str, target_id: int) -> None:
    logger.debug("Handling vote.")
    voter_id = update.effective_user.id
    query = update.callback_query

    if game_id not in game_voting_data:
        await context.bot.send_message(chat_id=voter_id, text="Voting session not found.")
        return

    if voter_id not in game_voting_data[game_id]['voters']:
        await context.bot.send_message(chat_id=voter_id, text="You have already confirmed your votes.")
        return

    # Initialize voter's votes if not present
    if voter_id not in game_voting_data[game_id]['votes']:
        game_voting_data[game_id]['votes'][voter_id] = []

    # Toggle vote
    if target_id in game_voting_data[game_id]['votes'][voter_id]:
        game_voting_data[game_id]['votes'][voter_id].remove(target_id)
    else:
        game_voting_data[game_id]['votes'][voter_id].append(target_id)

    # Rebuild the keyboard based on permissions rather than DB query
    permissions = game_voting_data[game_id]['permissions']
    player_names = game_voting_data[game_id]['player_names']
    
    # Filter only those who can be voted
    can_be_voted_players = [(uid, player_names[uid]) for uid in permissions if permissions[uid]['can_be_voted']]
    
    keyboard = []
    for target_id_loop, target_username in can_be_voted_players:
        # Check if the voter selected this target
        if target_id_loop in game_voting_data[game_id]['votes'][voter_id]:
            button_text = f"{target_username} ✓"
        else:
            button_text = f"{target_username} ✗"
        callback_data = f"vote_{target_id_loop}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

    keyboard.append([InlineKeyboardButton("Confirm Votes", callback_data="confirm_votes")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_reply_markup(reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Failed to edit message: {e}")

async def confirm_votes(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str) -> None:
    logger.debug("Confirming votes.")
    voter_id = update.effective_user.id
    query = update.callback_query

    if game_id not in game_voting_data:
        await context.bot.send_message(chat_id=voter_id, text="Voting session not found.")
        return

    if voter_id not in game_voting_data[game_id]['voters']:
        await context.bot.send_message(chat_id=voter_id, text="You have already confirmed your votes.")
        return

    # Prepare confirmation message
    voter_votes = game_voting_data[game_id]['votes'].get(voter_id, [])
    player_names = game_voting_data[game_id]['player_names']
    if voter_votes:
        voted_for_names = [player_names.get(target_id, f"User {target_id}") for target_id in voter_votes]
        confirmation_message = f"You are voting for: {', '.join(voted_for_names)}.\nAre you sure?"
    else:
        confirmation_message = "You have not cast any votes. Are you sure?"

    # Add Final Confirm and Cancel buttons
    keyboard = [
        [InlineKeyboardButton("Final Confirm", callback_data=f"final_confirm_vote_{game_id}")],
        [InlineKeyboardButton("Cancel", callback_data=f"cancel_vote_{game_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Send confirmation message
    await query.edit_message_text(text=confirmation_message, reply_markup=reply_markup)


async def final_confirm_vote(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.debug("Final vote confirmation.")
    voter_id = update.effective_user.id
    query = update.callback_query
    data_parts = query.data.split("_")
    game_id = data_parts[3]

    if game_id not in game_voting_data:
        await context.bot.send_message(chat_id=voter_id, text="Voting session not found.")
        return

    # Check if the voter is part of the game
    if voter_id not in game_voting_data[game_id]['player_ids']:
        await context.bot.send_message(chat_id=voter_id, text="You are not part of this game.")
        return
    
    if voter_id not in game_voting_data[game_id]['voters']:
        await context.bot.send_message(chat_id=voter_id, text="You have already confirmed your votes.")
        return

    # Remove voter from the set of active voters
    game_voting_data[game_id]['voters'].remove(voter_id)

    await query.edit_message_text(text="Your votes have been finally confirmed.")

    # Update the voting summary for the moderator
    await send_voting_summary(context, game_id)

    # Check if all players have voted
    if not game_voting_data[game_id]['voters']:
        await process_voting_results(update, context, game_id)

async def cancel_vote(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.debug("Cancelling vote.")
    voter_id = update.effective_user.id
    query = update.callback_query
    data_parts = query.data.split("_")
    game_id = data_parts[2]  # Extract game_id from callback_data

    if game_id not in game_voting_data:
        await context.bot.send_message(chat_id=voter_id, text="Voting session not found.")
        return

    # Reset the voter's votes
    game_voting_data[game_id]['votes'][voter_id] = []

    # Rebuild the keyboard using permissions rather than DB
    permissions = game_voting_data[game_id]['permissions']
    player_names = game_voting_data[game_id]['player_names']
    
    can_be_voted_players = [(uid, player_names[uid]) for uid in permissions if permissions[uid]['can_be_voted']]

    keyboard = []
    for target_id_loop, target_username in can_be_voted_players:
        button_text = f"{target_username} ✗"  # Reset to default "not voted"
        callback_data = f"vote_{target_id_loop}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

    keyboard.append([InlineKeyboardButton("Confirm Votes", callback_data="confirm_votes")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text="Vote cancelled. Please recast your votes.", reply_markup=reply_markup)


async def process_voting_results(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str) -> None:
    logger.debug("Processing voting results.")
    if game_id not in game_voting_data:
        logger.error(f"Game ID {game_id} not found in voting data.")
        return

    # Fetch active (non-eliminated) player names
    cursor.execute("""
    SELECT Roles.user_id, Users.username
    FROM Roles
    JOIN Users ON Roles.user_id = Users.user_id
    WHERE Roles.game_id = ? AND Roles.eliminated = 0
    """, (game_id,))
    players = cursor.fetchall()
    player_names = {user_id: username for user_id, username in players}

    # Count votes
    vote_counts = {}
    for voter_id, votes in game_voting_data[game_id]['votes'].items():
        for voted_id in votes:
            vote_counts[voted_id] = vote_counts.get(voted_id, 0) + 1

    # Sort results
    sorted_results = sorted(vote_counts.items(), key=lambda item: item[1], reverse=True)

    # Prepare the summary message
    summary_message = "🔍 **Voting Results (Summary):**\n\n"
    if sorted_results:
        for voted_id, count in sorted_results:
            summary_message += f"• **{player_names.get(voted_id, 'Unknown')}**: {count} vote(s)\n"
    else:
        summary_message += "No votes were cast."

    # Fetch moderator ID
    cursor.execute("SELECT moderator_id FROM Games WHERE game_id = ?", (game_id,))
    result = cursor.fetchone()
    if not result:
        logger.error(f"Game ID {game_id} not found when fetching moderator.")
        return
    moderator_id = result[0]

    # Send the summary message to all players
    for player_id in game_voting_data[game_id]['player_ids']:
        try:
            await context.bot.send_message(chat_id=player_id, text=summary_message, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Failed to send summary message to user {player_id}: {e}")

    # Send the summary message to the moderator
    try:
        await context.bot.send_message(chat_id=moderator_id, text=summary_message, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Failed to send voting summary to moderator {moderator_id}: {e}")

    # Generate detailed voting report
    detailed_report = "🗳️ **Detailed Voting Report:**\n\n"
    for voter_id, votes in game_voting_data[game_id]['votes'].items():
        voter_name = player_names.get(voter_id, f"User {voter_id}")
        if votes:
            voted_names = [player_names.get(target_id, f"User {target_id}") for target_id in votes]
            voted_str = ", ".join(voted_names)
            detailed_report += f"• **{voter_name}** voted for: {voted_str}\n"
        else:
            detailed_report += f"• **{voter_name}** did not vote.\n"

    # Check if the voting was anonymous
    anonymous = game_voting_data[game_id].get('anonymous', False)

    if anonymous:
        # Send detailed report only to the moderator
        try:
            await context.bot.send_message(chat_id=moderator_id, text=detailed_report, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Failed to send detailed voting report to moderator {moderator_id}: {e}")
    else:
        # Send the detailed report to all players
        for player_id in game_voting_data[game_id]['player_ids']:
            try:
                await context.bot.send_message(chat_id=player_id, text=detailed_report, parse_mode='Markdown')
            except Exception as e:
                logger.error(f"Failed to send detailed voting report to user {player_id}: {e}")
                # Notify the moderator about the failure
                try:
                    await context.bot.send_message(
                        chat_id=moderator_id,
                        text=f"⚠️ Failed to send detailed voting report to user {player_id}."
                    )
                except Exception as ex:
                    logger.error(f"Failed to notify moderator about failed message to user {player_id}: {ex}")

        # Send the detailed report to the moderator
        try:
            await context.bot.send_message(chat_id=moderator_id, text=detailed_report, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Failed to send detailed voting report to moderator {moderator_id}: {e}")

    # Clean up voting data for the game
    del game_voting_data[game_id]
    logger.debug(f"Voting data for game ID {game_id} has been cleared.")



async def prompt_voting_permissions(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str, anonymous: bool) -> None:
    """
    Prompt the moderator with a list of players and their default voting permissions.
    Moderator can toggle "Can Vote" and "Can be Voted" for each player.
    """
    # Fetch the moderator ID
    cursor.execute("SELECT moderator_id FROM Games WHERE game_id = ?", (game_id,))
    result = cursor.fetchone()
    if not result:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Game not found.")
        return
    moderator_id = result[0]

    # Fetch active players
    cursor.execute("""
    SELECT Roles.user_id, Users.username
    FROM Roles
    JOIN Users ON Roles.user_id = Users.user_id
    WHERE Roles.game_id = ? AND Roles.eliminated = 0
    """, (game_id,))
    players = cursor.fetchall()

    # Initialize permissions in memory
    # By default everyone can vote and be voted
    game_voting_data[game_id] = {
        'votes': {},
        'player_ids': [p[0] for p in players],
        'player_names': {p[0]: p[1] for p in players},
        'summary_message_id': None,
        'anonymous': anonymous,
        'permissions': {p[0]: {'can_vote': True, 'can_be_voted': True} for p in players},
        'voters': set(),  # Will fill after confirmation based on can_vote
    }

    # Build the initial permissions keyboard
    await show_voting_permissions(update, context, game_id, moderator_id)


async def show_voting_permissions(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str, moderator_id: int, message_id=None) -> None:
    """Show the current voting permissions in a nicely formatted table to the moderator."""
    permissions = game_voting_data[game_id]['permissions']
    player_names = game_voting_data[game_id]['player_names']

    keyboard = []
    # Header row (You can skip or include as text)
    # We'll send the header as a separate message text instead.
    # Rows: [Can Vote - Name - Can be Voted]
    for user_id, name in player_names.items():
        can_vote = "✅" if permissions[user_id]['can_vote'] else "❌"
        can_be_voted = "✅" if permissions[user_id]['can_be_voted'] else "❌"
        
        keyboard.append([
            InlineKeyboardButton(can_vote, callback_data=f"toggle_can_vote_{user_id}"),
            InlineKeyboardButton(name, callback_data="noop"),
            InlineKeyboardButton(can_be_voted, callback_data=f"toggle_can_be_voted_{user_id}")
        ])

    # Add a confirmation button at the bottom
    keyboard.append([InlineKeyboardButton("Confirm & Start Voting", callback_data="confirm_permissions")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "Set Voting Permissions (Toggle each player's ability to vote and/or be voted):\n\n" \
           "Format: [Can Vote] - [Name] - [Can be Voted]"
    if message_id:
        await context.bot.edit_message_text(
            chat_id=moderator_id,
            message_id=message_id,
            text=text,
            reply_markup=reply_markup
        )
    else:
        sent_msg = await context.bot.send_message(
            chat_id=moderator_id,
            text=text,
            reply_markup=reply_markup
        )
        # Store the message_id if needed
        game_voting_data[game_id]['permissions_message_id'] = sent_msg.message_id


async def handle_voting_permission_toggle(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data
    await query.answer()

    game_id = context.user_data.get('game_id')
    if not game_id or game_id not in game_voting_data:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No active voting session.")
        return

    permissions = game_voting_data[game_id]['permissions']

    if data.startswith("toggle_can_vote_"):
        # This means we are toggling the 'can_vote' permission
        target_user_id = int(data.replace("toggle_can_vote_", ""))
        current = permissions[target_user_id]['can_vote']
        permissions[target_user_id]['can_vote'] = not current
    elif data.startswith("toggle_can_be_voted_"):
        # This means we are toggling the 'can_be_voted' permission
        target_user_id = int(data.replace("toggle_can_be_voted_", ""))
        current = permissions[target_user_id]['can_be_voted']
        permissions[target_user_id]['can_be_voted'] = not current
    else:
        # Unknown action
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Unknown toggle action.")
        return

    moderator_id = update.effective_chat.id
    # Now redraw the permissions keyboard with updated states
    await show_voting_permissions(update, context, game_id, moderator_id, message_id=game_voting_data[game_id].get('permissions_message_id'))



async def confirm_permissions(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Once the moderator confirms the permissions, start the actual voting session."""
    query = update.callback_query
    await query.answer()

    game_id = context.user_data.get('game_id')
    if not game_id or game_id not in game_voting_data:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No active voting session.")
        return
    
    permissions = game_voting_data[game_id]['permissions']
    # Set the voters set to those who can vote
    voters = [uid for uid, perm in permissions.items() if perm['can_vote']]
    game_voting_data[game_id]['voters'] = set(voters)

    # Now proceed with sending voting messages only to those who can vote
    # and include only players who can be voted.

    # Prepare lists
    can_be_voted_players = [(uid, game_voting_data[game_id]['player_names'][uid]) 
                            for uid, perm in permissions.items() if perm['can_be_voted']]
    
    # Send voting messages to each player who can vote
    for voter_id in voters:
        keyboard = []
        for target_id, target_username in can_be_voted_players:
            button_text = f"{target_username} ❌"
            callback_data = f"vote_{target_id}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        keyboard.append([InlineKeyboardButton("Confirm Votes", callback_data=f"confirm_votes")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            if game_voting_data[game_id]['anonymous']:
                vote_text = "📢 **Anonymous Voting Session:**\nVote for a player to eliminate:"
            else:
                vote_text = "📢 **Voting Session:**\nVote for a player to eliminate:"

            await context.bot.send_message(
                chat_id=voter_id,
                text=vote_text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Failed to send voting message to user {voter_id}: {e}")

    # Send initial voting summary to the moderator
    await send_voting_summary(context, game_id)

    # Remove the permissions message, as setup is done.
    await context.bot.edit_message_reply_markup(chat_id=query.message.chat_id, message_id=query.message.message_id, reply_markup=None)
