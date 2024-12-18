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

def load_role_templates():
    try:
        with open(resource_path('role_templates.json'), 'r') as file:
            data = json.load(file)
            templates = data.get('templates', {})
            pending_templates = data.get('pending_templates', {})
        logger.debug(f"Role templates loaded: {templates}")
        logger.debug(f"Pending templates loaded: {pending_templates}")
        return templates, pending_templates
    except FileNotFoundError:
        logger.warning("role_templates.json not found. Creating a new one.")
        return {}, {}
    except json.JSONDecodeError:
        logger.error("Invalid JSON format in role_templates.json. Starting with empty templates.")
        return {}, {}

def save_role_templates(templates, pending_templates):
    with open(resource_path('role_templates.json'), 'w') as file:
        json.dump({'templates': templates, 'pending_templates': pending_templates}, file, indent=2)
    logger.debug(f"Role templates saved: {templates}")
    logger.debug(f"Pending templates saved: {pending_templates}")

def load_role_factions():
    factions = {}
    with open(resource_path('roles.json'), 'r') as file:
        data = json.load(file)
        for role in data.get('roles', []):
            factions[role['name']] = role['faction']
    logger.debug(f"Role factions loaded: {factions}")
    return factions

# Initialize global variables
available_roles = load_available_roles()
role_descriptions = load_role_descriptions()
role_templates, pending_templates = load_role_templates()
role_factions = load_role_factions()
