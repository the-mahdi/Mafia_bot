"""
Game inquiry module for the Mafia Bot.
Provides functions to generate and send summaries of game state to players.
"""

import logging
from telegram.ext import ContextTypes
from telegram.helpers import escape_markdown

# Updated imports for the new modular structure
from src.database.game_queries import get_moderator_id
from src.database.role_queries import get_players_with_roles
from src.game.roles.role_manager import role_factions

logger = logging.getLogger("Mafia Bot Game.Inquiry")

def _generate_faction_summary(players):
    """Generate a summary of factions for active and eliminated players."""
    # Count factions for active and eliminated players
    active_factions = {}
    eliminated_factions = {}
    
    for _, role, eliminated in players:
        faction = role_factions.get(role, "Unknown")
        if eliminated:
            eliminated_factions[faction] = eliminated_factions.get(faction, 0) + 1
        else:
            active_factions[faction] = active_factions.get(faction, 0) + 1
            
    # Prepare the summary message
    summary_message = "📢 **Inquiry (Faction Summary):** 📢\n\n"

    summary_message += "**Active Players:**\n"
    if active_factions:
        for faction, count in active_factions.items():
            summary_message += f"- {faction}: {count} player(s)\n"
    else:
        summary_message += "- No active players.\n"

    summary_message += "\n**Eliminated Players:**\n"
    if eliminated_factions:
        for faction, count in eliminated_factions.items():
            summary_message += f"- {faction}: {count} player(s)\n"
    else:
        summary_message += "- No players have been eliminated.\n"
        
    return summary_message

def _generate_detailed_summary(players):
    """Generate a detailed summary of roles per faction for active and eliminated players."""
    # Organize roles and factions for active and eliminated players
    active_info = {}
    eliminated_info = {}
    
    for _, role, eliminated in players:
        faction = role_factions.get(role, "Unknown")
        if eliminated:
            if faction not in eliminated_info:
                eliminated_info[faction] = []
            eliminated_info[faction].append(role)
        else:
            if faction not in active_info:
                active_info[faction] = []
            active_info[faction].append(role)
            
    # Prepare the detailed summary message
    summary_message = "📢 **Inquiry (Detailed Summary):** 📢\n\n"

    summary_message += "**Active Players:**\n"
    if active_info:
        for faction, roles in active_info.items():
            summary_message += f"- {faction}:\n"
            for role in set(roles):  # Use set to avoid duplicate role entries
                count = roles.count(role)
                summary_message += f"  - {role} ({count})\n"
    else:
        summary_message += "- No active players.\n"

    summary_message += "\n**Eliminated Players:**\n"
    if eliminated_info:
        for faction, roles in eliminated_info.items():
            summary_message += f"- {faction}:\n"
            for role in set(roles):  # Use set to avoid duplicate role entries
                count = roles.count(role)
                summary_message += f"  - {role} ({count})\n"
    else:
        summary_message += "- No players have been eliminated.\n"
        
    return summary_message

async def _send_message_to_players(context, players, moderator_id, message):
    """Send a message to all players and the moderator."""
    safe_message = escape_markdown(message, version=2)
    
    # Send to all players
    for user_id, _, _ in players:
        try:
            await context.bot.send_message(chat_id=user_id, text=safe_message, parse_mode='MarkdownV2')
        except Exception as e:
            logger.error(f"Failed to send message to user {user_id}: {e}")
    
    # Send to moderator
    if moderator_id:
        try:
            await context.bot.send_message(chat_id=moderator_id, text=safe_message, parse_mode='MarkdownV2')
        except Exception as e:
            logger.error(f"Failed to send message to moderator {moderator_id}: {e}")

async def send_inquiry_summary(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str) -> None:
    """Sends a summary of the factions present in the game to all players."""
    logger.debug(f"Sending inquiry summary for game ID {game_id}.")

    # Fetch all players (both active and eliminated) and their roles
    players = get_players_with_roles(game_id)
    
    if not players:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No players found in this game.")
        return

    # Get moderator ID
    moderator_id = get_moderator_id(game_id)
    
    # Generate faction summary
    summary_message = _generate_faction_summary(players)
    
    # Send summary to all players and moderator
    await _send_message_to_players(context, players, moderator_id, summary_message)


async def send_detailed_inquiry_summary(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str) -> None:
    """Sends a detailed summary of the factions and roles present in the game to all players."""
    logger.debug(f"Sending detailed inquiry summary for game ID {game_id}.")

    # Fetch all players (both active and eliminated) and their roles
    players = get_players_with_roles(game_id)
    
    if not players:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No players found in this game.")
        return

    # Get moderator ID
    moderator_id = get_moderator_id(game_id)
    
    # Generate detailed summary
    summary_message = _generate_detailed_summary(players)
    
    # Send summary to all players and moderator
    await _send_message_to_players(context, players, moderator_id, summary_message)