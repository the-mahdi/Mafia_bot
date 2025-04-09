"""
Functions to handle Doctor role actions in the Mafia game.
"""
import logging
from typing import Set
from telegram.ext import ContextTypes

logger = logging.getLogger("Mafia Bot Doctor Actions")

async def handle_heal_action(user_id: str, target_id: str, healed_players: Set[str], context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle Doctor heal action.
    
    Args:
        user_id: The user ID of the doctor performing the heal
        target_id: The user ID of the target to heal
        healed_players: Set of players that have been healed this night
        context: Telegram context object
    
    Returns:
        None
    """
    if not target_id:
        logger.debug(f"Doctor {user_id} didn't select a valid target")
        return
        
    # Add target to the set of healed players
    healed_players.add(target_id)
    
    # Notify the doctor that their action was successful
    await context.bot.send_message(
        chat_id=user_id,
        text="You have successfully protected your target for tonight."
    )
    
    logger.debug(f"Doctor {user_id} successfully healed player {target_id}")