import sys
import os

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def clear_user_data(context, keep_username=True):
    """
    Clears user data stored in context.user_data to prevent stale state.
    
    :param context: The context object containing user_data
    :param keep_username: Whether to keep the username in user_data (default: True)
    """
    # Store username if we want to keep it
    username = context.user_data.get("username") if keep_username else None
    
    # Clear all user data
    context.user_data.clear()
    
    # Restore username if needed
    if keep_username and username:
        context.user_data["username"] = username

def generate_voting_summary(voted_players, not_voted_players):
    """
    Generates a formatted voting summary message with emojis.

    :param voted_players: List of player names who have voted.
    :param not_voted_players: List of player names who have not voted.
    :return: Formatted string with voting summary.
    """
    voted_section = "🗳️ **Players Who Have Voted:**\n"
    if voted_players:
        voted_section += "\n".join([f"• {player}" for player in voted_players])
    else:
        voted_section += "• None"

    not_voted_section = "\n\n⏳ **Players Who Have Not Voted:**\n"
    if not_voted_players:
        not_voted_section += "\n".join([f"• {player}" for player in not_voted_players])
    else:
        not_voted_section += "• None"

    voting_summary = f"🎉 **Current Voting Session** 🎉\n\n{voted_section}{not_voted_section}"
    return voting_summary