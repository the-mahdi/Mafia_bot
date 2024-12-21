# In src/handlers/game_management/inquiry.py

import logging
from telegram.ext import ContextTypes
from src.db import cursor
from src.roles import role_factions

logger = logging.getLogger("Mafia Bot GameManagement.Inquiry")

async def send_inquiry_summary(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str) -> None:
    """Sends a summary of the factions present in the game to all players."""
    logger.debug(f"Sending inquiry summary for game ID {game_id}.")

    # Fetch all players (both active and eliminated) and their roles
    cursor.execute("""
        SELECT Roles.user_id, Roles.role, Roles.eliminated
        FROM Roles
        WHERE Roles.game_id = ?
    """, (game_id,))
    players = cursor.fetchall()

    if not players:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No players found in this game.")
        return

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

    # Send the summary to all players
    for user_id, _, _ in players:
        try:
            await context.bot.send_message(chat_id=user_id, text=summary_message, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Failed to send inquiry summary to user {user_id}: {e}")

    # Also send the summary to the moderator
    cursor.execute("SELECT moderator_id FROM Games WHERE game_id = ?", (game_id,))
    moderator_id = cursor.fetchone()[0]
    if moderator_id:
        try:
            await context.bot.send_message(chat_id=moderator_id, text=summary_message, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Failed to send inquiry summary to moderator {moderator_id}: {e}")