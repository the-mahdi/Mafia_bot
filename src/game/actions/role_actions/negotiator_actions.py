"""
Handles negotiation logic for Mozakere (Mafia Negotiator) role
"""
import random
from src.database.action_queries import (
    record_complex_action, 
    add_action_target,
    get_pending_complex_actions,
    mark_complex_action_resolved
)
from src.database.user_queries import update_player_faction

async def handle_negotiation(game_id: int, negotiator_id: int, target_id: int):
    """
    Processes a negotiation attempt between the Mafia Negotiator and a Town member
    """
    # Record the complex negotiation action
    action_id = record_complex_action(
        game_id=game_id,
        role="Mozakere",
        action_command="negotiate",
        initiator_id=negotiator_id,
        phase="night",
        status="pending"
    )
    
    # Add the negotiation target
    add_action_target(action_id, target_id)
    
    return {
        "success": True,
        "message": f"Negotiation attempt with player {target_id} recorded",
        "action_id": action_id
    }

async def resolve_negotiations(game_id: int):
    """
    Resolves all pending negotiations at the end of the night phase
    """
    pending_actions = get_pending_complex_actions(game_id, "negotiate")
    
    results = []
    for action in pending_actions:
        target_id = action["targets"][0]
        
        # Implement actual negotiation logic with 30% success rate
        success = random.random() < 0.3
        
        if success:
            update_player_faction(target_id, "Mafia")
            message = f"Player {target_id} successfully recruited to Mafia"
        else:
            message = f"Negotiation with player {target_id} failed"
        
        mark_complex_action_resolved(action["action_id"])
        
        results.append({
            "negotiator_id": action["initiator_id"],
            "target_id": target_id,
            "success": success,
            "message": message
        })
    
    return results