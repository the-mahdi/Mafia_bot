import sqlite3
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import logging
import uuid
import asyncio
import random
import aiohttp
# TODO: Update these imports when the respective refactoring tasks are completed
from src.db import conn, cursor  # Will be updated to src.database.connection
from src.roles import available_roles, role_descriptions, role_templates, role_factions  # Will be updated to src.game.roles.role_manager
from src.utils.path import resource_path
from src.utils import generate_voting_summary  # Will be updated to src.utils.formatting
from src.config import RANDOM_ORG_API_KEY  # Will be updated to src.core.config
import json

logger = logging.getLogger("Mafia Bot GameManagement")

# Initialize an asyncio lock for synchronization
role_counts_lock = asyncio.Lock()

# Number of roles per page
ROLES_PER_PAGE = 27

async def get_random_shuffle(lst: list, api_key: str) -> list:
    """
    Shuffles a list using Random.org's generateIntegerSequences API. Returns the shuffled list if successful,
    otherwise returns a locally shuffled list.
    """
    if not lst:
        return lst.copy()

    payload = {
        "jsonrpc": "2.0",
        "method": "generateIntegerSequences",
        "params": {
            "apiKey": api_key,
            "n": 1,  # Number of sequences
            "length": len(lst),  # Length of each sequence
            "min": 1,  # Minimum integer
            "max": len(lst),  # Maximum integer
            "replacement": False  # No replacement to ensure a permutation
        },
        "id": 1
    }

    headers = {'Content-Type': 'application/json'}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post('https://api.random.org/json-rpc/4/invoke', json=payload, headers=headers, timeout=10) as resp:
                if resp.status != 200:
                    logger.error(f"Random.org API returned non-200 status code: {resp.status}")
                    return random.sample(lst, len(lst))  # Fallback to local shuffle
                data = await resp.json()
                if 'result' in data and 'random' in data['result'] and 'data' in data['result']['random']:
                    shuffle_sequence = data['result']['random']['data'][0]  # First (and only) sequence
                    # Validate the shuffle_sequence
                    if sorted(shuffle_sequence) != list(range(1, len(lst) + 1)):
                        logger.error("Invalid shuffle sequence received from Random.org.")
                        return random.sample(lst, len(lst))  # Fallback to local shuffle
                    # Convert to 0-based indices
                    shuffled_list = [lst[i - 1] for i in shuffle_sequence]
                    return shuffled_list
                else:
                    logger.error(f"Unexpected response format from Random.org: {data}")
                    return random.sample(lst, len(lst))  # Fallback to local shuffle
    except Exception as e:
        logger.error(f"Exception while fetching shuffle from Random.org: {e}")
        return random.sample(lst, len(lst))  # Fallback to local shuffle

def get_player_count(game_id: int) -> int:
    cursor.execute("SELECT COUNT(*) FROM Roles WHERE game_id = ?", (game_id,))
    count = cursor.fetchone()[0]
    logger.debug(f"Game ID {game_id} has {count} players.")
    return count

def get_templates_for_player_count(player_count: int) -> list:
    templates = role_templates.get(str(player_count), [])
    logger.debug(f"Templates for player count {player_count}: {templates}")
    return templates