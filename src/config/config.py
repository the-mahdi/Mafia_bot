import os
from utils import resource_path

def read_tokens():
    """Reads tokens and maintainer ID from token.txt."""
    try:
        with open(resource_path('token.txt'), 'r') as file:
            lines = [line.strip() for line in file.readlines()]
            if len(lines) < 3:
                raise ValueError("token.txt must contain at least three lines: "
                                 "Telegram token, Random.org API key, and Maintainer Telegram ID.")
            token = lines[0]
            random_org_api_key = lines[1]
            maintainer_id = lines[2]
            return token, random_org_api_key, maintainer_id
    except FileNotFoundError:
        raise FileNotFoundError("token.txt not found.")
    except ValueError as e:
        raise ValueError(e)

TOKEN, RANDOM_ORG_API_KEY, MAINTAINER_ID = read_tokens()