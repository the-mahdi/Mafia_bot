"""
Database query functions for voting operations.
This module centralizes all database operations related to voting.
"""

import logging
from src.database.connection import conn, cursor

logger = logging.getLogger("Mafia Bot Database.VoteQueries")

# VotingSessions Table Operations

def delete_voting_session(game_id):
    """Delete any existing voting session for a game."""
    cursor.execute("DELETE FROM VotingSessions WHERE game_id = ?", (game_id,))
    conn.commit()

def create_voting_session(game_id, is_anonymous):
    """Create a new VotingSession record."""
    cursor.execute("""
    INSERT INTO VotingSessions (game_id, is_anonymous, summary_message_id, permissions_message_id)
    VALUES (?, ?, NULL, NULL)
    """, (game_id, 1 if is_anonymous else 0))
    conn.commit()

def update_voting_session_anonymous(game_id, is_anonymous):
    """Update the anonymous status of a voting session."""
    cursor.execute("""
    UPDATE VotingSessions SET is_anonymous = ? WHERE game_id = ?
    """, (1 if is_anonymous else 0, game_id))
    conn.commit()

def get_voting_session(game_id):
    """Get voting session info for a game."""
    cursor.execute("SELECT is_anonymous, summary_message_id, permissions_message_id FROM VotingSessions WHERE game_id = ?", (game_id,))
    return cursor.fetchone()

def update_summary_message_id(game_id, message_id):
    """Update the summary message ID for a voting session."""
    cursor.execute("""
    UPDATE VotingSessions SET summary_message_id = ? WHERE game_id = ?
    """, (message_id, game_id))
    conn.commit()

def update_permissions_message_id(game_id, message_id):
    """Update the permissions message ID for a voting session."""
    cursor.execute("""
    UPDATE VotingSessions SET permissions_message_id = ? WHERE game_id = ?
    """, (message_id, game_id))
    conn.commit()

# VoterPermissions Table Operations

def delete_voter_permissions(game_id):
    """Delete all voter permissions for a game."""
    cursor.execute("DELETE FROM VoterPermissions WHERE game_id = ?", (game_id,))
    conn.commit()

def initialize_voter_permissions(game_id, player_id):
    """Initialize voter permissions for a player."""
    cursor.execute("""
    INSERT INTO VoterPermissions (game_id, user_id, can_vote, can_be_voted, has_voted)
    VALUES (?, ?, 1, 1, 0)
    """, (game_id, player_id))
    conn.commit()

def get_voter_permissions(game_id, user_id):
    """Get a player's voting permissions."""
    cursor.execute("""
    SELECT can_vote, can_be_voted, has_voted FROM VoterPermissions 
    WHERE game_id = ? AND user_id = ?
    """, (game_id, user_id))
    return cursor.fetchone()

def get_all_voter_permissions(game_id):
    """Get all player permissions for a game with usernames."""
    cursor.execute("""
    SELECT VoterPermissions.user_id, Users.username, VoterPermissions.can_vote, VoterPermissions.can_be_voted
    FROM VoterPermissions
    JOIN Users ON VoterPermissions.user_id = Users.user_id
    WHERE VoterPermissions.game_id = ?
    """, (game_id,))
    return cursor.fetchall()

def update_voter_permission(game_id, user_id, can_vote=None, can_be_voted=None, has_voted=None):
    """Update a voter's permissions. Only updates fields that are not None."""
    if can_vote is not None:
        cursor.execute("""
        UPDATE VoterPermissions SET can_vote = ? 
        WHERE game_id = ? AND user_id = ?
        """, (can_vote, game_id, user_id))
    
    if can_be_voted is not None:
        cursor.execute("""
        UPDATE VoterPermissions SET can_be_voted = ? 
        WHERE game_id = ? AND user_id = ?
        """, (can_be_voted, game_id, user_id))
    
    if has_voted is not None:
        cursor.execute("""
        UPDATE VoterPermissions SET has_voted = ? 
        WHERE game_id = ? AND user_id = ?
        """, (has_voted, game_id, user_id))
    
    conn.commit()

def get_players_who_can_vote(game_id):
    """Get all players who can vote in a game."""
    cursor.execute("""
    SELECT VoterPermissions.user_id, Users.username
    FROM VoterPermissions
    JOIN Users ON VoterPermissions.user_id = Users.user_id
    WHERE VoterPermissions.game_id = ? AND VoterPermissions.can_vote = 1
    """, (game_id,))
    return cursor.fetchall()

def get_players_who_can_be_voted(game_id):
    """Get all players who can be voted in a game."""
    cursor.execute("""
    SELECT VoterPermissions.user_id, Users.username
    FROM VoterPermissions
    JOIN Users ON VoterPermissions.user_id = Users.user_id
    WHERE VoterPermissions.game_id = ? AND VoterPermissions.can_be_voted = 1
    """, (game_id,))
    return cursor.fetchall()

def get_voted_players(game_id):
    """Get players who have voted."""
    cursor.execute("""
    SELECT Users.username
    FROM VoterPermissions
    JOIN Users ON VoterPermissions.user_id = Users.user_id
    WHERE VoterPermissions.game_id = ? AND VoterPermissions.can_vote = 1 AND VoterPermissions.has_voted = 1
    """, (game_id,))
    return [row[0] for row in cursor.fetchall()]

def get_not_voted_players(game_id):
    """Get players who have not voted."""
    cursor.execute("""
    SELECT Users.username
    FROM VoterPermissions
    JOIN Users ON VoterPermissions.user_id = Users.user_id
    WHERE VoterPermissions.game_id = ? AND VoterPermissions.can_vote = 1 AND VoterPermissions.has_voted = 0
    """, (game_id,))
    return [row[0] for row in cursor.fetchall()]

def check_all_votes_cast(game_id):
    """Check if all players who can vote have voted."""
    cursor.execute("""
    SELECT COUNT(*) FROM VoterPermissions 
    WHERE game_id = ? AND can_vote = 1 AND has_voted = 0
    """, (game_id,))
    return cursor.fetchone()[0] == 0

# Votes Table Operations

def delete_votes(game_id, voter_id=None):
    """Delete votes for a game, optionally filtering by voter."""
    if voter_id is not None:
        cursor.execute("""
        DELETE FROM Votes WHERE game_id = ? AND voter_id = ?
        """, (game_id, voter_id))
    else:
        cursor.execute("DELETE FROM Votes WHERE game_id = ?", (game_id,))
    conn.commit()

def toggle_vote(game_id, voter_id, target_id):
    """Toggle a vote - if it exists delete it, otherwise add it."""
    # Check if the vote already exists
    cursor.execute("""
    SELECT 1 FROM Votes 
    WHERE game_id = ? AND voter_id = ? AND target_id = ?
    """, (game_id, voter_id, target_id))
    vote_exists = cursor.fetchone() is not None

    # Toggle vote
    if vote_exists:
        cursor.execute("""
        DELETE FROM Votes 
        WHERE game_id = ? AND voter_id = ? AND target_id = ?
        """, (game_id, voter_id, target_id))
    else:
        cursor.execute("""
        INSERT INTO Votes (game_id, voter_id, target_id)
        VALUES (?, ?, ?)
        """, (game_id, voter_id, target_id))
    conn.commit()
    return not vote_exists  # Return the new state (True if vote was added)

def get_player_votes(game_id, voter_id):
    """Get all votes from a specific player."""
    cursor.execute("""
    SELECT target_id FROM Votes 
    WHERE game_id = ? AND voter_id = ?
    """, (game_id, voter_id))
    return [row[0] for row in cursor.fetchall()]

def get_player_votes_with_names(game_id, voter_id):
    """Get all votes from a specific player with target names."""
    cursor.execute("""
    SELECT Votes.target_id, Users.username
    FROM Votes
    JOIN Users ON Votes.target_id = Users.user_id
    WHERE Votes.game_id = ? AND Votes.voter_id = ?
    """, (game_id, voter_id))
    return cursor.fetchall()

def get_vote_counts(game_id):
    """Get vote counts for each target."""
    cursor.execute("""
    SELECT target_id, COUNT(*) as vote_count 
    FROM Votes 
    WHERE game_id = ? 
    GROUP BY target_id
    ORDER BY vote_count DESC
    """, (game_id,))
    return cursor.fetchall()

def get_detailed_votes(game_id):
    """Get detailed voting information including voter and target names."""
    cursor.execute("""
    SELECT v.voter_id, v.target_id, u1.username as voter_name, u2.username as target_name
    FROM Votes v
    JOIN Users u1 ON v.voter_id = u1.user_id
    JOIN Users u2 ON v.target_id = u2.user_id
    WHERE v.game_id = ?
    """, (game_id,))
    return cursor.fetchall()

# Utility functions

def get_active_players(game_id):
    """Get all active (non-eliminated) players in a game."""
    cursor.execute("""
    SELECT Roles.user_id, Users.username
    FROM Roles
    JOIN Users ON Roles.user_id = Users.user_id
    WHERE Roles.game_id = ? AND Roles.eliminated = 0
    """, (game_id,))
    return cursor.fetchall()

def get_moderator_id(game_id):
    """Get the moderator ID for a game."""
    cursor.execute("SELECT moderator_id FROM Games WHERE game_id = ?", (game_id,))
    result = cursor.fetchone()
    return result[0] if result else None