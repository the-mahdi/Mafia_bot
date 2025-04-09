"""
Voting functionality for the Mafia game.
This module handles the voting process, including:
- Creating voting sessions
- Managing vote permissions 
- Processing votes
- Generating voting summaries
"""

from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.helpers import escape_markdown
import logging
import json

from src.utils.formatting import generate_voting_summary
from src.database import vote_queries

logger = logging.getLogger("Mafia Bot Game.Voting")

# This dictionary will be used to cache data temporarily during active voting operations
# but the persistent state will be in the database
game_voting_cache = {}

class VotingManager:
    """Class to manage voting sessions and operations"""
    
    @staticmethod
    async def announce_voting(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, is_anonymous=False) -> None:
        """Announce a new voting session (either public or anonymous)"""
        operation_type = "Anonymous Voting" if is_anonymous else "Voting"
        logger.debug(f"Announcing {operation_type}.")
        
        user_id = update.effective_user.id
        game_id = context.user_data.get('game_id')
        logger.debug(f"Announcing {operation_type.lower()} for game_id: {game_id}")

        if not game_id:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="No game selected.")
            return

        # Check if the user is the moderator
        moderator_id = vote_queries.get_moderator_id(game_id)
        if not moderator_id or moderator_id != user_id:
            await context.bot.send_message(
                chat_id=update.effective_chat.id, 
                text="You are not authorized to announce voting."
            )
            return

        # Create a new voting session
        await VotingManager._create_voting_session(update, context, game_id, is_anonymous)

    @staticmethod
    async def _create_voting_session(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str, is_anonymous: bool) -> None:
        """Helper function to create a new voting session in the database"""
        
        # Delete any existing voting session for this game
        vote_queries.delete_voting_session(game_id)
        vote_queries.delete_voter_permissions(game_id)
        vote_queries.delete_votes(game_id)
        
        # Create a new VotingSession record
        vote_queries.create_voting_session(game_id, is_anonymous)
        
        # Fetch active (non-eliminated) players in the game
        players = vote_queries.get_active_players(game_id)
        
        # Initialize VoterPermissions for all players
        for player_id, _ in players:
            vote_queries.initialize_voter_permissions(game_id, player_id)
        
        # Initialize temporary cache for the UI interactions
        game_voting_cache[game_id] = {
            'player_ids': [player[0] for player in players],
            'player_names': {player[0]: player[1] for player in players}
        }
        
        # Proceed directly to the permissions setup stage
        await VotingManager.prompt_voting_permissions(update, context, game_id, is_anonymous)

    @staticmethod
    async def send_voting_summary(context: ContextTypes.DEFAULT_TYPE, game_id: str) -> None:
        """Sends or updates the voting summary message to the moderator."""
        logger.debug(f"Sending voting summary for game ID {game_id}.")

        # Fetch voting session information
        session_info = vote_queries.get_voting_session(game_id)
        if not session_info:
            logger.error(f"Game ID {game_id} not found in voting data.")
            return
        
        _, summary_message_id, _ = session_info

        # Fetch moderator ID
        moderator_id = vote_queries.get_moderator_id(game_id)
        if not moderator_id:
            logger.error(f"Game ID {game_id} not found when fetching moderator.")
            return

        # Fetch players who have voted and not voted
        voted_players = vote_queries.get_voted_players(game_id)
        not_voted_players = vote_queries.get_not_voted_players(game_id)

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
                vote_queries.update_summary_message_id(game_id, message.message_id)
        else:
            # Send a new message
            message = await context.bot.send_message(
                chat_id=moderator_id,
                text=safe_summary,
                parse_mode='MarkdownV2'
            )
            # Update summary message ID in the database
            vote_queries.update_summary_message_id(game_id, message.message_id)

    @staticmethod
    async def handle_vote(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str, target_id: int) -> None:
        """Handle a player voting for another player"""
        logger.debug("Handling vote.")
        voter_id = update.effective_user.id
        query = update.callback_query

        # Check if voting session exists
        session_info = vote_queries.get_voting_session(game_id)
        if not session_info:
            await context.bot.send_message(chat_id=voter_id, text="Voting session not found.")
            return

        # Check if voter can vote and hasn't already confirmed
        voter_info = vote_queries.get_voter_permissions(game_id, voter_id)
        if not voter_info or voter_info[0] == 0:  # can_vote == 0
            await context.bot.send_message(chat_id=voter_id, text="You are not permitted to vote.")
            return
        if voter_info[2] == 1:  # has_voted == 1
            await context.bot.send_message(chat_id=voter_id, text="You have already confirmed your votes.")
            return

        # Check if target can be voted
        target_info = vote_queries.get_voter_permissions(game_id, target_id)
        if not target_info or target_info[1] == 0:  # can_be_voted == 0
            await context.bot.send_message(chat_id=voter_id, text="This player cannot be voted for.")
            return

        # Toggle vote - if exists delete it, otherwise add it
        vote_queries.toggle_vote(game_id, voter_id, target_id)

        # Fetch all players who can be voted for
        can_be_voted_players = vote_queries.get_players_who_can_be_voted(game_id)

        # Fetch this voter's current votes
        current_votes = vote_queries.get_player_votes(game_id, voter_id)

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

    @staticmethod
    async def confirm_votes(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str) -> None:
        """Show confirmation dialog for votes"""
        logger.debug("Confirming votes.")
        voter_id = update.effective_user.id
        query = update.callback_query

        # Check if voting session exists
        session_info = vote_queries.get_voting_session(game_id)
        if not session_info:
            await context.bot.send_message(chat_id=voter_id, text="Voting session not found.")
            return

        # Check if voter can vote and hasn't already confirmed
        voter_info = vote_queries.get_voter_permissions(game_id, voter_id)
        if not voter_info or voter_info[0] == 0:  # can_vote == 0
            await context.bot.send_message(chat_id=voter_id, text="You are not permitted to vote.")
            return
        if voter_info[2] == 1:  # has_voted == 1
            await context.bot.send_message(chat_id=voter_id, text="You have already confirmed your votes.")
            return

        # Fetch current votes
        votes = vote_queries.get_player_votes_with_names(game_id, voter_id)

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

    @staticmethod
    async def final_confirm_vote(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str) -> None:
        """Finalize vote confirmation"""
        logger.debug("Final vote confirmation.")
        voter_id = update.effective_user.id
        query = update.callback_query

        # Check if voting session exists
        session_info = vote_queries.get_voting_session(game_id)
        if not session_info:
            await context.bot.send_message(chat_id=voter_id, text="Voting session not found.")
            return

        # Check if voter can vote and hasn't already confirmed
        voter_info = vote_queries.get_voter_permissions(game_id, voter_id)
        if not voter_info or voter_info[0] == 0:  # can_vote == 0
            await context.bot.send_message(chat_id=voter_id, text="You are not permitted to vote.")
            return
        if voter_info[2] == 1:  # has_voted == 1
            await context.bot.send_message(chat_id=voter_id, text="You have already confirmed your votes.")
            return

        # Mark voter as having voted
        vote_queries.update_voter_permission(game_id, voter_id, has_voted=1)

        await query.edit_message_text(text="Your votes have been finally confirmed.")

        # Update the voting summary for the moderator
        await VotingManager.send_voting_summary(context, game_id)

        # Check if all players have voted
        all_votes_cast = vote_queries.check_all_votes_cast(game_id)
        
        if all_votes_cast:
            await VotingManager.process_voting_results(update, context, game_id)

    @staticmethod
    async def cancel_vote(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str) -> None:
        """Cancel votes and return to voting interface"""
        logger.debug("Cancelling vote.")
        voter_id = update.effective_user.id
        query = update.callback_query

        # Check if voting session exists
        session_info = vote_queries.get_voting_session(game_id)
        if not session_info:
            await context.bot.send_message(chat_id=voter_id, text="Voting session not found.")
            return

        # Delete all votes for this voter
        vote_queries.delete_votes(game_id, voter_id)

        # Fetch all players who can be voted for
        can_be_voted_players = vote_queries.get_players_who_can_be_voted(game_id)

        # Build keyboard
        keyboard = []
        for target_id, target_username in can_be_voted_players:
            button_text = f"{target_username} ❌"  # Reset to default "not voted"
            callback_data = f"vote_{target_id}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

        keyboard.append([InlineKeyboardButton("Confirm Votes", callback_data="confirm_votes")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text="Vote cancelled. Please recast your votes.", reply_markup=reply_markup)

    @staticmethod
    async def process_voting_results(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str) -> None:
        """Process and announce the results of voting"""
        logger.debug("Processing voting results.")
        
        # Check if voting session exists
        session_info = vote_queries.get_voting_session(game_id)
        if not session_info:
            logger.error(f"Game ID {game_id} not found in voting data.")
            return
        is_anonymous = session_info[0] == 1

        # Fetch active (non-eliminated) player names
        players = vote_queries.get_active_players(game_id)
        player_names = {user_id: username for user_id, username in players}
        player_ids = [player[0] for player in players]

        # Count votes
        vote_counts = vote_queries.get_vote_counts(game_id)

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
        moderator_id = vote_queries.get_moderator_id(game_id)
        if not moderator_id:
            logger.error(f"Game ID {game_id} not found when fetching moderator.")
            return

        # Send the summary message to all players
        for player_id in player_ids:
            try:
                await context.bot.send_message(chat_id=player_id, text=safe_summary, parse_mode='MarkdownV2')
            except Exception as e:
                logger.error(f"Failed to send summary message to user {player_id}: {e}")

        # Fetch detailed voting data for report
        votes_data = vote_queries.get_detailed_votes(game_id)

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
                voter_perm = vote_queries.get_voter_permissions(game_id, voter_id)
                if voter_perm and voter_perm[0] == 1:  # can_vote == 1
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
        from src.utils.context import clear_user_data
        username = context.user_data.get("username")
        game_id_stored = context.user_data.get("game_id")
        
        # Clean all user data
        clear_user_data(context)
        
        # Restore the game_id and username since voting doesn't end the game
        if game_id_stored:
            context.user_data["game_id"] = game_id_stored
        if username:
            context.user_data["username"] = username

    @staticmethod
    async def prompt_voting_permissions(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str, anonymous: bool) -> None:
        """
        Prompt the moderator with a list of players and their default voting permissions.
        Moderator can toggle "Can Vote" and "Can be Voted" for each player.
        """
        # Fetch the moderator ID
        moderator_id = vote_queries.get_moderator_id(game_id)
        if not moderator_id:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Game not found.")
            return

        # Make sure the voting session exists and update anonymous status
        vote_queries.update_voting_session_anonymous(game_id, anonymous)

        # Show the permissions UI to the moderator
        await VotingManager.show_voting_permissions(update, context, game_id, moderator_id)

    @staticmethod
    async def show_voting_permissions(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str, moderator_id: int, message_id=None) -> None:
        """Show the current voting permissions in a nicely formatted table to the moderator."""
        # Fetch player permissions from the database
        player_permissions = vote_queries.get_all_voter_permissions(game_id)

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
            vote_queries.update_permissions_message_id(game_id, sent_msg.message_id)
            
            # Also cache the message ID temporarily
            if game_id not in game_voting_cache:
                game_voting_cache[game_id] = {}
            game_voting_cache[game_id]['permissions_message_id'] = sent_msg.message_id

    @staticmethod
    async def handle_voting_permission_toggle(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, permission_type: str, target_user_id: int) -> None:
        """Toggle voting permissions for a player"""
        query = update.callback_query
        await query.answer()

        game_id = context.user_data.get('game_id')
        
        # Verify voting session exists
        session_info = vote_queries.get_voting_session(game_id)
        if not session_info:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="No active voting session.")
            return

        # Get current permissions
        voter_permissions = vote_queries.get_voter_permissions(game_id, target_user_id)
        if not voter_permissions:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Player permissions not found.")
            return
        
        can_vote, can_be_voted, _ = voter_permissions
        
        # Toggle the appropriate permission
        if permission_type == "can_vote":
            vote_queries.update_voter_permission(game_id, target_user_id, can_vote=1-can_vote)  # Toggle 0->1, 1->0
        elif permission_type == "can_be_voted":
            vote_queries.update_voter_permission(game_id, target_user_id, can_be_voted=1-can_be_voted)
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Unknown permission type.")
            return

        moderator_id = update.effective_chat.id
        
        # Get the permissions message ID from cache or database
        permissions_message_id = None
        if game_id in game_voting_cache and 'permissions_message_id' in game_voting_cache[game_id]:
            permissions_message_id = game_voting_cache[game_id]['permissions_message_id']
        else:
            permissions_message_id = session_info[2]  # permissions_message_id is at index 2
            # Cache it for future use
            if game_id not in game_voting_cache:
                game_voting_cache[game_id] = {}
            game_voting_cache[game_id]['permissions_message_id'] = permissions_message_id
        
        # Now redraw the permissions keyboard with updated states
        await VotingManager.show_voting_permissions(update, context, game_id, moderator_id, message_id=permissions_message_id)

    @staticmethod
    async def confirm_permissions(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Once the moderator confirms the permissions, start the actual voting session."""
        query = update.callback_query
        await query.answer()

        game_id = context.user_data.get('game_id')
        
        # Verify voting session exists
        session_info = vote_queries.get_voting_session(game_id)
        if not session_info:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="No active voting session.")
            return
        
        is_anonymous = session_info[0] == 1
        
        # Get all players who can vote
        voters = vote_queries.get_players_who_can_vote(game_id)
        
        # Get all players who can be voted
        can_be_voted_players = vote_queries.get_players_who_can_be_voted(game_id)
        
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
        await VotingManager.send_voting_summary(context, game_id)

        # Remove the permissions message, as setup is done.
        await context.bot.edit_message_reply_markup(chat_id=query.message.chat_id, message_id=query.message.message_id, reply_markup=None)


# Compatibility functions to maintain the same API as before
# These are simple wrappers around the VotingManager class

async def announce_voting(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE) -> None:
    await VotingManager.announce_voting(update, context, is_anonymous=False)

async def announce_anonymous_voting(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE) -> None:
    await VotingManager.announce_voting(update, context, is_anonymous=True)

async def handle_vote(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str, target_id: int) -> None:
    await VotingManager.handle_vote(update, context, game_id, target_id)

async def confirm_votes(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str) -> None:
    await VotingManager.confirm_votes(update, context, game_id)

async def final_confirm_vote(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data_parts = query.data.split("_")
    game_id = data_parts[3]
    await VotingManager.final_confirm_vote(update, context, game_id)

async def cancel_vote(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data_parts = query.data.split("_")
    game_id = data_parts[2]
    await VotingManager.cancel_vote(update, context, game_id)

async def handle_voting_permission_toggle(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data
    
    if data.startswith("toggle_can_vote_"):
        target_user_id = int(data.replace("toggle_can_vote_", ""))
        permission_type = "can_vote"
    elif data.startswith("toggle_can_be_voted_"):
        target_user_id = int(data.replace("toggle_can_be_voted_", ""))
        permission_type = "can_be_voted"
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Unknown toggle action.")
        return
        
    await VotingManager.handle_voting_permission_toggle(update, context, permission_type, target_user_id)

async def confirm_permissions(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE) -> None:
    await VotingManager.confirm_permissions(update, context)