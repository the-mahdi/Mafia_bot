import json
from utils import resource_path
import logging

logger = logging.getLogger("Mafia Bot Roles")

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

# Initialize global variables in roles.py (or a separate initializer module)
from roles.loader import load_available_roles, load_role_descriptions, load_role_factions
from roles.templates import load_role_templates

available_roles = load_available_roles()
role_descriptions = load_role_descriptions()
role_templates, pending_templates = load_role_templates()
role_factions = load_role_factions()