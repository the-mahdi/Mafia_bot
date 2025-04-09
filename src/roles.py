import json
from src.utils.path import resource_path
import logging
import os

logger = logging.getLogger("Mafia Bot Roles")

def load_roles():
    """Load the complete roles dictionary from the split JSON files in data/roles_split."""
    roles = {}
    roles_dir = resource_path(os.path.join('data', 'roles_split'))
    
    try:
        # Check if the roles_split directory exists
        if not os.path.isdir(roles_dir):
            logger.error(f"Directory {roles_dir} not found.")
            return {}
            
        # List all JSON files in the roles_split directory
        json_files = [f for f in os.listdir(roles_dir) if f.endswith('.json')]
        
        if not json_files:
            logger.error(f"No JSON files found in {roles_dir}.")
            return {}
            
        # Load roles from each JSON file and merge them
        for json_file in json_files:
            file_path = os.path.join(roles_dir, json_file)
            try:
                with open(file_path, 'r') as file:
                    data = json.load(file)
                    file_roles = data.get('roles', {})
                    roles.update(file_roles)
                    logger.debug(f"Loaded roles from {json_file}: {list(file_roles.keys())}")
            except (FileNotFoundError, json.JSONDecodeError) as e:
                logger.error(f"Error loading {json_file}: {e}")
        
        logger.info(f"Loaded a total of {len(roles)} roles from {len(json_files)} files.")
        return roles
        
    except Exception as e:
        logger.error(f"Unexpected error loading roles: {e}")
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