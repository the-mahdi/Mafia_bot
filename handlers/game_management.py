import sqlite3
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import logging
import uuid
import asyncio
import random
import aiohttp
from db import conn, cursor
from roles import available_roles, role_descriptions, role_templates, role_factions
from utils import resource_path, generate_voting_summary  
from config import RANDOM_ORG_API_KEY
import json

logger = logging.getLogger("Mafia Bot GameManagement")

# Initialize an asyncio lock for synchronization
role_counts_lock = asyncio.Lock()

# Number of roles per page
ROLES_PER_PAGE = 27

async def get_random_shuffle(lst: list, api_key: str) -> list:
    """
    Shuffles a list using Random.org's generateIntegerSequences API. Returns the shuffled list if successful,
    otherwise returns a locally shuffled list.
    """
    if not lst:
        return lst.copy()

    payload = {
        "jsonrpc": "2.0",
        "method": "generateIntegerSequences",
        "params": {
            "apiKey": api_key,
            "n": 1,  # Number of sequences
            "length": len(lst),  # Length of each sequence
            "min": 1,  # Minimum integer
            "max": len(lst),  # Maximum integer
            "replacement": False  # No replacement to ensure a permutation
        },
        "id": 1
    }

    headers = {'Content-Type': 'application/json'}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post('https://api.random.org/json-rpc/4/invoke', json=payload, headers=headers, timeout=10) as resp:
                if resp.status != 200:
                    logger.error(f"Random.org API returned non-200 status code: {resp.status}")
                    return random.sample(lst, len(lst))  # Fallback to local shuffle
                data = await resp.json()
                if 'result' in data and 'random' in data['result'] and 'data' in data['result']['random']:
                    shuffle_sequence = data['result']['random']['data'][0]  # First (and only) sequence
                    # Validate the shuffle_sequence
                    if sorted(shuffle_sequence) != list(range(1, len(lst) + 1)):
                        logger.error("Invalid shuffle sequence received from Random.org.")
                        return random.sample(lst, len(lst))  # Fallback to local shuffle
                    # Convert to 0-based indices
                    shuffled_list = [lst[i - 1] for i in shuffle_sequence]
                    return shuffled_list
                else:
                    logger.error(f"Unexpected response format from Random.org: {data}")
                    return random.sample(lst, len(lst))  # Fallback to local shuffle
    except Exception as e:
        logger.error(f"Exception while fetching shuffle from Random.org: {e}")
        return random.sample(lst, len(lst))  # Fallback to local shuffle

def get_player_count(game_id: int) -> int:
    cursor.execute("SELECT COUNT(*) FROM Roles WHERE game_id = ?", (game_id,))
    count = cursor.fetchone()[0]
    logger.debug(f"Game ID {game_id} has {count} players.")
    return count

def get_templates_for_player_count(player_count: int) -> list:
    templates = role_templates.get(str(player_count), [])
    logger.debug(f"Templates for player count {player_count}: {templates}")
    return templates

async def show_role_buttons(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, message_id=None) -> int:
    logger.debug("Displaying role buttons.")
    game_id = context.user_data.get('game_id')
    if not game_id:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No game selected.")
        return

    async with role_counts_lock:
        cursor.execute("SELECT role, count FROM GameRoles WHERE game_id = ?", (game_id,))
        role_counts = {role: count for role, count in cursor.fetchall()}

    # Ensure all available roles are present
    for role in available_roles:
        if role not in role_counts:
            role_counts[role] = 0

    # Get the current page from user_data, default to 0
    current_page = context.user_data.get('current_page', 0)

    start_index = current_page * ROLES_PER_PAGE
    end_index = start_index + ROLES_PER_PAGE
    roles_on_page = available_roles[start_index:end_index]

    keyboard = []
    for role in roles_on_page:
        keyboard.append([
            InlineKeyboardButton("-", callback_data=f"decrease_{role}"),
            InlineKeyboardButton(f"{role} ({role_counts[role]})", callback_data=f"role_{role}"),
            InlineKeyboardButton("+", callback_data=f"increase_{role}")
        ])

    # Navigation buttons
    nav_buttons = []
    if current_page > 0:
        nav_buttons.append(InlineKeyboardButton("Previous", callback_data="prev_page"))
    if end_index < len(available_roles):
        nav_buttons.append(InlineKeyboardButton("Next", callback_data="next_page"))
    if nav_buttons:
        keyboard.append(nav_buttons)

    # Add Reset, Confirm, and Save Template buttons
    keyboard.append([
        InlineKeyboardButton("Confirm Roles and Save as Template", callback_data="confirm_roles_and_save_template")
    ])
    keyboard.append([
        InlineKeyboardButton("Reset Roles", callback_data="reset_roles"),
        InlineKeyboardButton("Confirm Roles", callback_data="confirm_roles"),
        InlineKeyboardButton("Back to Menu", callback_data="back_to_menu")
    ])
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "Select roles and their counts:"

    if message_id:
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=message_id,
            text=text,
            reply_markup=reply_markup
        )
        return message_id  # Return the same message_id if editing
    else:
        sent_message = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            reply_markup=reply_markup
        )
        return sent_message.message_id  # Return the new message_id

async def confirm_and_set_roles(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: int) -> (bool, str):
    logger.debug("Confirming and setting roles.")
    cursor.execute("SELECT user_id FROM Roles WHERE game_id = ?", (game_id,))
    users = [r[0] for r in cursor.fetchall()]
    logger.debug(f"Users in game ID {game_id}: {users}")

    if not users:
        logger.debug("No users found in the game.")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No players in the game.")
        return False, "No players"

    async with role_counts_lock:
        cursor.execute("SELECT role, count FROM GameRoles WHERE game_id = ?", (game_id,))
        role_counts = {role: count for role, count in cursor.fetchall()}

    total_roles = sum(role_counts.values())
    total_players = len(users)

    if total_roles != total_players:
        logger.debug(f"Number of roles does not match number of players: {total_players} users, {total_roles} roles.")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Number of roles does not match number of players.\n{len(users)} users, {sum(role_counts.values())} roles."
        )
        return False, "Mismatch in roles and players"

    # Assign roles fairly
    user_roles = []
    for role, count in role_counts.items():
        user_roles.extend([role] * count)
    logger.debug(f"Role assignments: {user_roles}")

    # Attempt to shuffle using Random.org
    method_used = "fallback (local random)"
    if RANDOM_ORG_API_KEY:
        shuffled_user_roles = await get_random_shuffle(user_roles, RANDOM_ORG_API_KEY)
        if shuffled_user_roles:
            user_roles = shuffled_user_roles
            method_used = "Random.org"
            logger.debug("Shuffled roles using Random.org")
        else:
            logger.warning("Failed to shuffle roles using Random.org. Falling back to local random.")

    else:
        random.shuffle(user_roles)
        logger.debug("Shuffled roles using local random.")

    # Shuffle users to randomize role assignments
    if RANDOM_ORG_API_KEY and method_used == "Random.org":
        shuffled_users = await get_random_shuffle(users, RANDOM_ORG_API_KEY)
        if shuffled_users:
            users = shuffled_users
            logger.debug("Shuffled users using Random.org")
        else:
            logger.warning("Failed to shuffle users using Random.org. Falling back to local random.")
            random.shuffle(users)
            method_used = "fallback (local random)"
    else:
        random.shuffle(users)
        logger.debug("Shuffled users using local random.")

    # Assign roles to users
    try:
        cursor.execute("BEGIN TRANSACTION")
        for user, role in zip(users, user_roles):
            cursor.execute(
                "UPDATE Roles SET role = ? WHERE game_id = ? AND user_id = ?",
                (role, game_id, user)
            )
            logger.debug(f"Role {role} set for user ID {user}")
        # Update the randomness_method in Games table
        cursor.execute(
            "UPDATE Games SET randomness_method = ? WHERE game_id = ?",
            (method_used, game_id)
        )
        conn.commit()
        logger.debug(f"Roles set for game ID {game_id} using {method_used}")
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to set roles due to error: {e}")
        return False, method_used

    # -------------------- Send the roles, their count, and descriptions to all players --------------------

    # Fetch role counts excluding roles with count 0
    cursor.execute("SELECT role, count FROM GameRoles WHERE game_id = ? AND count > 0", (game_id,))
    role_counts = cursor.fetchall()

    # Count total number of players
    total_players = len(users)

    # Prepare the summary message
    summary_message = f"📢 **Game Summary** 📢\n\n" \
                      f"**Total Players:** {total_players}\n\n" \
                      f"**Roles in the Game:**\n"

    for role, count in role_counts:
        description = role_descriptions.get(role, "No description available.")
        summary_message += f"- **{role}** ({count}): {description}\n\n"

    # Send the summary message to all players
    cursor.execute("""
        SELECT Roles.user_id, Users.username
        FROM Roles
        JOIN Users ON Roles.user_id = Users.user_id
        WHERE Roles.game_id = ?
    """, (game_id,))
    player_roles = cursor.fetchall()
    for user_id, username in player_roles:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=summary_message,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Failed to send game summary to user {user_id}: {e}")
            try:
                await context.bot.send_message(
                    chat_id=update.effective_user.id,
                    text=f"Failed to send game summary to user {username} (ID: {user_id}). Please check their privacy settings."
                )
            except Exception as ex:
                logger.error(f"Failed to notify moderator about summary message for user {user_id}: {ex}")

    return True, method_used

async def create_game(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.debug("Creating a new game.")
    user_id = update.effective_user.id
    max_attempts = 10  # Set a maximum number of attempts to prevent infinite loops
    attempts = 0

    while attempts < max_attempts:
        # Generate a secure UUID-based passcode
        passcode = str(uuid.uuid4())
        logger.debug(f"Generated passcode: {passcode}")

        # Generate a unique game_id using UUID
        game_id = str(uuid.uuid4())
        logger.debug(f"Generated game_id: {game_id}")

        try:
            cursor.execute("INSERT INTO Games (game_id, passcode, moderator_id) VALUES (?, ?, ?)", (game_id, passcode, user_id))
            # Initialize GameRoles with zero counts for all roles
            for role in available_roles:
                cursor.execute(
                    "INSERT INTO GameRoles (game_id, role, count) VALUES (?, ?, 0)",
                    (game_id, role)
                )
            conn.commit()
            logger.debug(f"Game created with game_id: {game_id}, passcode: {passcode}, moderator_id: {user_id}")
            context.user_data['game_id'] = game_id  # Store game_id in user_data
            logger.debug(f"Game created. game_id stored in user_data: {game_id}")

            message = f"Game created successfully!\nPasscode: {passcode}\nShare this passcode with players to join."
            await context.bot.send_message(chat_id=update.effective_chat.id, text=message)
            # Send the passcode without other text to make the copy-paste easier
            await context.bot.send_message(chat_id=update.effective_chat.id, text=passcode)
            return  # Exit the loop if game creation is successful
        except sqlite3.IntegrityError:
            logger.error(f"Failed to create game due to game_id collision. Attempt {attempts + 1}/{max_attempts}")
            attempts += 1

    # If the loop completes without creating a game
    logger.error("Failed to create game after multiple attempts.")
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Failed to create game. Please try again.")

async def join_game(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, passcode: str) -> None:
    logger.debug("User attempting to join a game.")
    user_id = update.effective_user.id
    username = context.user_data.get("username", f"User{user_id}")

    cursor.execute("SELECT game_id, moderator_id, started FROM Games WHERE passcode = ?", (passcode,))
    result = cursor.fetchone()
    if result:
        game_id, moderator_id, started = result

        if started:
            logger.debug(f"Attempt to join started game_id: {game_id}")
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Cannot join. The game has already started.")
            return  # Exit the function to prevent joining

        context.user_data['game_id'] = game_id  # Store game_id in user_data
        logger.debug(f"User joined game. game_id stored in user_data: {game_id}")

        # Update or insert user information
        cursor.execute("""
        INSERT INTO Users (user_id, username, last_updated)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id) DO UPDATE SET
        username = ?,
        last_updated = CURRENT_TIMESTAMP
        WHERE username != ? OR last_updated < CURRENT_TIMESTAMP
        """, (user_id, username, username, username))

        cursor.execute("""
        INSERT OR IGNORE INTO Roles (game_id, user_id, role)
        VALUES (?, ?, NULL)
        """, (game_id, user_id))

        conn.commit()
        message = "Joined the game successfully!"
        await context.bot.send_message(chat_id=update.effective_chat.id, text=message)
        logger.debug(f"User {username} (ID: {user_id}) joined game {game_id}")

        # Notify moderator
        if moderator_id != user_id:
            try:
                await context.bot.send_message(chat_id=moderator_id, text=f"User {username} (ID: {user_id}) has joined the game!")
            except Exception as e:
                logger.error(f"Failed to notify moderator {moderator_id}: {e}")
    else:
        message = "Invalid passcode. Please try again."
        await context.bot.send_message(chat_id=update.effective_chat.id, text=message)


async def start_game(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.debug("Starting the game.")
    user_id = update.effective_user.id

    # Retrieve game_id from context.user_data
    game_id = context.user_data.get('game_id')

    if not game_id:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Game not found.")
        return

    cursor.execute("SELECT moderator_id, started, randomness_method FROM Games WHERE game_id = ?", (game_id,))
    result = cursor.fetchone()
    if not result:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Game not found.")
        return
    moderator_id, started, randomness_method = result

    if user_id != moderator_id:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="You are not authorized to start this game.")
        return

    if started:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="The game has already started.")
        return

    cursor.execute("""
        SELECT Roles.user_id, Roles.role, Users.username
        FROM Roles
        JOIN Users ON Roles.user_id = Users.user_id
        WHERE Roles.game_id = ?
    """, (game_id,))
    player_roles = cursor.fetchall()
    logger.debug(f"Player roles: {player_roles}")

    if not player_roles or any(role is None or role == '' for _, role, _ in player_roles):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Cannot start the game. Roles have not been assigned to all players."
        )
        return

    role_message = "Game started! Here are the assigned roles:\n"

    # Determine the randomness methodology based on the stored randomness_method
    if randomness_method == "Random.org":
        methodology_description = (
            "Randomness Methodology: Random.org API\n\n"
            "This game used the Random.org API to generate truly random numbers for role assignment. "
            "Random.org uses atmospheric noise to produce high-quality random numbers, which are "
            "considered more random than those generated by pseudo-random number algorithms typically "
            "used in computer programs. This method ensures a fair and unbiased distribution of roles. "
            "The same methodology is being used in national lotteries, sports events, and other scenarios, "
            "concerning billions of dollars at stake.\n\n"
            "If you think this is not fair, write your complaint on a paper, put it in a bottle, and throw it into the ocean. "
            "If I find it, I will consider it. I promise!"
        )
        randomness_method = "Random.org"
    else:
        methodology_description = (
            "Randomness Methodology: Python's random module\n\n"
            "There was a problem with the Random.org API, so this game used Python's built-in random module for role assignment. "
            "This module uses the Mersenne Twister algorithm, a pseudo-random number generator. While not truly random, "
            "it provides high-quality randomness suitable for most applications, including game role "
            "assignment. The seed for this generator is derived from the system time, ensuring "
            "different results each time the program runs. "
            "This method is more than enough for a game of Mafia."
        )
        randomness_method = "Python's random module"

    # Notify each player of their role and the randomness methodology
    for user_id, role, username in player_roles:
        if role:
            role_description = role_descriptions.get(role, "No description available.")
            role_faction = role_factions.get(role, "Unknown Faction")
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"Hi {username}, your role is: {role} ({role_faction})\n\nRole Description:\n{role_description}\n\n{methodology_description}"
                )
                role_message += f"{username} (ID: {user_id}): {role}\n"
            except Exception as e:
                logger.error(f"Failed to send role to user {user_id}: {e}")
                try:
                    await context.bot.send_message(
                        chat_id=moderator_id,
                        text=f"Failed to send role to user {username} (ID: {user_id}). Please check their privacy settings."
                    )
                except Exception as ex:
                    logger.error(f"Failed to notify moderator about summary message for user {user_id}: {ex}")
        else:
            await context.bot.send_message(
                chat_id=user_id,
                text="Error: No role assigned. Please contact the game moderator."
            )

    # Send roles summary and randomness methodology to moderator
    await context.bot.send_message(
        chat_id=moderator_id,
        text=f"{role_message}"
    )

    # Mark the game as started
    cursor.execute("UPDATE Games SET started = 1 WHERE game_id = ?", (game_id,))
    conn.commit()
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"The game has started! Roles, descriptions, and randomness methodology have been sent to all players. Method used: {randomness_method}"
    )
    logger.debug(f"Game {game_id} started using {randomness_method}")

async def set_roles(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.debug("Setting roles.")
    # This function can be expanded if additional functionality is needed
    await show_role_buttons(update, context)

async def start_latest_game(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.debug("Starting the latest game created by the moderator.")
    user_id = update.effective_user.id

    # Retrieve the latest game created by the moderator that hasn't been started yet
    cursor.execute("""
        SELECT game_id, started, randomness_method
        FROM Games
        WHERE moderator_id = ?
        ORDER BY rowid DESC
        LIMIT 1
    """, (user_id,))
    result = cursor.fetchone()

    if not result:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="You have not created any games.")
        return

    game_id, started, randomness_method = result

    if started:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="The latest game you created has already started.")
        return

    # Store game_id in context.user_data
    context.user_data['game_id'] = game_id

    # ------------------- Commented Out Section -------------------
    # Previously, confirm_and_set_roles was called here, which sends the game summary.
    # Since roles should be confirmed manually, we remove this call.

    # success, method = await confirm_and_set_roles(update, context, game_id)
    # if not success:
    #     await context.bot.send_message(chat_id=update.effective_chat.id, text="Error setting roles. Please try again.")
    # else:
    #     await start_game(update, context)  # Call start_game without passcode
    #     await context.bot.send_message(
    #         chat_id=update.effective_chat.id,
    #         text=f"The game has started successfully!\nRandomness source: {method}."
    #     )
    # -------------------------------------------------------------

    # Instead, directly start the game assuming roles have already been set
    await start_game(update, context)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="The game has started successfully!"
    )
    logger.debug(f"Game {game_id} started successfully.")


# Initialize a dictionary to store voting data for each game
game_voting_data = {}

async def announce_voting(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.debug("Announcing Voting.")
    user_id = update.effective_user.id
    game_id = context.user_data.get('game_id')
    logger.debug(f"Announcing voting for game_id: {game_id}")

    if not game_id:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No game selected.")
        return

    # Check if the user is the moderator
    cursor.execute("SELECT moderator_id FROM Games WHERE game_id = ?", (game_id,))
    result = cursor.fetchone()
    if not result or result[0] != user_id:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="You are not authorized to announce voting.")
        return

    # Fetch active (non-eliminated) players in the game
    cursor.execute("""
    SELECT Roles.user_id, Users.username
    FROM Roles
    JOIN Users ON Roles.user_id = Users.user_id
    WHERE Roles.game_id = ? AND Roles.eliminated = 0
    """, (game_id,))
    players = cursor.fetchall()
    player_ids = [player[0] for player in players]
    player_names = {user_id: username for user_id, username in players}

    # Initialize voting data with 'anonymous' flag set to False
    game_voting_data[game_id] = {
        'votes': {},  # Will store individual votes for each voter
        'voters': set(player_ids),  # Initialize voters as the set of active player IDs
        'player_ids': player_ids,
        'player_names': player_names,  # Store player names
        'summary_message_id': None,  # Initialize summary message ID
        'anonymous': False  # Flag to indicate anonymous voting
    }

    # Send voting message to each player
    for player_id, player_username in players:
        keyboard = []
        for target_id, target_username in players:
            button_text = f"{target_username} ❌"  # Voting button
            callback_data = f"vote_{target_id}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

        keyboard.append([InlineKeyboardButton("Confirm Votes", callback_data=f"confirm_votes")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await context.bot.send_message(
                chat_id=player_id,
                text=f"📢 **Voting Session:**\nVote for a player to eliminate:",
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Failed to send voting message to user {player_id}: {e}")

    # Send initial voting summary to the moderator
    await send_voting_summary(context, game_id)

async def announce_anonymous_voting(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.debug("Announcing Anonymous Voting.")
    user_id = update.effective_user.id
    game_id = context.user_data.get('game_id')
    logger.debug(f"Announcing anonymous voting for game_id: {game_id}")

    if not game_id:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No game selected.")
        return

    # Check if the user is the moderator
    cursor.execute("SELECT moderator_id FROM Games WHERE game_id = ?", (game_id,))
    result = cursor.fetchone()
    if not result or result[0] != user_id:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="You are not authorized to announce anonymous voting.")
        return

    # Fetch active (non-eliminated) players in the game
    cursor.execute("""
    SELECT Roles.user_id, Users.username
    FROM Roles
    JOIN Users ON Roles.user_id = Users.user_id
    WHERE Roles.game_id = ? AND Roles.eliminated = 0
    """, (game_id,))
    players = cursor.fetchall()
    player_ids = [player[0] for player in players]
    player_names = {user_id: username for user_id, username in players}

    # Initialize voting data with 'anonymous' flag set to True
    game_voting_data[game_id] = {
        'votes': {},  # Will store individual votes for each voter
        'voters': set(player_ids),  # Initialize voters as the set of active player IDs
        'player_ids': player_ids,
        'player_names': player_names,  # Store player names
        'summary_message_id': None,  # Initialize summary message ID
        'anonymous': True  # Flag to indicate anonymous voting
    }

    # Send voting message to each player
    for player_id, player_username in players:
        keyboard = []
        for target_id, target_username in players:
            button_text = f"{target_username} ❌"  # Voting button
            callback_data = f"vote_{target_id}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

        keyboard.append([InlineKeyboardButton("Confirm Votes", callback_data=f"confirm_votes")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await context.bot.send_message(
                chat_id=player_id,
                text=f"📢 **Anonymous Voting Session:**\nVote for a player to eliminate:",
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Failed to send voting message to user {player_id}: {e}")

    # Send initial voting summary to the moderator
    await send_voting_summary(context, game_id)


async def send_voting_summary(context: ContextTypes.DEFAULT_TYPE, game_id: str) -> None:
    """Sends or updates the voting summary message to the moderator."""
    logger.debug(f"Sending voting summary for game ID {game_id}.")

    if game_id not in game_voting_data:
        logger.error(f"Game ID {game_id} not found in voting data.")
        return

    # Fetch moderator ID
    cursor.execute("SELECT moderator_id FROM Games WHERE game_id = ?", (game_id,))
    result = cursor.fetchone()
    if not result:
        logger.error(f"Game ID {game_id} not found when fetching moderator.")
        return
    moderator_id = result[0]

    voted_players = [
        game_voting_data[game_id]['player_names'][voter_id]
        for voter_id in game_voting_data[game_id]['player_ids']
        if voter_id not in game_voting_data[game_id]['voters']
    ]
    not_voted_players = [
        game_voting_data[game_id]['player_names'][voter_id]
        for voter_id in game_voting_data[game_id]['voters']
    ]

    summary_message = generate_voting_summary(voted_players, not_voted_players)

    # Check if a summary message already exists for this game
    if game_voting_data[game_id]['summary_message_id']:
        try:
            # Edit the existing message
            await context.bot.edit_message_text(
                chat_id=moderator_id,
                message_id=game_voting_data[game_id]['summary_message_id'],
                text=summary_message,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Failed to edit voting summary message: {e}")
            # Optionally, send a new message if editing fails
            message = await context.bot.send_message(
                chat_id=moderator_id,
                text=summary_message,
                parse_mode='Markdown'
            )
            game_voting_data[game_id]['summary_message_id'] = message.message_id
    else:
        # Send a new message
        message = await context.bot.send_message(
            chat_id=moderator_id,
            text=summary_message,
            parse_mode='Markdown'
        )
        game_voting_data[game_id]['summary_message_id'] = message.message_id

async def handle_vote(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str, target_id: int) -> None:
    logger.debug("Handling vote.")
    voter_id = update.effective_user.id
    query = update.callback_query

    if game_id not in game_voting_data:
        await context.bot.send_message(chat_id=voter_id, text="Voting session not found.")
        return

    if voter_id not in game_voting_data[game_id]['voters']:
        await context.bot.send_message(chat_id=voter_id, text="You have already confirmed your votes.")
        return

    # Initialize voter's votes if not already present
    if voter_id not in game_voting_data[game_id]['votes']:
        game_voting_data[game_id]['votes'][voter_id] = []

    # Toggle vote
    if target_id in game_voting_data[game_id]['votes'][voter_id]:
        game_voting_data[game_id]['votes'][voter_id].remove(target_id)
    else:
        game_voting_data[game_id]['votes'][voter_id].append(target_id)

    # Update the button text
    keyboard = []
    cursor.execute("""
    SELECT Roles.user_id, Users.username
    FROM Roles
    JOIN Users ON Roles.user_id = Users.user_id
    WHERE Roles.game_id = ? AND Roles.eliminated = 0
    """, (game_id,))
    players = cursor.fetchall()

    for target_id_loop, target_username in players:
        # Check if the voter has voted for this target
        if target_id_loop in game_voting_data[game_id]['votes'][voter_id]:
            button_text = f"{target_username} ✅"  # Indicate vote with checkmark
        else:
            button_text = f"{target_username} ❌"  # Indicate no vote
        callback_data = f"vote_{target_id_loop}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

    keyboard.append([InlineKeyboardButton("Confirm Votes", callback_data=f"confirm_votes")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_reply_markup(reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Failed to edit message: {e}")

async def confirm_votes(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str) -> None:
    logger.debug("Confirming votes.")
    voter_id = update.effective_user.id
    query = update.callback_query

    if game_id not in game_voting_data:
        await context.bot.send_message(chat_id=voter_id, text="Voting session not found.")
        return

    if voter_id not in game_voting_data[game_id]['voters']:
        await context.bot.send_message(chat_id=voter_id, text="You have already confirmed your votes.")
        return

    # Prepare confirmation message
    voter_votes = game_voting_data[game_id]['votes'].get(voter_id, [])
    player_names = game_voting_data[game_id]['player_names']
    if voter_votes:
        voted_for_names = [player_names.get(target_id, f"User {target_id}") for target_id in voter_votes]
        confirmation_message = f"You are voting for: {', '.join(voted_for_names)}.\nAre you sure?"
    else:
        confirmation_message = "You have not cast any votes. Are you sure?"

    # Add Final Confirm and Cancel buttons
    keyboard = [
        [InlineKeyboardButton("Final Confirm", callback_data=f"final_confirm_vote_{game_id}")],
        [InlineKeyboardButton("Cancel", callback_data=f"cancel_vote_{game_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Send confirmation message
    await query.edit_message_text(text=confirmation_message, reply_markup=reply_markup)


async def final_confirm_vote(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.debug("Final vote confirmation.")
    voter_id = update.effective_user.id
    query = update.callback_query
    data_parts = query.data.split("_")
    game_id = data_parts[3]

    if game_id not in game_voting_data:
        await context.bot.send_message(chat_id=voter_id, text="Voting session not found.")
        return

    # Check if the voter is part of the game
    if voter_id not in game_voting_data[game_id]['player_ids']:
        await context.bot.send_message(chat_id=voter_id, text="You are not part of this game.")
        return
    
    if voter_id not in game_voting_data[game_id]['voters']:
        await context.bot.send_message(chat_id=voter_id, text="You have already confirmed your votes.")
        return

    # Remove voter from the set of active voters
    game_voting_data[game_id]['voters'].remove(voter_id)

    await query.edit_message_text(text="Your votes have been finally confirmed.")

    # Update the voting summary for the moderator
    await send_voting_summary(context, game_id)

    # Check if all players have voted
    if not game_voting_data[game_id]['voters']:
        await process_voting_results(update, context, game_id)

async def cancel_vote(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.debug("Cancelling vote.")
    voter_id = update.effective_user.id
    query = update.callback_query
    data_parts = query.data.split("_")
    game_id = data_parts[2]  # Extract game_id from callback_data

    if game_id not in game_voting_data:
        await context.bot.send_message(chat_id=voter_id, text="Voting session not found.")
        return

    # Reset the voter's votes
    game_voting_data[game_id]['votes'][voter_id] = []

    # Rebuild the voting buttons
    keyboard = []
    cursor.execute("""
    SELECT Roles.user_id, Users.username
    FROM Roles
    JOIN Users ON Roles.user_id = Users.user_id
    WHERE Roles.game_id = ? AND Roles.eliminated = 0
    """, (game_id,))
    players = cursor.fetchall()

    for target_id_loop, target_username in players:
        button_text = f"{target_username} ❌"  # Reset to default "Nay"
        callback_data = f"vote_{target_id_loop}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

    keyboard.append([InlineKeyboardButton("Confirm Votes", callback_data=f"confirm_votes")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Send the updated voting message
    await query.edit_message_text(text="Vote cancelled. Please recast your votes.", reply_markup=reply_markup)


async def process_voting_results(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str) -> None:
    logger.debug("Processing voting results.")
    if game_id not in game_voting_data:
        logger.error(f"Game ID {game_id} not found in voting data.")
        return

    # Fetch active (non-eliminated) player names
    cursor.execute("""
    SELECT Roles.user_id, Users.username
    FROM Roles
    JOIN Users ON Roles.user_id = Users.user_id
    WHERE Roles.game_id = ? AND Roles.eliminated = 0
    """, (game_id,))
    players = cursor.fetchall()
    player_names = {user_id: username for user_id, username in players}

    # Count votes
    vote_counts = {}
    for voter_id, votes in game_voting_data[game_id]['votes'].items():
        for voted_id in votes:
            vote_counts[voted_id] = vote_counts.get(voted_id, 0) + 1

    # Sort results
    sorted_results = sorted(vote_counts.items(), key=lambda item: item[1], reverse=True)

    # Prepare the summary message
    summary_message = "🔍 **Voting Results (Summary):**\n\n"
    if sorted_results:
        for voted_id, count in sorted_results:
            summary_message += f"• **{player_names.get(voted_id, 'Unknown')}**: {count} vote(s)\n"
    else:
        summary_message += "No votes were cast."

    # Fetch moderator ID
    cursor.execute("SELECT moderator_id FROM Games WHERE game_id = ?", (game_id,))
    result = cursor.fetchone()
    if not result:
        logger.error(f"Game ID {game_id} not found when fetching moderator.")
        return
    moderator_id = result[0]

    # Send the summary message to all players
    for player_id in game_voting_data[game_id]['player_ids']:
        try:
            await context.bot.send_message(chat_id=player_id, text=summary_message, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Failed to send summary message to user {player_id}: {e}")

    # Send the summary message to the moderator
    try:
        await context.bot.send_message(chat_id=moderator_id, text=summary_message, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Failed to send voting summary to moderator {moderator_id}: {e}")

    # Generate detailed voting report
    detailed_report = "🗳️ **Detailed Voting Report:**\n\n"
    for voter_id, votes in game_voting_data[game_id]['votes'].items():
        voter_name = player_names.get(voter_id, f"User {voter_id}")
        if votes:
            voted_names = [player_names.get(target_id, f"User {target_id}") for target_id in votes]
            voted_str = ", ".join(voted_names)
            detailed_report += f"• **{voter_name}** voted for: {voted_str}\n"
        else:
            detailed_report += f"• **{voter_name}** did not vote.\n"

    # Check if the voting was anonymous
    anonymous = game_voting_data[game_id].get('anonymous', False)

    if anonymous:
        # Send detailed report only to the moderator
        try:
            await context.bot.send_message(chat_id=moderator_id, text=detailed_report, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Failed to send detailed voting report to moderator {moderator_id}: {e}")
    else:
        # Send the detailed report to all players
        for player_id in game_voting_data[game_id]['player_ids']:
            try:
                await context.bot.send_message(chat_id=player_id, text=detailed_report, parse_mode='Markdown')
            except Exception as e:
                logger.error(f"Failed to send detailed voting report to user {player_id}: {e}")
                # Notify the moderator about the failure
                try:
                    await context.bot.send_message(
                        chat_id=moderator_id,
                        text=f"⚠️ Failed to send detailed voting report to user {player_id}."
                    )
                except Exception as ex:
                    logger.error(f"Failed to notify moderator about failed message to user {player_id}: {ex}")

        # Send the detailed report to the moderator
        try:
            await context.bot.send_message(chat_id=moderator_id, text=detailed_report, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Failed to send detailed voting report to moderator {moderator_id}: {e}")

    # Clean up voting data for the game
    del game_voting_data[game_id]
    logger.debug(f"Voting data for game ID {game_id} has been cleared.")

async def eliminate_player(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str) -> None:
    logger.debug("Initiating player elimination process.")
    
    # Fetch active (non-eliminated) players
    cursor.execute("""
        SELECT Roles.user_id, Users.username
        FROM Roles
        JOIN Users ON Roles.user_id = Users.user_id
        WHERE Roles.game_id = ? AND Roles.eliminated = 0
    """, (game_id,))
    players = cursor.fetchall()
    
    if not players:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No active players to eliminate.")
        return
    
    # Create elimination buttons for each player
    keyboard = []
    for user_id, username in players:
        keyboard.append([InlineKeyboardButton(username, callback_data=f"eliminate_confirm_{user_id}")])
    
    # Add a back button
    keyboard.append([InlineKeyboardButton("Back to Manage Games", callback_data="manage_games")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Select a player to eliminate:", reply_markup=reply_markup)

async def handle_elimination_confirmation(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str, target_user_id: int) -> None:
    logger.debug(f"Handling elimination confirmation for user ID {target_user_id} in game ID {game_id}.")
    
    # Fetch the username of the target user
    cursor.execute("SELECT username FROM Users WHERE user_id = ?", (target_user_id,))
    result = cursor.fetchone()
    if not result:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="User not found.")
        return
    username = result[0]
    
    # Ask for confirmation
    keyboard = [
        [InlineKeyboardButton("Yes, Eliminate", callback_data=f"eliminate_yes_{target_user_id}")],
        [InlineKeyboardButton("Cancel", callback_data=f"eliminate_cancel_{target_user_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Are you sure you want to eliminate {username}?", reply_markup=reply_markup)

async def confirm_elimination(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str, target_user_id: int) -> None:
    logger.debug(f"Confirming elimination for user ID {target_user_id} in game ID {game_id}.")
    
    # Mark the player as eliminated in the database
    cursor.execute("""
        UPDATE Roles
        SET eliminated = 1
        WHERE game_id = ? AND user_id = ?
    """, (game_id, target_user_id))
    conn.commit()
    
    # Fetch the username of the eliminated player
    cursor.execute("SELECT username FROM Users WHERE user_id = ?", (target_user_id,))
    result = cursor.fetchone()
    username = result[0] if result else "Unknown"
    
    # Notify the moderator
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"{username} has been eliminated from the game.")
    
    # Notify the eliminated player
    try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text="You have been eliminated from the game. Better luck next time!"
        )
    except Exception as e:
        logger.error(f"Failed to notify user {target_user_id} about elimination: {e}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Failed to notify {username} about their elimination.")

    # Remove the eliminated player from any ongoing voting session
    if game_id in game_voting_data:
        if target_user_id in game_voting_data[game_id]['voters']:
            game_voting_data[game_id]['voters'].remove(target_user_id)
        if target_user_id in game_voting_data[game_id]['player_votes']:
            del game_voting_data[game_id]['player_votes'][target_user_id]
        # Optionally, re-check if all voters have voted after removal
        if not game_voting_data[game_id]['voters']:
            await process_voting_results(update, context, game_id)

async def cancel_elimination(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: str, target_user_id: int) -> None:
    logger.debug(f"Elimination of user ID {target_user_id} in game ID {game_id} has been canceled.")
    
    # Fetch the username of the target user
    cursor.execute("SELECT username FROM Users WHERE user_id = ?", (target_user_id,))
    result = cursor.fetchone()
    username = result[0] if result else "Unknown"
    
    # Notify the moderator
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Elimination of {username} has been canceled.")
