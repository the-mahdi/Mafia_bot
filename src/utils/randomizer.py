# You can add any randomization-related functions here in the future.
# For now, it can be empty or have placeholder functions.
import random
import aiohttp
import logging
from .constants import RANDOM_ORG_API_KEY

logger = logging.getLogger("Mafia Bot Randomizer")

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