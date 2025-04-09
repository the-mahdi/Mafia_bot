import logging
from typing import List, Dict, Any
from src.database.action_queries import (
    record_complex_action,
    add_action_target,
    get_pending_complex_actions,
    mark_complex_action_resolved,
    set_role_state,
    get_role_state
)
from src.database.game_queries import get_game_players
from src.game.roles.role_manager import get_role_data

logger = logging.getLogger(__name__)

async def handle_gun_distribution(game_id: int, gunsmith_id: int) -> None:
    """Handle the initial gun distribution phase during day phase."""
    try:
        # Create complex action to track gun distribution
        action_id = record_complex_action(
            game_id=game_id,
            actor_id=gunsmith_id,
            action_type="gun_distribution",
            phase="day",
            status="pending"
        )
        
        # Store gunsmith's remaining guns in role state
        role_data = get_role_data("Gunsmith")
        max_guns = role_data.get("metadata", {}).get("max_guns", 3)
        set_role_state(game_id, gunsmith_id, "guns_remaining", max_guns)
        
        logger.info(f"Initialized gun distribution for gunsmith {gunsmith_id} in game {game_id}")

    except Exception as e:
        logger.error(f"Error initializing gun distribution: {str(e)}")
        raise

async def process_gun_shot(game_id: int, gunsmith_id: int) -> None:
    """Process gun shot actions during night phase."""
    try:
        pending_actions = get_pending_complex_actions(game_id, "gun_shot")
        
        for action in pending_actions:
            targets = action.get("targets", [])
            if len(targets) != 1:
                logger.warning(f"Invalid gun shot action {action['id']} - expected 1 target")
                continue
                
            target_id = targets[0]
            # Mark player as shot (will be processed in phase manager)
            set_role_state(game_id, target_id, "shot", True)
            
            # Deduct gun from gunsmith's inventory
            guns_remaining = get_role_state(game_id, gunsmith_id, "guns_remaining") or 0
            set_role_state(game_id, gunsmith_id, "guns_remaining", max(0, guns_remaining - 1))
            
            mark_complex_action_resolved(action["id"])
            logger.info(f"Processed gun shot from {gunsmith_id} to {target_id}")

    except Exception as e:
        logger.error(f"Error processing gun shots: {str(e)}")
        raise

async def resolve_gunsmith_actions(game_id: int) -> None:
    """Resolve all pending gunsmith-related actions."""
    try:
        # Check for pending distributions
        distributions = get_pending_complex_actions(game_id, "gun_distribution")
        for action in distributions:
            # Implementation would handle actual gun distribution logic
            mark_complex_action_resolved(action["id"])
            
        # Process any gun shots
        await process_gun_shot(game_id, action["actor_id"])

    except Exception as e:
        logger.error(f"Error resolving gunsmith actions: {str(e)}")
        raise