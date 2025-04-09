"""
Module for handling win condition checks in the Mafia game.
This module is responsible for checking if any faction has won the game based on game state.
"""

import json
import logging
import datetime
from telegram.ext import ContextTypes
from src.database.connection import conn, cursor
from src.game.state_machine import GameState

logger = logging.getLogger("Mafia Bot WinConditions")

async def check_win_condition(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str):
    """
    Check if any faction has won the game.
    
    Args:
        update: The update context
        context: The callback context
        game_id: The ID of the game to check
        
    Returns:
        bool: True if the game is over, False if it continues
    """
    logger.debug(f"Checking win conditions for game {game_id}")
    
    # Count alive players by faction - improved query to fetch comprehensive game state
    cursor.execute("""
    SELECT 
        r.role,
        ro.faction,
        u.username,
        r.user_id,
        r.eliminated,
        r.metadata
    FROM Roles r
    JOIN Users u ON r.user_id = u.user_id
    JOIN (
        SELECT role, json_extract(value, '$.faction') as faction
        FROM (
            SELECT role, json_each(json_extract(value, '$.actions')) as value
            FROM json_each((SELECT json_extract(readfile('data/roles.json'), '$.roles')))
        )
        GROUP BY role
    ) ro ON r.role = ro.role
    WHERE r.game_id = ?
    ORDER BY r.eliminated, ro.faction, r.role
    """, (game_id,))
    
    all_players = cursor.fetchall()
    
    # Build comprehensive game state
    game_state = {
        'total_players': len(all_players),
        'alive_players': 0,
        'eliminated_players': 0,
        'factions': {},
        'players_by_faction': {},
        'players': []
    }
    
    # Process players
    for role, faction, username, user_id, eliminated, metadata in all_players:
        player_info = {
            'user_id': user_id,
            'username': username,
            'role': role,
            'faction': faction,
            'eliminated': bool(eliminated),
            'metadata': json.loads(metadata) if metadata else {}
        }
        
        game_state['players'].append(player_info)
        
        # Count alive/eliminated
        if eliminated:
            game_state['eliminated_players'] += 1
        else:
            game_state['alive_players'] += 1
            
            # Initialize faction counters if needed
            if faction not in game_state['factions']:
                game_state['factions'][faction] = 0
                game_state['players_by_faction'][faction] = []
            
            # Increment faction counter and add to faction list
            game_state['factions'][faction] += 1
            game_state['players_by_faction'][faction].append(player_info)
    
    # Log the detailed game state
    logger.debug(f"Game state for {game_id}: {game_state['alive_players']} alive players, " +
                f"factions: {game_state['factions']}")
    
    # Store game state in context for access by other functions
    if 'game_data' not in context.chat_data:
        context.chat_data['game_data'] = {}
    if game_id not in context.chat_data['game_data']:
        context.chat_data['game_data'][game_id] = {}
    
    context.chat_data['game_data'][game_id]['game_state'] = game_state
    
    # Check win conditions using the fetched game state
    mafia_count = game_state['factions'].get('Mafia', 0)
    villager_count = game_state['factions'].get('Villager', 0)
    independent_count = game_state['factions'].get('Independent', 0)
    
    winner = None
    win_reason = ""
    
    # Check win conditions
    # 1. Villagers win if no Mafia members remain
    if mafia_count == 0 and villager_count > 0:
        winner = "Villagers"
        win_reason = "All Mafia members have been eliminated!"
    
    # 2. Mafia wins if they equal or outnumber the Villagers
    elif mafia_count >= villager_count and mafia_count > 0:
        winner = "Mafia"
        win_reason = "The Mafia now equals or outnumbers the Villagers!"
    
    # 3. Check for Independent wins - specific for each independent role
    # Get all alive independent players
    independent_players = game_state['players_by_faction'].get('Independent', [])
    for player in independent_players:
        role = player['role']
        user_id = player['user_id']
        
        # Example: Serial Killer win condition (last player standing or only other Mafia remain)
        if role == "Serial Killer" and game_state['alive_players'] <= 2 and mafia_count == 0:
            winner = "Serial Killer"
            win_reason = f"The Serial Killer ({player['username']}) has eliminated all threats!"
        
        # Example: Jester win condition (if they were eliminated by vote)
        if role == "Jester":
            metadata = player['metadata']
            if player['eliminated'] and metadata.get('elimination_cause') == 'vote':
                winner = "Jester"
                win_reason = f"The Jester ({player['username']}) tricked everyone into voting them out!"
        
        # Add more independent role win conditions as needed
    
    if winner:
        # Game is over - update game status in the database
        game_end_time = int(datetime.datetime.now().timestamp())
        cursor.execute("""
            UPDATE Games 
            SET current_phase = ?, 
                winner = ?, 
                win_reason = ?,
                ended = 1,
                end_time = ?
            WHERE game_id = ?
        """, (GameState.GAME_OVER.name, winner, win_reason, game_end_time, game_id))
        conn.commit()
        
        logger.info(f"Game {game_id} ended with winner: {winner} - Reason: {win_reason}")
        
        # Cancel any active timers for this game
        if 'active_timers' in context.chat_data:
            for timer_key in list(context.chat_data['active_timers'].keys()):
                if timer_key.startswith(f"{game_id}_"):
                    job = context.chat_data['active_timers'].pop(timer_key)
                    job.schedule_removal()
                    logger.debug(f"Removed timer {timer_key} for ended game")
        
        # Announce winner
        cursor.execute("SELECT user_id FROM Roles WHERE game_id = ?", (game_id,))
        all_players_ids = [row[0] for row in cursor.fetchall()]
        
        # Get moderator ID and game chat ID for final announcement
        cursor.execute("SELECT moderator_id, chat_id FROM Games WHERE game_id = ?", (game_id,))
        moderator_data = cursor.fetchone()
        moderator_id = moderator_data[0]
        game_chat_id = moderator_data[1]
        
        # Construct win announcement with emoji for visual appeal
        win_announcement = f"🏆 Game Over! The {winner} have won the game! 🏆\n{win_reason}"
        
        # Send to moderator first
        await context.bot.send_message(
            chat_id=moderator_id,
            text=win_announcement
        )
        
        # Send to all players
        for user_id in all_players_ids:
            await context.bot.send_message(
                chat_id=user_id,
                text=win_announcement
            )
        
        # If there's a game chat, announce there too
        if game_chat_id:
            try:
                await context.bot.send_message(
                    chat_id=game_chat_id, 
                    text=win_announcement
                )
                logger.debug(f"Sent game end announcement to game chat {game_chat_id}")
            except Exception as e:
                logger.error(f"Failed to send game end announcement to game chat: {e}")
        
        # Reveal all roles - formatted nicely with emoji indicators
        reveal_message = "📜 Final role assignments:\n\n"
        
        # Group by faction for better readability
        factions = {}
        for player in game_state['players']:
            faction = player['faction']
            if faction not in factions:
                factions[faction] = []
            factions[faction].append(player)
        
        # Generate the reveal message by faction
        for faction, players in factions.items():
            reveal_message += f"**{faction}**:\n"
            for player in players:
                status = "🪦 Eliminated" if player['eliminated'] else "🔆 Alive"
                cause = ""
                if player['eliminated'] and player['metadata'].get('elimination_cause'):
                    cause = f" (by {player['metadata']['elimination_cause']})"
                reveal_message += f"- {player['username']}: {player['role']}{cause} - {status}\n"
            reveal_message += "\n"
        
        # Send the role reveal to all players
        for user_id in all_players_ids:
            await context.bot.send_message(
                chat_id=user_id,
                text=reveal_message
            )
        
        # Send a game summary with statistics to the moderator
        stats_message = "📊 Game Statistics:\n\n"
        stats_message += f"Total players: {game_state['total_players']}\n"
        stats_message += f"Winner: {winner}\n"
        stats_message += f"Win reason: {win_reason}\n\n"
        
        # Add faction statistics
        stats_message += "Faction distribution at game end:\n"
        for faction, count in game_state['factions'].items():
            stats_message += f"- {faction}: {count} alive\n"
        
        # Send statistics to moderator
        await context.bot.send_message(
            chat_id=moderator_id,
            text=stats_message
        )
        
        # Clean up any persistent game data
        # 1. Remove game-specific data from context
        if game_id in context.chat_data.get('game_data', {}):
            del context.chat_data['game_data'][game_id]
            logger.debug(f"Cleared game data from context for game {game_id}")
        
        # 2. Clear any temporary game data from database
        # Keep the core game record and roles for history, but clear actions
        cursor.execute("DELETE FROM Actions WHERE game_id = ?", (game_id,))
        conn.commit()
        logger.debug(f"Cleared actions for ended game {game_id}")
        
        # Return True to indicate game is over
        return True
    
    # Return False to indicate game continues
    return False