"""
Role-specific action handlers for the Mafia game.
"""

from src.game.actions.role_actions.doctor_actions import handle_heal_action
from src.game.actions.role_actions.cowboy_actions import handle_cowboy_shot

__all__ = [
    'handle_heal_action',
    'handle_cowboy_shot',
]