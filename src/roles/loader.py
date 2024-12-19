import json
from utils import resource_path
import logging

logger = logging.getLogger("Mafia Bot Roles")

def load_available_roles():
    with open(resource_path('roles.json'), 'r') as file:
        data = json.load(file)
    available_roles = [role['name'] for role in data.get('roles', [])]
    logger.debug(f"Available roles loaded: {available_roles}")
    return available_roles

def load_role_descriptions():
    descriptions = {}
    with open(resource_path('roles.json'), 'r') as file:
        data = json.load(file)
    for role in data.get('roles', []):
        descriptions[role['name']] = role['description']
    return descriptions

def load_role_factions():
    factions = {}
    with open(resource_path('roles.json'), 'r') as file:
        data = json.load(file)
    for role in data.get('roles', []):
        factions[role['name']] = role['faction']
    logger.debug(f"Role factions loaded: {factions}")
    return factions