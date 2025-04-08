from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import logging
from src.db import conn, cursor
from src.utils import generate_voting_summary
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.helpers import escape_markdown  # <-- New import
import json

logger = logging.getLogger("Mafia Bot GameManagement.Voting")

# This dictionary will be used to cache data temporarily during active voting operations
# but the persistent state will be in the database
game_voting_cache = {}

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

    # Create a new voting session with anonymous=False
    await _create_voting_session(update, context, game_id, False)


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

    # Create a new voting session with anonymous=True
    await _create_voting_session(update, context, game_id, True)


async def _create_voting_session(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str, is_anonymous: bool) -> None:
    """Helper function to create a new voting session in the database"""
    
    # Delete any existing voting session for this game
    cursor.execute("DELETE FROM VotingSessions WHERE game_id = ?", (game_id,))
    cursor.execute("DELETE FROM VoterPermissions WHERE game_id = ?", (game_id,))
    cursor.execute("DELETE FROM Votes WHERE game_id = ?", (game_id,))
    conn.commit()
    
    # Create a new VotingSession record
    cursor.execute("""
    INSERT INTO VotingSessions (game_id, is_anonymous, summary_message_id, permissions_message_id)
    VALUES (?, ?, NULL, NULL)
    """, (game_id, 1 if is_anonymous else 0))
    
    # Fetch active (non-eliminated) players in the game
    cursor.execute("""
    SELECT Roles.user_id, Users.username
    FROM Roles
    JOIN Users ON Roles.user_id = Users.user_id
    WHERE Roles.game_id = ? AND Roles.eliminated = 0
    """, (game_id,))
    players = cursor.fetchall()
    
    # Initialize VoterPermissions for all players
    for player_id, _ in players:
        cursor.execute("""
        INSERT INTO VoterPermissions (game_id, user_id, can_vote, can_be_voted, has_voted)
        VALUES (?, ?, 1, 1, 0)
        """, (game_id, player_id))
    
    conn.commit()
    
    # Initialize temporary cache for the UI interactions
    game_voting_cache[game_id] = {
        'player_ids': [player[0] for player in players],
        'player_names': {player[0]: player[1] for player in players}
    }
    
    # Proceed directly to the permissions setup stage
    await prompt_voting_permissions(update, context, game_id, is_anonymous)


async def send_voting_summary(context: ContextTypes.DEFAULT_TYPE, game_id: str) -> None:
    """Sends or updates the voting summary message to the moderator."""
    logger.debug(f"Sending voting summary for game ID {game_id}.")

    # Fetch voting session information
    cursor.execute("SELECT is_anonymous, summary_message_id FROM VotingSessions WHERE game_id = ?", (game_id,))
    session_info = cursor.fetchone()
    if not session_info:
        logger.error(f"Game ID {game_id} not found in voting data.")
        return
    
    summary_message_id = session_info[1]

    # Fetch moderator ID
    cursor.execute("SELECT moderator_id FROM Games WHERE game_id = ?", (game_id,))
    result = cursor.fetchone()
    if not result:
        logger.error(f"Game ID {game_id} not found when fetching moderator.")
        return
    moderator_id = result[0]

    # Fetch players who have voted and not voted
    cursor.execute("""
    SELECT Users.username
    FROM VoterPermissions
    JOIN Users ON VoterPermissions.user_id = Users.user_id
    WHERE VoterPermissions.game_id = ? AND VoterPermissions.can_vote = 1 AND VoterPermissions.has_voted = 1
    """, (game_id,))
    voted_players = [row[0] for row in cursor.fetchall()]

    cursor.execute("""
    SELECT Users.username
    FROM VoterPermissions
    JOIN Users ON VoterPermissions.user_id = Users.user_id
    WHERE VoterPermissions.game_id = ? AND VoterPermissions.can_vote = 1 AND VoterPermissions.has_voted = 0
    """, (game_id,))
    not_voted_players = [row[0] for row in cursor.fetchall()]

    summary_message = generate_voting_summary(voted_players, not_voted_players)
    safe_summary = escape_markdown(summary_message, version=2)

    # Check if a summary message already exists for this game
    if summary_message_id:
        try:
            # Edit the existing message
            await context.bot.edit_message_text(
                chat_id=moderator_id,
                message_id=summary_message_id,
                text=safe_summary,
                parse_mode='MarkdownV2'
            )
        except Exception as e:
            logger.error(f"Failed to edit voting summary message: {e}")
            # Send a new message if editing fails
            message = await context.bot.send_message(
                chat_id=moderator_id,
                text=safe_summary,
                parse_mode='MarkdownV2'
            )
            # Update summary message ID in the database
            cursor.execute("""
            UPDATE VotingSessions SET summary_message_id = ? WHERE game_id = ?
            """, (message.message_id, game_id))
            conn.commit()
    else:
        # Send a new message
        message = await context.bot.send_message(
            chat_id=moderator_id,
            text=safe_summary,
            parse_mode='MarkdownV2'
        )
        # Update summary message ID in the database
        cursor.execute("""
        UPDATE VotingSessions SET summary_message_id = ? WHERE game_id = ?
        """, (message.message_id, game_id))
        conn.commit()


async def handle_vote(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str, target_id: int) -> None:
    logger.debug("Handling vote.")
    voter_id = update.effective_user.id
    query = update.callback_query

    # Check if voting session exists
    cursor.execute("SELECT is_anonymous FROM VotingSessions WHERE game_id = ?", (game_id,))
    session_info = cursor.fetchone()
    if not session_info:
        await context.bot.send_message(chat_id=voter_id, text="Voting session not found.")
        return

    # Check if voter can vote and hasn't already confirmed
    cursor.execute("""
    SELECT can_vote, has_voted FROM VoterPermissions 
    WHERE game_id = ? AND user_id = ?
    """, (game_id, voter_id))
    voter_info = cursor.fetchone()
    if not voter_info or voter_info[0] == 0:
        await context.bot.send_message(chat_id=voter_id, text="You are not permitted to vote.")
        return
    if voter_info[1] == 1:
        await context.bot.send_message(chat_id=voter_id, text="You have already confirmed your votes.")
        return

    # Check if target can be voted
    cursor.execute("""
    SELECT can_be_voted FROM VoterPermissions 
    WHERE game_id = ? AND user_id = ?
    """, (game_id, target_id))
    target_info = cursor.fetchone()
    if not target_info or target_info[0] == 0:
        await context.bot.send_message(chat_id=voter_id, text="This player cannot be voted for.")
        return

    # Check if the vote already exists
    cursor.execute("""
    SELECT 1 FROM Votes 
    WHERE game_id = ? AND voter_id = ? AND target_id = ?
    """, (game_id, voter_id, target_id))
    vote_exists = cursor.fetchone() is not None

    # Toggle vote - if exists delete it, otherwise add it
    if vote_exists:
        cursor.execute("""
        DELETE FROM Votes 
        WHERE game_id = ? AND voter_id = ? AND target_id = ?
        """, (game_id, voter_id, target_id))
    else:
        cursor.execute("""
        INSERT INTO Votes (game_id, voter_id, target_id)
        VALUES (?, ?, ?)
        """, (game_id, voter_id, target_id))
    conn.commit()

    # Fetch all players who can be voted for
    cursor.execute("""
    SELECT VoterPermissions.user_id, Users.username
    FROM VoterPermissions
    JOIN Users ON VoterPermissions.user_id = Users.user_id
    WHERE VoterPermissions.game_id = ? AND VoterPermissions.can_be_voted = 1
    """, (game_id,))
    can_be_voted_players = cursor.fetchall()

    # Fetch this voter's current votes
    cursor.execute("""
    SELECT target_id FROM Votes 
    WHERE game_id = ? AND voter_id = ?
    """, (game_id, voter_id))
    current_votes = [row[0] for row in cursor.fetchall()]

    # Build keyboard
    keyboard = []
    for target_id_loop, target_username in can_be_voted_players:
        # Check if the voter selected this target
        if target_id_loop in current_votes:
            button_text = f"{target_username} ✅"
        else:
            button_text = f"{target_username} ❌"
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

    # Check if voting session exists
    cursor.execute("SELECT is_anonymous FROM VotingSessions WHERE game_id = ?", (game_id,))
    session_info = cursor.fetchone()
    if not session_info:
        await context.bot.send_message(chat_id=voter_id, text="Voting session not found.")
        return

    # Check if voter can vote and hasn't already confirmed
    cursor.execute("""
    SELECT can_vote, has_voted FROM VoterPermissions 
    WHERE game_id = ? AND user_id = ?
    """, (game_id, voter_id))
    voter_info = cursor.fetchone()
    if not voter_info or voter_info[0] == 0:
        await context.bot.send_message(chat_id=voter_id, text="You are not permitted to vote.")
        return
    if voter_info[1] == 1:
        await context.bot.send_message(chat_id=voter_id, text="You have already confirmed your votes.")
        return

    # Fetch current votes
    cursor.execute("""
    SELECT Votes.target_id, Users.username
    FROM Votes
    JOIN Users ON Votes.target_id = Users.user_id
    WHERE Votes.game_id = ? AND Votes.voter_id = ?
    """, (game_id, voter_id))
    votes = cursor.fetchall()

    # Prepare confirmation message
    if votes:
        voted_for_names = [vote[1] for vote in votes]
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

    # Check if voting session exists
    cursor.execute("SELECT is_anonymous FROM VotingSessions WHERE game_id = ?", (game_id,))
    session_info = cursor.fetchone()
    if not session_info:
        await context.bot.send_message(chat_id=voter_id, text="Voting session not found.")
        return

    # Check if voter can vote and hasn't already confirmed
    cursor.execute("""
    SELECT can_vote, has_voted FROM VoterPermissions 
    WHERE game_id = ? AND user_id = ?
    """, (game_id, voter_id))
    voter_info = cursor.fetchone()
    if not voter_info or voter_info[0] == 0:
        await context.bot.send_message(chat_id=voter_id, text="You are not permitted to vote.")
        return
    if voter_info[1] == 1:
        await context.bot.send_message(chat_id=voter_id, text="You have already confirmed your votes.")
        return

    # Mark voter as having voted
    cursor.execute("""
    UPDATE VoterPermissions SET has_voted = 1 
    WHERE game_id = ? AND user_id = ?
    """, (game_id, voter_id))
    conn.commit()

    await query.edit_message_text(text="Your votes have been finally confirmed.")

    # Update the voting summary for the moderator
    await send_voting_summary(context, game_id)

    # Check if all players have voted
    cursor.execute("""
    SELECT COUNT(*) FROM VoterPermissions 
    WHERE game_id = ? AND can_vote = 1 AND has_voted = 0
    """, (game_id,))
    remaining_voters = cursor.fetchone()[0]
    
    if remaining_voters == 0:
        await process_voting_results(update, context, game_id)


async def cancel_vote(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.debug("Cancelling vote.")
    voter_id = update.effective_user.id
    query = update.callback_query
    data_parts = query.data.split("_")
    game_id = data_parts[2]  # Extract game_id from callback_data

    # Check if voting session exists
    cursor.execute("SELECT is_anonymous FROM VotingSessions WHERE game_id = ?", (game_id,))
    session_info = cursor.fetchone()
    if not session_info:
        await context.bot.send_message(chat_id=voter_id, text="Voting session not found.")
        return

    # Delete all votes for this voter
    cursor.execute("""
    DELETE FROM Votes WHERE game_id = ? AND voter_id = ?
    """, (game_id, voter_id))
    conn.commit()

    # Fetch all players who can be voted for
    cursor.execute("""
    SELECT VoterPermissions.user_id, Users.username
    FROM VoterPermissions
    JOIN Users ON VoterPermissions.user_id = Users.user_id
    WHERE VoterPermissions.game_id = ? AND VoterPermissions.can_be_voted = 1
    """, (game_id,))
    can_be_voted_players = cursor.fetchall()

    # Build keyboard
    keyboard = []
    for target_id, target_username in can_be_voted_players:
        button_text = f"{target_username} ❌"  # Reset to default "not voted"
        callback_data = f"vote_{target_id}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

    keyboard.append([InlineKeyboardButton("Confirm Votes", callback_data="confirm_votes")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text="Vote cancelled. Please recast your votes.", reply_markup=reply_markup)


async def process_voting_results(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str) -> None:
    logger.debug("Processing voting results.")
    
    # Check if voting session exists
    cursor.execute("SELECT is_anonymous FROM VotingSessions WHERE game_id = ?", (game_id,))
    session_info = cursor.fetchone()
    if not session_info:
        logger.error(f"Game ID {game_id} not found in voting data.")
        return
    is_anonymous = session_info[0] == 1

    # Fetch active (non-eliminated) player names
    cursor.execute("""
    SELECT Roles.user_id, Users.username
    FROM Roles
    JOIN Users ON Roles.user_id = Users.user_id
    WHERE Roles.game_id = ? AND Roles.eliminated = 0
    """, (game_id,))
    players = cursor.fetchall()
    player_names = {user_id: username for user_id, username in players}
    player_ids = [player[0] for player in players]

    # Count votes
    cursor.execute("""
    SELECT target_id, COUNT(*) as vote_count 
    FROM Votes 
    WHERE game_id = ? 
    GROUP BY target_id
    ORDER BY vote_count DESC
    """, (game_id,))
    vote_counts = cursor.fetchall()

    # Prepare the summary message
    summary_message = "🔍 **Voting Results (Summary):**\n\n"
    if vote_counts:
        for voted_id, count in vote_counts:
            summary_message += f"• **{player_names.get(voted_id, 'Unknown')}**: {count} vote(s)\n"
    else:
        summary_message += "No votes were cast."

    # Escape summary message before sending
    safe_summary = escape_markdown(summary_message, version=2)

    # Fetch moderator ID
    cursor.execute("SELECT moderator_id FROM Games WHERE game_id = ?", (game_id,))
    result = cursor.fetchone()
    if not result:
        logger.error(f"Game ID {game_id} not found when fetching moderator.")
        return
    moderator_id = result[0]

    # Send the summary message to all players
    for player_id in player_ids:
        try:
            await context.bot.send_message(chat_id=player_id, text=safe_summary, parse_mode='MarkdownV2')
        except Exception as e:
            logger.error(f"Failed to send summary message to user {player_id}: {e}")

    # Fetch detailed voting data for report
    cursor.execute("""
    SELECT v.voter_id, v.target_id, u1.username as voter_name, u2.username as target_name
    FROM Votes v
    JOIN Users u1 ON v.voter_id = u1.user_id
    JOIN Users u2 ON v.target_id = u2.user_id
    WHERE v.game_id = ?
    """, (game_id,))
    votes_data = cursor.fetchall()

    # Create a dictionary to organize votes by voter
    votes_by_voter = {}
    for voter_id, target_id, voter_name, target_name in votes_data:
        if voter_id not in votes_by_voter:
            votes_by_voter[voter_id] = {"name": voter_name, "votes": []}
        votes_by_voter[voter_id]["votes"].append(target_name)

    # Generate detailed voting report
    detailed_report = "🗳️ **Detailed Voting Report:**\n\n"
    
    # Add voters who cast votes
    for voter_id in player_ids:
        if voter_id in votes_by_voter:
            voter_info = votes_by_voter[voter_id]
            voter_name = voter_info["name"]
            voted_names = ", ".join(voter_info["votes"])
            detailed_report += f"• **{voter_name}** voted for: {voted_names}\n"
        else:
            # Check if this player could vote but didn't
            cursor.execute("""
            SELECT can_vote FROM VoterPermissions 
            WHERE game_id = ? AND user_id = ?
            """, (game_id, voter_id))
            voter_perm = cursor.fetchone()
            if voter_perm and voter_perm[0] == 1:
                voter_name = player_names.get(voter_id, f"User {voter_id}")
                detailed_report += f"• **{voter_name}** did not vote.\n"

    # Escape detailed report
    safe_detailed_report = escape_markdown(detailed_report, version=2)

    if is_anonymous:
        # Send detailed report only to the moderator
        try:
            await context.bot.send_message(chat_id=moderator_id, text=safe_detailed_report, parse_mode='MarkdownV2')
        except Exception as e:
            logger.error(f"Failed to send detailed voting report to moderator {moderator_id}: {e}")
    else:
        # Send the detailed report to all players
        for player_id in player_ids:
            try:
                await context.bot.send_message(chat_id=player_id, text=safe_detailed_report, parse_mode='MarkdownV2')
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

    # Clean up voting data for the game - keep in DB for reference but clear cache
    if game_id in game_voting_cache:
        del game_voting_cache[game_id]
    logger.debug(f"Voting cache for game ID {game_id} has been cleared.")
    
    # Clear voting-related data from context.user_data but keep game_id and username
    # Only the moderator's context is available directly here, players will clear on other actions
    from src.utils import clear_user_data
    username = context.user_data.get("username")
    game_id_stored = context.user_data.get("game_id")
    
    # Clean all user data
    clear_user_data(context)
    
    # Restore the game_id and username since voting doesn't end the game
    if game_id_stored:
        context.user_data["game_id"] = game_id_stored
    if username:
        context.user_data["username"] = username


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

    # Make sure the voting session exists and update anonymous status
    cursor.execute("""
    UPDATE VotingSessions SET is_anonymous = ? WHERE game_id = ?
    """, (1 if anonymous else 0, game_id))
    conn.commit()

    # Show the permissions UI to the moderator
    await show_voting_permissions(update, context, game_id, moderator_id)


async def show_voting_permissions(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str, moderator_id: int, message_id=None) -> None:
    """Show the current voting permissions in a nicely formatted table to the moderator."""
    # Fetch player permissions from the database
    cursor.execute("""
    SELECT VoterPermissions.user_id, Users.username, VoterPermissions.can_vote, VoterPermissions.can_be_voted
    FROM VoterPermissions
    JOIN Users ON VoterPermissions.user_id = Users.user_id
    WHERE VoterPermissions.game_id = ?
    """, (game_id,))
    player_permissions = cursor.fetchall()

    keyboard = []
    # Rows: [Can Vote - Name - Can be Voted]
    for user_id, name, can_vote, can_be_voted in player_permissions:
        can_vote_text = "✅" if can_vote else "❌"
        can_be_voted_text = "✅" if can_be_voted else "❌"
        
        keyboard.append([
            InlineKeyboardButton(can_vote_text, callback_data=f"toggle_can_vote_{user_id}"),
            InlineKeyboardButton(name, callback_data="noop"),
            InlineKeyboardButton(can_be_voted_text, callback_data=f"toggle_can_be_voted_{user_id}")
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
        # Store the permissions message ID in the database
        cursor.execute("""
        UPDATE VotingSessions SET permissions_message_id = ? WHERE game_id = ?
        """, (sent_msg.message_id, game_id))
        conn.commit()
        
        # Also cache the message ID temporarily
        if game_id not in game_voting_cache:
            game_voting_cache[game_id] = {}
        game_voting_cache[game_id]['permissions_message_id'] = sent_msg.message_id


async def handle_voting_permission_toggle(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data
    await query.answer()

    game_id = context.user_data.get('game_id')
    
    # Verify voting session exists
    cursor.execute("SELECT 1 FROM VotingSessions WHERE game_id = ?", (game_id,))
    if not cursor.fetchone():
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No active voting session.")
        return

    if data.startswith("toggle_can_vote_"):
        # Toggle the 'can_vote' permission
        target_user_id = int(data.replace("toggle_can_vote_", ""))
        
        # Get current value and toggle it
        cursor.execute("""
        SELECT can_vote FROM VoterPermissions 
        WHERE game_id = ? AND user_id = ?
        """, (game_id, target_user_id))
        current = cursor.fetchone()[0]
        new_value = 0 if current else 1
        
        # Update in database
        cursor.execute("""
        UPDATE VoterPermissions SET can_vote = ? 
        WHERE game_id = ? AND user_id = ?
        """, (new_value, game_id, target_user_id))
        conn.commit()
        
    elif data.startswith("toggle_can_be_voted_"):
        # Toggle the 'can_be_voted' permission
        target_user_id = int(data.replace("toggle_can_be_voted_", ""))
        
        # Get current value and toggle it
        cursor.execute("""
        SELECT can_be_voted FROM VoterPermissions 
        WHERE game_id = ? AND user_id = ?
        """, (game_id, target_user_id))
        current = cursor.fetchone()[0]
        new_value = 0 if current else 1
        
        # Update in database
        cursor.execute("""
        UPDATE VoterPermissions SET can_be_voted = ? 
        WHERE game_id = ? AND user_id = ?
        """, (new_value, game_id, target_user_id))
        conn.commit()
        
    else:
        # Unknown action
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Unknown toggle action.")
        return

    moderator_id = update.effective_chat.id
    
    # Get the permissions message ID from cache or database
    permissions_message_id = None
    if game_id in game_voting_cache and 'permissions_message_id' in game_voting_cache[game_id]:
        permissions_message_id = game_voting_cache[game_id]['permissions_message_id']
    else:
        cursor.execute("SELECT permissions_message_id FROM VotingSessions WHERE game_id = ?", (game_id,))
        result = cursor.fetchone()
        if result and result[0]:
            permissions_message_id = result[0]
            # Cache it for future use
            if game_id not in game_voting_cache:
                game_voting_cache[game_id] = {}
            game_voting_cache[game_id]['permissions_message_id'] = permissions_message_id
    
    # Now redraw the permissions keyboard with updated states
    await show_voting_permissions(update, context, game_id, moderator_id, message_id=permissions_message_id)


async def confirm_permissions(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Once the moderator confirms the permissions, start the actual voting session."""
    query = update.callback_query
    await query.answer()

    game_id = context.user_data.get('game_id')
    
    # Verify voting session exists
    cursor.execute("SELECT is_anonymous FROM VotingSessions WHERE game_id = ?", (game_id,))
    session_result = cursor.fetchone()
    if not session_result:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No active voting session.")
        return
    
    is_anonymous = session_result[0] == 1
    
    # Get all players who can vote
    cursor.execute("""
    SELECT VoterPermissions.user_id, Users.username
    FROM VoterPermissions
    JOIN Users ON VoterPermissions.user_id = Users.user_id
    WHERE VoterPermissions.game_id = ? AND VoterPermissions.can_vote = 1
    """, (game_id,))
    voters = cursor.fetchall()
    
    # Get all players who can be voted
    cursor.execute("""
    SELECT VoterPermissions.user_id, Users.username
    FROM VoterPermissions
    JOIN Users ON VoterPermissions.user_id = Users.user_id
    WHERE VoterPermissions.game_id = ? AND VoterPermissions.can_be_voted = 1
    """, (game_id,))
    can_be_voted_players = cursor.fetchall()
    
    # Send voting messages to each player who can vote
    for voter_id, _ in voters:
        keyboard = []
        for target_id, target_username in can_be_voted_players:
            button_text = f"{target_username} ❌"
            callback_data = f"vote_{target_id}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        keyboard.append([InlineKeyboardButton("Confirm Votes", callback_data=f"confirm_votes")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            if is_anonymous:
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
