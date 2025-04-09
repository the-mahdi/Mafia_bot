"""
Functions to handle Mafia role actions in the Mafia game.
"""
import json
import logging
from typing import Set, Dict, List, Optional
from telegram.ext import ContextTypes

from src.database.connection import conn, cursor
from src.database import role_queries

logger = logging.getLogger("Mafia Bot Mafia Actions")

async def handle_mafia_kill(user_id: str, target_id: str, game_id: str, 
                           kill_targets: Set[str], context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle standard Mafia kill action.
    
    Args:
        user_id: The user ID of the mafia member performing the kill
        target_id: The user ID of the target to kill
        game_id: The ID of the current game
        kill_targets: Set of players that will be marked for elimination this night
        context: Telegram context object
    
    Returns:
        None
    """
    if not target_id:
        logger.debug(f"Mafia member {user_id} didn't select a valid target")
        return
    
    # Add target to the set of kill targets
    kill_targets.add(target_id)
    
    # Notify the mafia member that their action was successful
    await context.bot.send_message(
        chat_id=user_id,
        text="The Mafia's target has been marked for elimination tonight."
    )
    
    logger.debug(f"Mafia member {user_id} marked player {target_id} for elimination")

async def handle_double_kill(game_id: str, user_id: str, target_ids: List[str], 
                             kill_targets: Set[str], context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle Mafia double kill action after Mashoghe death.
    
    Args:
        game_id: The ID of the current game
        user_id: The user ID of the God Father performing the kill
        target_ids: List of user IDs to kill (should be 2)
        kill_targets: Set of players that will be marked for elimination this night
        context: Telegram context object
    
    Returns:
        None
    """
    if not target_ids or len(target_ids) != 2:
        logger.debug(f"God Father {user_id} didn't select two valid targets for double kill")
        return
    
    # Add targets to the set of kill targets
    kill_targets.update(target_ids)
    
    # Notify the God Father that their action was successful
    await context.bot.send_message(
        chat_id=user_id,
        text="You have successfully marked two targets for elimination tonight."
    )
    
    logger.debug(f"God Father {user_id} marked players {target_ids} for double elimination")
    
    # Reset the double kill flag in game metadata
    cursor.execute("SELECT metadata FROM Games WHERE game_id = ?", (game_id,))
    game_metadata_row = cursor.fetchone()
    
    if game_metadata_row and game_metadata_row[0]:
        try:
            game_metadata = json.loads(game_metadata_row[0])
            game_metadata['mafia_double_kill_enabled'] = False
            cursor.execute(
                "UPDATE Games SET metadata = ? WHERE game_id = ?", 
                (json.dumps(game_metadata), game_id)
            )
            conn.commit()
        except Exception as e:
            logger.error(f"Error updating game metadata after double kill: {e}")

async def handle_joker_action(game_id: str, user_id: str, target_id: str, 
                              context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle Joker action to reverse investigation results.
    
    Args:
        game_id: The ID of the current game
        user_id: The user ID of the Joker
        target_id: The user ID of the player whose investigation result will be reversed
        context: Telegram context object
        
    Returns:
        None
    """
    if not target_id:
        logger.debug(f"Joker {user_id} didn't select a valid target")
        return
    
    # Store the Joker's target in game metadata for reference during Detective investigations
    cursor.execute("SELECT metadata FROM Games WHERE game_id = ?", (game_id,))
    game_metadata_row = cursor.fetchone()
    game_metadata = {}
    
    if game_metadata_row and game_metadata_row[0]:
        try:
            game_metadata = json.loads(game_metadata_row[0])
        except json.JSONDecodeError:
            logger.warning(f"Invalid metadata for game {game_id}, initializing as empty")
            game_metadata = {}
    
    if 'joker_targets' not in game_metadata:
        game_metadata['joker_targets'] = []
    
    game_metadata['joker_targets'].append(target_id)
    
    cursor.execute(
        "UPDATE Games SET metadata = ? WHERE game_id = ?", 
        (json.dumps(game_metadata), game_id)
    )
    conn.commit()
    
    await context.bot.send_message(
        chat_id=user_id,
        text="Your Joker action has been set. If the Detective investigates your chosen target, the results will be reversed."
    )
    
    logger.debug(f"Joker {user_id} set target {target_id} for result reversal")

async def handle_doctor_lec_save(game_id: str, user_id: str, target_id: str, 
                                context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle Doctor Lecter's ability to save a Mafia member from Sniper shot.
    
    Args:
        game_id: The ID of the current game
        user_id: The user ID of Doctor Lecter
        target_id: The user ID of the Mafia member to protect
        context: Telegram context object
        
    Returns:
        None
    """
    if not target_id:
        logger.debug(f"Doctor Lecter {user_id} didn't select a valid target")
        return
    
    # First verify that target is indeed Mafia
    is_mafia = await role_queries.is_player_in_faction(game_id, target_id, "Mafia")
    
    if not is_mafia:
        await context.bot.send_message(
            chat_id=user_id,
            text="You can only protect Mafia members. Your action has failed."
        )
        logger.debug(f"Doctor Lecter {user_id} tried to protect non-Mafia player {target_id}")
        return
    
    # Store the protected player in game metadata
    cursor.execute("SELECT metadata FROM Games WHERE game_id = ?", (game_id,))
    game_metadata_row = cursor.fetchone()
    game_metadata = {}
    
    if game_metadata_row and game_metadata_row[0]:
        try:
            game_metadata = json.loads(game_metadata_row[0])
        except json.JSONDecodeError:
            logger.warning(f"Invalid metadata for game {game_id}, initializing as empty")
            game_metadata = {}
    
    if 'doctor_lec_protected' not in game_metadata:
        game_metadata['doctor_lec_protected'] = []
    
    game_metadata['doctor_lec_protected'].append(target_id)
    
    cursor.execute(
        "UPDATE Games SET metadata = ? WHERE game_id = ?", 
        (json.dumps(game_metadata), game_id)
    )
    conn.commit()
    
    await context.bot.send_message(
        chat_id=user_id,
        text="You have successfully protected your fellow Mafia member from the Sniper's shot tonight."
    )
    
    # Notify the protected player
    await context.bot.send_message(
        chat_id=target_id,
        text="You feel a sense of security tonight - Doctor Lecter is watching over you."
    )
    
    logger.debug(f"Doctor Lecter {user_id} protected Mafia member {target_id} from Sniper")

async def apply_mafia_kills(game_id: str, kill_targets: Set[str], healed_players: Set[str],
                           ruyin_tan_immunity: Dict[str, bool], eliminated_players: List[tuple],
                           context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Apply standard mafia kills that weren't handled by special actions.
    
    Args:
        game_id: The ID of the current game
        kill_targets: Set of players targeted by Mafia kills
        healed_players: Set of players protected by the Doctor
        ruyin_tan_immunity: Dictionary tracking Bulletproof players' immunity status
        eliminated_players: List to add eliminated players and their cause
        context: Telegram context object
        
    Returns:
        bool: True if Mashoghe was killed, False otherwise
    """
    mashoghe_died = False
    
    for target_id in kill_targets:
        if target_id not in healed_players:
            # Check if target is already eliminated (e.g., by sniper)
            cursor.execute("SELECT eliminated, role FROM Roles WHERE game_id = ? AND user_id = ?", (game_id, target_id))
            result = cursor.fetchone()
            if result and result[0] == 0:  # not yet eliminated
                role = result[1]
                
                # Check if target is Mashoghe - track if they're killed
                if role == "Mashoghe":
                    mashoghe_died = True
                    logger.debug(f"Mashoghe (user_id: {target_id}) was killed during this night.")
                
                # Check if target is Ruyin tan (Bulletproof) with unused immunity
                is_immune = False
                if role == "Ruyin tan" and not ruyin_tan_immunity.get(target_id, True):
                    # Mark immunity as used
                    cursor.execute(
                        "UPDATE Roles SET metadata = ? WHERE game_id = ? AND user_id = ?", 
                        (json.dumps({"immunity_used": True}), game_id, target_id)
                    )
                    is_immune = True
                    await context.bot.send_message(
                        chat_id=target_id, 
                        text="You were targeted by the Mafia, but your bulletproof vest saved you! (This works only once)"
                    )
                
                # Check if target is ToughGuy (can survive one attack)
                if role == "ToughGuy" and not is_immune:
                    # Check if already hit once
                    cursor.execute("SELECT metadata FROM Roles WHERE game_id = ? AND user_id = ?", (game_id, target_id))
                    metadata_row = cursor.fetchone()
                    metadata = {}
                    
                    if metadata_row and metadata_row[0]:
                        try:
                            metadata = json.loads(metadata_row[0])
                        except:
                            metadata = {}
                    
                    hit_before = metadata.get('hit_before', False)
                    
                    if not hit_before:
                        # First hit - survive but mark as hit
                        metadata['hit_before'] = True
                        cursor.execute(
                            "UPDATE Roles SET metadata = ? WHERE game_id = ? AND user_id = ?", 
                            (json.dumps(metadata), game_id, target_id)
                        )
                        await context.bot.send_message(
                            chat_id=target_id, 
                            text="You were attacked but survived due to your toughness! A second attack will be fatal."
                        )
                        is_immune = True
                
                if not is_immune:
                    cursor.execute("SELECT username FROM Users WHERE user_id = ?", (target_id,))
                    username = cursor.fetchone()[0]
                    eliminated_players.append((target_id, username, "mafia_kill"))
                    await context.bot.send_message(chat_id=target_id, text="You have been eliminated during the night!")
    
    return mashoghe_died

async def handle_natasha_silence(game_id: str, user_id: str, target_id: str, 
                                context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle Natasha's ability to silence a player for the next day.
    
    Args:
        game_id: The ID of the current game
        user_id: The user ID of Natasha
        target_id: The user ID of the player to silence
        context: Telegram context object
        
    Returns:
        None
    """
    if not target_id:
        logger.debug(f"Natasha {user_id} didn't select a valid target")
        return
    
    # Check if target is immune to silence (e.g., blessed by Priest)
    cursor.execute("SELECT metadata FROM Roles WHERE game_id = ? AND user_id = ?", (game_id, target_id))
    metadata_row = cursor.fetchone()
    metadata = {}
    
    if metadata_row and metadata_row[0]:
        try:
            metadata = json.loads(metadata_row[0])
        except:
            metadata = {}
    
    if metadata.get('silence_immune', False):
        await context.bot.send_message(
            chat_id=user_id,
            text="Your target is somehow protected from being silenced. Your action failed."
        )
        return
    
    # Mark player as silenced for the next day
    metadata['silenced'] = True
    cursor.execute(
        "UPDATE Roles SET metadata = ? WHERE game_id = ? AND user_id = ?", 
        (json.dumps(metadata), game_id, target_id)
    )
    conn.commit()
    
    await context.bot.send_message(
        chat_id=user_id,
        text="Your target will be silenced for the next day."
    )
    
    await context.bot.send_message(
        chat_id=target_id,
        text="You have been silenced by Natasha! You won't be able to speak during the next day phase."
    )
    
    logger.debug(f"Natasha {user_id} silenced player {target_id} for the next day")