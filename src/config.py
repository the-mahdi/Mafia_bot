import os
import json
from src.utils.path import resource_path
import logging

logger = logging.getLogger("Mafia Bot Config")

def read_tokens():
    try:
        with open(resource_path(os.path.join('data','token.txt')), 'r') as file:
            lines = [line.strip() for line in file.readlines()]
            if len(lines) < 3:
                logger.error("token.txt must contain at least three lines: Telegram token, Random.org API key, and Maintainer Telegram ID.")
                exit(1)
            TOKEN = lines[0]
            RANDOM_ORG_API_KEY = lines[1]
            MAINTAINER_ID = lines[2]
            return TOKEN, RANDOM_ORG_API_KEY, MAINTAINER_ID
    except FileNotFoundError:
        logger.error("token.txt not found.")
        exit(1)

TOKEN, RANDOM_ORG_API_KEY, MAINTAINER_ID = read_tokens()