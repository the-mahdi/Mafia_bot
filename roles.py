import json
from utils import resource_path
import logging

logger = logging.getLogger("Mafia Bot Roles")

def load_available_roles():
    with open(resource_path('list_roles.txt'), 'r') as file:
        available_roles = [line.strip() for line in file if line.strip()]
    logger.debug(f"Available roles loaded: {available_roles}")
    return available_roles

def read_role_descriptions():
    descriptions = {}
    with open(resource_path('role_descriptions.txt'), 'r') as file:
        for line in file:
            if ':' in line:
                role, description = line.strip().split(':', 1)
                descriptions[role.strip()] = description.strip()
    return descriptions

def load_role_templates():
    try:
        with open(resource_path('role_templates.json'), 'r') as file:
            templates = json.load(file).get('templates', {})
        logger.debug(f"Role templates loaded: {templates}")
        return templates
    except FileNotFoundError:
        logger.warning("role_templates.json not found. Creating a new one.")
        return {}
    except json.JSONDecodeError:
        logger.error("Invalid JSON format in role_templates.json. Starting with an empty template.")
        return {}

def save_role_templates(templates):
    with open(resource_path('role_templates.json'), 'w') as file:
        json.dump({'templates': templates}, file, indent=2)
    logger.debug(f"Role templates saved: {templates}")

available_roles = load_available_roles()
role_descriptions = read_role_descriptions()

# Ensure every available role has a description
for role in available_roles:
    if role not in role_descriptions:
        role_descriptions[role] = "No description available for this role."

role_templates = load_role_templates()
