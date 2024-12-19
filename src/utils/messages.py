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