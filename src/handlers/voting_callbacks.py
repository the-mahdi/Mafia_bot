from telegram import Update
from telegram.ext import ContextTypes
import logging
from src.db import conn, cursor

logger = logging.getLogger("Mafia Bot VotingCallbacks")

async def handle_announce_voting(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the 'announce_voting' callback query."""
    logger.debug("Announce Voting button pressed.")
    user_id = update.effective_user.id
    game_id = context.user_data.get('game_id')
    
    if not game_id:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No game selected.")
        return
    
    # Check if the user is the moderator
    cursor.execute("SELECT moderator_id FROM Games WHERE game_id = ?", (game_id,))
    result = cursor.fetchone()
    if not result or result[0] != user_id:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="You are not authorized to announce voting.")
        return
    
    from src.handlers.game_management.voting import prompt_voting_permissions
    await prompt_voting_permissions(update, context, game_id, anonymous=False)

async def handle_announce_anonymous_voting(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the 'announce_anonymous_voting' callback query."""
    logger.debug("Announce Anonymous Voting button pressed.")
    user_id = update.effective_user.id
    game_id = context.user_data.get('game_id')
    
    if not game_id:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No game selected.")
        return
    
    # Check if the user is the moderator
    cursor.execute("SELECT moderator_id FROM Games WHERE game_id = ?", (game_id,))
    result = cursor.fetchone()
    if not result or result[0] != user_id:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="You are not authorized to announce anonymous voting.")
        return
    
    from src.handlers.game_management.voting import prompt_voting_permissions
    await prompt_voting_permissions(update, context, game_id, anonymous=True)

async def handle_vote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the 'vote_[user_id]' callback queries."""
    query = update.callback_query
    data = query.data
    target_id = int(data.split("_")[1])
    game_id = context.user_data.get('game_id')
    
    if not game_id:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Game ID not found.")
        return
    
    from src.handlers.game_management import handle_vote
    await handle_vote(update, context, game_id, target_id)

async def handle_confirm_votes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the 'confirm_votes' callback query."""
    game_id = context.user_data.get('game_id')
    
    if not game_id:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Game ID not found.")
        return
    
    from src.handlers.game_management import confirm_votes
    await confirm_votes(update, context, game_id)

async def handle_final_confirm_vote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the 'final_confirm_vote_[user_id]' callback queries."""
    from src.handlers.game_management import final_confirm_vote
    await final_confirm_vote(update, context)

async def handle_cancel_vote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the 'cancel_vote_[user_id]' callback queries."""
    from src.handlers.game_management import cancel_vote
    await cancel_vote(update, context)

async def handle_toggle_vote_permission(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the 'toggle_can_vote_[user_id]' and 'toggle_can_be_voted_[user_id]' callback queries."""
    from src.handlers.game_management.voting import handle_voting_permission_toggle
    await handle_voting_permission_toggle(update, context)

async def handle_confirm_permissions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the 'confirm_permissions' callback query."""
    from src.handlers.game_management.voting import confirm_permissions
    await confirm_permissions(update, context)