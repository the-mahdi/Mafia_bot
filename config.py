import os
import sys
from utils import resource_path
import logging

logger = logging.getLogger("Mafia Bot Config")

def read_tokens():
    try:
        with open(resource_path('token.txt'), 'r') as file:
            lines = [line.strip() for line in file.readlines()]
            if len(lines) < 2:
                logger.error("token.txt must contain at least two lines: Telegram token and Random.org API key.")
                exit(1)
            TOKEN = lines[0]
            RANDOM_ORG_API_KEY = lines[1]
            return TOKEN, RANDOM_ORG_API_KEY
    except FileNotFoundError:
        logger.error("token.txt not found.")
        exit(1)

TOKEN, RANDOM_ORG_API_KEY = read_tokens()
