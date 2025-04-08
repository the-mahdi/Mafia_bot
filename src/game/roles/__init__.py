"""
Role management and related functionality.
This package provides access to role data and related operations.
"""

from src.game.roles.role_manager import (
    get_role_manager,
    available_roles,
    role_descriptions,
    role_factions,
    role_actions,
    role_templates,
    pending_templates,
    save_role_templates
)

# Exposed to maintain compatibility with existing imports
__all__ = [
    'get_role_manager',
    'available_roles',
    'role_descriptions',
    'role_factions',
    'role_actions', 
    'role_templates',
    'pending_templates',
    'save_role_templates'
]