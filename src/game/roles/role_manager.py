import json
import logging
import os
from src.utils.path import resource_path

logger = logging.getLogger("Mafia Bot Roles")

class RoleManager:
    """
    Class to manage role data, including loading and providing access to 
    role descriptions, factions, actions, and templates.
    """
    _instance = None

    def __new__(cls):
        """Singleton pattern to ensure only one instance exists"""
        if cls._instance is None:
            cls._instance = super(RoleManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the RoleManager if not already initialized"""
        if not self._initialized:
            self._roles = self._load_roles()
            self._available_roles = list(self._roles.keys())
            self._role_descriptions = {role: self._roles[role]['description'] for role in self._roles}
            self._role_factions = {role: self._roles[role]['faction'] for role in self._roles}
            self._role_actions = {role: self._roles[role]['actions'] for role in self._roles}
            self._role_templates, self._pending_templates = self._load_role_templates()
            self._initialized = True

    def _load_roles(self):
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

    def _load_role_templates(self):
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

    def save_role_templates(self, templates=None, pending_templates=None):
        """Save role templates and pending templates to role_templates.json."""
        if templates is not None:
            self._role_templates = templates
        if pending_templates is not None:
            self._pending_templates = pending_templates
            
        with open(resource_path(os.path.join('data', 'role_templates.json')), 'w') as file:
            json.dump({
                'templates': self._role_templates, 
                'pending_templates': self._pending_templates
            }, file, indent=2)
            logger.debug(f"Role templates saved: {self._role_templates}")
            logger.debug(f"Pending templates saved: {self._pending_templates}")

    # Accessor methods to replace the global variables
    def get_all_roles(self):
        """Get the complete roles dictionary."""
        return self._roles
    
    def get_available_roles(self):
        """Get the list of available role names."""
        return self._available_roles
    
    def get_role_descriptions(self):
        """Get the dictionary of role descriptions."""
        return self._role_descriptions
    
    def get_role_description(self, role_name):
        """Get the description for a specific role."""
        return self._role_descriptions.get(role_name, "No description available")
    
    def get_role_factions(self):
        """Get the dictionary of role factions."""
        return self._role_factions
    
    def get_role_faction(self, role_name):
        """Get the faction for a specific role."""
        return self._role_factions.get(role_name, "Unknown")
    
    def get_role_actions(self):
        """Get the dictionary of role actions."""
        return self._role_actions
    
    def get_role_action(self, role_name):
        """Get the actions for a specific role."""
        return self._role_actions.get(role_name, {})
    
    def get_role_templates(self):
        """Get the dictionary of role templates."""
        return self._role_templates
    
    def get_pending_templates(self):
        """Get the dictionary of pending templates."""
        return self._pending_templates
    
    def get_role_data(self, role_name):
        """Get the complete data for a specific role."""
        return self._roles.get(role_name, {})

    # Enhanced methods for action handling
    def get_role_actions_by_phase(self, role_name, phase):
        """Get a role's actions for a specific phase (night/day/trigger).
        
        Args:
            role_name (str): The name of the role
            phase (str): The phase ('night', 'day', 'trigger')
            
        Returns:
            list: List of action dictionaries for the specified role and phase
        """
        role_actions = self.get_role_action(role_name)
        return role_actions.get(phase, [])
    
    def get_action_priority(self, role_name, action_command):
        """Get the priority for a specific role's action.
        
        Args:
            role_name (str): The name of the role
            action_command (str): The action command to find the priority for
            
        Returns:
            int: The priority value (higher numbers execute first) or 0 if not found
        """
        role_actions = self.get_role_action(role_name)
        # Search in all phases for the action command
        for phase in role_actions:
            for action in role_actions[phase]:
                if action.get('command') == action_command:
                    return action.get('priority', 0)
        return 0
    
    def get_interactive_actions(self, role_name, phase):
        """Get all interactive actions for a role in a specific phase.
        
        Args:
            role_name (str): The name of the role
            phase (str): The phase ('night', 'day', 'trigger')
            
        Returns:
            list: List of interactive action dictionaries
        """
        phase_actions = self.get_role_actions_by_phase(role_name, phase)
        return [action for action in phase_actions if action.get('interactive') == 'button']
    
    def get_passive_actions(self, role_name, phase):
        """Get all passive (non-interactive) actions for a role in a specific phase.
        
        Args:
            role_name (str): The name of the role
            phase (str): The phase ('night', 'day', 'trigger')
            
        Returns:
            list: List of passive action dictionaries
        """
        phase_actions = self.get_role_actions_by_phase(role_name, phase)
        return [action for action in phase_actions if action.get('interactive') == 'none']
    
    def get_action_by_command(self, role_name, action_command):
        """Get the complete action data for a specific command.
        
        Args:
            role_name (str): The name of the role
            action_command (str): The action command to find
            
        Returns:
            dict: The action data or empty dict if not found
        """
        role_actions = self.get_role_action(role_name)
        for phase in role_actions:
            for action in role_actions[phase]:
                if action.get('command') == action_command:
                    return action
        return {}
    
    def get_action_targets(self, role_name, action_command):
        """Get the number of targets for a specific action.
        
        Args:
            role_name (str): The name of the role
            action_command (str): The action command
            
        Returns:
            int/str: Number of targets or 'multiple' if variable
        """
        action = self.get_action_by_command(role_name, action_command)
        return action.get('targets', 0)
    
    def can_target_self(self, role_name, action_command):
        """Check if an action can target the player themselves.
        
        Args:
            role_name (str): The name of the role
            action_command (str): The action command
            
        Returns:
            bool: True if the action can target self, False otherwise
        """
        action = self.get_action_by_command(role_name, action_command)
        return action.get('self_target', False)
    
    def get_win_condition(self, role_name):
        """Get the win condition for a role.
        
        Args:
            role_name (str): The name of the role
            
        Returns:
            str: The win condition type or 'faction' if not specified
        """
        role_data = self.get_role_data(role_name)
        return role_data.get('win_condition', 'faction')

# Create module-level convenience functions that use the singleton instance
# This maintains compatibility with the old import pattern

def get_role_manager():
    """Get the singleton RoleManager instance."""
    return RoleManager()

# Compatibility functions to make migration easier
def available_roles():
    """Get the list of available role names."""
    return get_role_manager().get_available_roles()

def role_descriptions():
    """Get the dictionary of role descriptions."""
    return get_role_manager().get_role_descriptions()

def role_factions():
    """Get the dictionary of role factions."""
    return get_role_manager().get_role_factions()

def role_actions():
    """Get the dictionary of role actions."""
    return get_role_manager().get_role_actions()

def role_templates():
    """Get the dictionary of role templates."""
    return get_role_manager().get_role_templates()

def pending_templates():
    """Get the dictionary of pending templates."""
    return get_role_manager().get_pending_templates()

def save_role_templates(templates=None, pending_templates=None):
    """Save role templates and pending templates to role_templates.json."""
    get_role_manager().save_role_templates(templates, pending_templates)

# Enhanced compatibility functions for the new methods
def get_role_actions_by_phase(role_name, phase):
    """Get a role's actions for a specific phase (night/day/trigger)."""
    return get_role_manager().get_role_actions_by_phase(role_name, phase)

def get_action_priority(role_name, action_command):
    """Get the priority for a specific role's action."""
    return get_role_manager().get_action_priority(role_name, action_command)

def get_interactive_actions(role_name, phase):
    """Get all interactive actions for a role in a specific phase."""
    return get_role_manager().get_interactive_actions(role_name, phase)

def get_passive_actions(role_name, phase):
    """Get all passive actions for a role in a specific phase."""
    return get_role_manager().get_passive_actions(role_name, phase)

def get_action_by_command(role_name, action_command):
    """Get the complete action data for a specific command."""
    return get_role_manager().get_action_by_command(role_name, action_command)

def get_action_targets(role_name, action_command):
    """Get the number of targets for a specific action."""
    return get_role_manager().get_action_targets(role_name, action_command)

def can_target_self(role_name, action_command):
    """Check if an action can target the player themselves."""
    return get_role_manager().can_target_self(role_name, action_command)

def get_win_condition(role_name):
    """Get the win condition for a role."""
    return get_role_manager().get_win_condition(role_name)

# Initialize the manager on module import
_manager = get_role_manager()