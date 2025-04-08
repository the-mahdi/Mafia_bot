from telegram import Update
from telegram.ext import ContextTypes
import logging
from src.db import conn, cursor
from src.handlers.game_management import (
    start_latest_game, eliminate_player, handle_elimination_confirmation,
    confirm_elimination, cancel_elimination, revive_player,
    handle_revive_confirmation, confirm_revive, cancel_revive,
    send_inquiry_summary, send_detailed_inquiry_summary,
)

logger = logging.getLogger("Mafia Bot GameManagementCallbacks")

async def handle_start_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the 'start_game_manage_games' callback query."""
    logger.debug("Start Game button pressed.")
    await start_latest_game(update, context)

async def handle_eliminate_player(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the 'eliminate_player' callback query."""
    logger.debug("Eliminate player button pressed.")
    user_id = update.effective_user.id
    game_id = context.user_data.get('game_id')
    
    if not game_id:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No game selected.")
        return
    
    # Check if the user is the moderator
    cursor.execute("SELECT moderator_id FROM Games WHERE game_id = ?", (game_id,))
    result = cursor.fetchone()
    if not result or result[0] != user_id:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="You are not authorized to eliminate players.")
        return
    
    await eliminate_player(update, context, game_id)

async def handle_elimination_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the 'eliminate_confirm_[user_id]' callback queries."""
    query = update.callback_query
    data = query.data
    target_user_id = int(data.split("_")[2])
    game_id = context.user_data.get('game_id')
    
    if not game_id:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No game selected.")
        return
        
    await handle_elimination_confirmation(update, context, game_id, target_user_id)

async def handle_elimination_yes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the 'eliminate_yes_[user_id]' callback queries."""
    query = update.callback_query
    data = query.data
    target_user_id = int(data.split("_")[2])
    game_id = context.user_data.get('game_id')
    
    if not game_id:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No game selected.")
        return
        
    await confirm_elimination(update, context, game_id, target_user_id)

async def handle_elimination_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the 'eliminate_cancel_[user_id]' callback queries."""
    query = update.callback_query
    data = query.data
    target_user_id = int(data.split("_")[2])
    game_id = context.user_data.get('game_id')
    
    if not game_id:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No game selected.")
        return
        
    await cancel_elimination(update, context, game_id, target_user_id)

async def handle_revive_player(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the 'revive_player' callback query."""
    logger.debug("Revive player button pressed.")
    user_id = update.effective_user.id
    game_id = context.user_data.get('game_id')
    
    if not game_id:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No game selected.")
        return
    
    # Check if the user is the moderator
    cursor.execute("SELECT moderator_id FROM Games WHERE game_id = ?", (game_id,))
    result = cursor.fetchone()
    if not result or result[0] != user_id:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="You are not authorized to revive players.")
        return
    
    await revive_player(update, context, game_id)

async def handle_revive_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the 'revive_confirm_[user_id]' callback queries."""
    query = update.callback_query
    data = query.data
    target_user_id = int(data.split("_")[2])
    game_id = context.user_data.get('game_id')
    
    if not game_id:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No game selected.")
        return
        
    await handle_revive_confirmation(update, context, game_id, target_user_id)

async def handle_revive_yes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the 'revive_yes_[user_id]' callback queries."""
    query = update.callback_query
    data = query.data
    target_user_id = int(data.split("_")[2])
    game_id = context.user_data.get('game_id')
    
    if not game_id:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No game selected.")
        return
        
    await confirm_revive(update, context, game_id, target_user_id)

async def handle_revive_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the 'revive_cancel_[user_id]' callback queries."""
    query = update.callback_query
    data = query.data
    target_user_id = int(data.split("_")[2])
    game_id = context.user_data.get('game_id')
    
    if not game_id:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No game selected.")
        return
        
    await cancel_revive(update, context, game_id, target_user_id)

async def handle_inquiry_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the 'inquiry_summary' callback query."""
    logger.debug("Inquiry (Summary) button pressed.")
    user_id = update.effective_user.id
    game_id = context.user_data.get('game_id')
    
    if not game_id:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No game selected.")
        return
    
    # Check if the user is the moderator
    cursor.execute("SELECT moderator_id FROM Games WHERE game_id = ?", (game_id,))
    result = cursor.fetchone()
    if not result or result[0] != user_id:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="You are not authorized to use this feature.")
        return
    
    await send_inquiry_summary(update, context, game_id)

async def handle_inquiry_detailed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the 'inquiry_detailed' callback query."""
    logger.debug("Inquiry (Detailed) button pressed.")
    user_id = update.effective_user.id
    game_id = context.user_data.get('game_id')
    
    if not game_id:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No game selected.")
        return
    
    # Check if the user is the moderator
    cursor.execute("SELECT moderator_id FROM Games WHERE game_id = ?", (game_id,))
    result = cursor.fetchone()
    if not result or result[0] != user_id:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="You are not authorized to use this feature.")
        return
    
    await send_detailed_inquiry_summary(update, context, game_id)