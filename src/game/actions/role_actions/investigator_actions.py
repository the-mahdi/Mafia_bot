"""
Functions to handle Investigator role actions in the Mafia game.
"""
import logging
from typing import Dict, Any, Optional
from telegram.ext import ContextTypes
from telegram import Update

from src.database.role_queries import get_player_role_info
from src.database.user_queries import get_user_name
from src.game.roles.role_manager import get_role_faction

logger = logging.getLogger("Mafia Bot Investigator Actions")

async def handle_investigation_action(
    user_id: str, 
    target_id: str, 
    game_id: str,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handle Investigator's night investigation action.
    
    Args:
        user_id: The user ID of the investigator performing the investigation
        target_id: The user ID of the target being investigated
        game_id: The ID of the current game
        context: Telegram context object
    
    Returns:
        None
    """
    if not target_id:
        logger.debug(f"Investigator {user_id} didn't select a valid target")
        return
    
    # Get the target's role information
    target_role_info = get_player_role_info(game_id, target_id)
    
    if not target_role_info:
        logger.error(f"Could not find role info for player {target_id} in game {game_id}")
        await context.bot.send_message(
            chat_id=user_id,
            text="There was an error performing your investigation. Please contact the game moderator."
        )
        return
    
    target_role = target_role_info.get('role')
    target_faction = get_role_faction(target_role)
    target_name = get_user_name(target_id)
    
    # Prepare the investigation result message
    # Note: Consider any role-specific logic here (e.g., roles that can mislead investigation)
    result_message = f"🔍 *Investigation Results* 🔍\n\n"
    result_message += f"You investigated: *{target_name}*\n"
    
    # Basic implementation - shows faction, can be extended for more complex investigation logic
    result_message += f"Your investigation reveals they belong to the *{target_faction}* faction."
    
    # Send results to the investigator
    await context.bot.send_message(
        chat_id=user_id,
        text=result_message,
        parse_mode="Markdown"
    )
    
    logger.debug(f"Investigator {user_id} successfully investigated player {target_id} - {target_role}")