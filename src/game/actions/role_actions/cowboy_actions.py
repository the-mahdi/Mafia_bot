"""
Functions to handle Cowboy role actions in the Mafia game.
"""
import json
import logging
from typing import Set, Dict, List, Tuple
from telegram.ext import ContextTypes

from src.database.connection import conn, cursor
from src.database.user_queries import get_user_name

logger = logging.getLogger("Mafia Bot Cowboy Actions")

async def handle_cowboy_shot(
    user_id: str, 
    target_id: str, 
    game_id: str,
    eliminated_players: List[Tuple[str, str, str]],
    context: ContextTypes.DEFAULT_TYPE,
    healed_players: Set[str] = None
) -> None:
    """
    Handle Cowboy shot action.
    
    Args:
        user_id: The user ID of the cowboy performing the shot
        target_id: The user ID of the target to shoot
        game_id: The ID of the current game
        eliminated_players: List to add eliminated players and their cause
        context: Telegram context object
        healed_players: Set of players that have been healed this night (optional)
        
    Returns:
        None
    """
    if not target_id:
        logger.debug(f"Cowboy {user_id} didn't select a valid target")
        return
    
    # Check if the target is protected by a doctor
    if healed_players and target_id in healed_players:
        await context.bot.send_message(
            chat_id=user_id,
            text="Your target was protected by someone. Your shot had no effect. However, you must still leave the game."
        )
        
        # Cowboy still gets eliminated after using their ability
        cowboy_name = get_user_name(user_id)
        eliminated_players.append((user_id, cowboy_name, "cowboy_self"))
        
        await context.bot.send_message(
            chat_id=user_id,
            text="You have left the game after using your Cowboy shot!"
        )
        logger.debug(f"Cowboy {user_id} shot at player {target_id}, but they were protected. Cowboy eliminated.")
        return
    
    # Check if target is Ruyin tan (Bulletproof) with unused immunity
    is_immune = False
    
    # Get target's role
    cursor.execute("SELECT role, metadata FROM Roles WHERE game_id = ? AND user_id = ?", (game_id, target_id))
    target_result = cursor.fetchone()
    
    if target_result:
        target_role, target_metadata = target_result
        
        # Check for Bulletproof immunity
        if target_role == "Ruyin tan":
            # Parse metadata to check if immunity was already used
            immunity_used = True  # Default to true (no immunity) if can't determine
            
            if target_metadata:
                try:
                    metadata_dict = json.loads(target_metadata)
                    immunity_used = metadata_dict.get('immunity_used', False)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid metadata for Ruyin Tan player {target_id}")
            
            if not immunity_used:
                # Mark immunity as used
                cursor.execute(
                    "UPDATE Roles SET metadata = ? WHERE game_id = ? AND user_id = ?", 
                    (json.dumps({"immunity_used": True}), game_id, target_id)
                )
                is_immune = True
                await context.bot.send_message(
                    chat_id=target_id, 
                    text="You were targeted by the Cowboy, but your bulletproof vest saved you! (This works only once)"
                )
                
                # Notify the Cowboy that their shot was blocked
                await context.bot.send_message(
                    chat_id=user_id,
                    text="Your target was wearing a bulletproof vest! Your shot was ineffective."
                )
                
                # Cowboy still gets eliminated after using their ability
                cowboy_name = get_user_name(user_id)
                eliminated_players.append((user_id, cowboy_name, "cowboy_self"))
                
                await context.bot.send_message(
                    chat_id=user_id, 
                    text="You have left the game after using your Cowboy shot!"
                )
                logger.debug(f"Cowboy {user_id} shot at Ruyin Tan {target_id}, who was immune. Cowboy eliminated.")
                return  # Skip to next action
    
    # If not immune, proceed with normal elimination
    if not is_immune:
        # Mark target for elimination
        target_name = get_user_name(target_id)
        eliminated_players.append((target_id, target_name, "cowboy"))
        
        await context.bot.send_message(
            chat_id=target_id, 
            text="You have been eliminated by the Cowboy!"
        )
        
        # Cowboy also gets eliminated after using their ability
        cowboy_name = get_user_name(user_id)
        eliminated_players.append((user_id, cowboy_name, "cowboy_self"))
        
        await context.bot.send_message(
            chat_id=user_id, 
            text="You have left the game after using your Cowboy shot!"
        )
        
        logger.debug(f"Cowboy {user_id} successfully shot player {target_id}. Both are eliminated.")