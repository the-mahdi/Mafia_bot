"""
Functions to handle Sniper (Tak Tir) role actions in the Mafia game.
"""
import logging
from typing import Set, Dict, List
from telegram.ext import ContextTypes

from src.database import role_queries

logger = logging.getLogger("Mafia Bot Sniper Actions")

async def handle_sniper_shot(user_id: str, target_id: str, game_id: str, 
                             to_eliminate: Set[str], context: ContextTypes.DEFAULT_TYPE,
                             healed_players: Set[str] = None) -> None:
    """
    Handle Sniper (Tak Tir) shot action.
    
    Args:
        user_id: The user ID of the sniper performing the shot
        target_id: The user ID of the target to shoot
        game_id: The ID of the current game
        to_eliminate: Set of players that will be eliminated this night
        context: Telegram context object
        healed_players: Set of players that have been healed this night (optional)
    
    Returns:
        None
    """
    if not target_id:
        logger.debug(f"Sniper {user_id} didn't select a valid target")
        return
    
    # Check if the target is protected by a doctor
    if healed_players and target_id in healed_players:
        await context.bot.send_message(
            chat_id=user_id,
            text="Your target was protected by someone. Your shot had no effect."
        )
        logger.debug(f"Sniper {user_id} shot at player {target_id}, but they were protected")
        return
    
    # Get the faction of the target
    target_faction = await role_queries.get_player_faction(game_id, target_id)
    
    if target_faction == "Villager":
        # If the target is a Villager, the sniper dies too
        to_eliminate.add(user_id)
        to_eliminate.add(target_id)
        
        await context.bot.send_message(
            chat_id=user_id,
            text="You shot a Villager! Both you and your target will be eliminated."
        )
        logger.debug(f"Sniper {user_id} shot Villager {target_id}, both will be eliminated")
    else:
        # If the target is Mafia or Independent, only the target dies
        to_eliminate.add(target_id)
        
        await context.bot.send_message(
            chat_id=user_id,
            text="Your shot was successful! Your target will be eliminated."
        )
        logger.debug(f"Sniper {user_id} successfully shot non-Villager {target_id}")