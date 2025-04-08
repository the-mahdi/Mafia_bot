import json
from src.utils.path import resource_path
import logging
import os

logger = logging.getLogger("Mafia Bot Roles")

def load_roles():
    """Load the complete roles dictionary from roles.json."""
    try:
        with open(resource_path(os.path.join('data', 'roles.json')), 'r') as file:
            data = json.load(file)
            roles = data.get('roles', {})
            logger.debug(f"Loaded roles: {list(roles.keys())}")
            return roles
    except FileNotFoundError:
        logger.error("roles.json not found.")
        return {}
    except json.JSONDecodeError:
        logger.error("Invalid JSON format in roles.json.")
        return {}

def load_role_templates():
    """Load role templates and pending templates from role_templates.json."""
    try:
        with open(resource_path(os.path.join('data', 'role_templates.json')), 'r') as file:
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
    """Save role templates and pending templates to role_templates.json."""
    with open(resource_path(os.path.join('data', 'role_templates.json')), 'w') as file:
        json.dump({'templates': templates, 'pending_templates': pending_templates}, file, indent=2)
        logger.debug(f"Role templates saved: {templates}")
        logger.debug(f"Pending templates saved: {pending_templates}")

# Initialize global variables
roles = load_roles()
available_roles = list(roles.keys())
role_descriptions = {role: roles[role]['description'] for role in roles}
role_factions = {role: roles[role]['faction'] for role in roles}
role_actions = {role: roles[role]['actions'] for role in roles}
role_templates, pending_templates = load_role_templates()