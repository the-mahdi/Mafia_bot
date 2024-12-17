# handlers/game_management.py
import sqlite3
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import logging
import uuid
import asyncio
import random
import aiohttp
from db import conn, cursor
from roles import available_roles, role_descriptions, role_templates
from utils import resource_path
from config import RANDOM_ORG_API_KEY
import json

logger = logging.getLogger("Mafia Bot GameManagement")

# Initialize an asyncio lock for synchronization
role_counts_lock = asyncio.Lock()

async def get_random_shuffle(lst: list, api_key: str) -> list:
    """
    Shuffles a list using Random.org's generateIntegerSequences API. Returns the shuffled list if successful,
    otherwise returns None.
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
                    return None
                data = await resp.json()
                if 'result' in data and 'random' in data['result'] and 'data' in data['result']['random']:
                    shuffle_sequence = data['result']['random']['data'][0]  # First (and only) sequence
                    # Validate the shuffle_sequence
                    if sorted(shuffle_sequence) != list(range(1, len(lst) + 1)):
                        logger.error("Invalid shuffle sequence received from Random.org.")
                        return None
                    # Convert to 0-based indices
                    shuffled_list = [lst[i - 1] for i in shuffle_sequence]
                    return shuffled_list
                else:
                    logger.error(f"Unexpected response format from Random.org: {data}")
                    return None
    except Exception as e:
        logger.error(f"Exception while fetching shuffle from Random.org: {e}")
        return None

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

    keyboard = []
    for role in available_roles:
        keyboard.append([
            InlineKeyboardButton("−", callback_data=f"decrease_{role}"),
            InlineKeyboardButton(f"{role} ({role_counts[role]})", callback_data=f"role_{role}"),
            InlineKeyboardButton("+", callback_data=f"increase_{role}")
        ])
    # Add Reset and Back buttons
    keyboard.append([InlineKeyboardButton("Reset Roles", callback_data="reset_roles")])
    keyboard.append([
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
        logger.debug(f"Role {role} assigned {count} times")

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

    # Shuffle users using Random.org if possible
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
    summary_message = f"📊 **Game Summary** 📊\n\n" \
                      f"**Total Players:** {total_players}\n\n" \
                      f"**Roles in the Game:**\n"

    for role, count in role_counts:
        description = role_descriptions.get(role, "No description available.")
        summary_message += f"- **{role}** ({count}): {description}\n"

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

    # --------------------- Send the roles, their count, and descriptions to all players ---------------------
    return True, method_used

async def create_game(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.debug("Creating a new game.")
    user_id = update.effective_user.id

    # Generate a secure UUID-based passcode
    passcode = str(uuid.uuid4())
    logger.debug(f"Generated passcode: {passcode}")

    try:
        cursor.execute("INSERT INTO Games (passcode, moderator_id) VALUES (?, ?)", (passcode, user_id))
        game_id = cursor.lastrowid
        # Initialize GameRoles with zero counts for all roles
        for role in available_roles:
            cursor.execute(
                "INSERT INTO GameRoles (game_id, role, count) VALUES (?, ?, 0)",
                (game_id, role)
            )
        conn.commit()
        logger.debug(f"Game created with game_id: {game_id}, passcode: {passcode}, moderator_id: {user_id}")
        context.user_data['game_id'] = game_id  # Store game_id in user_data

        message = f"Game created successfully!\nPasscode: {passcode}\nShare this passcode with players to join."
        await context.bot.send_message(chat_id=update.effective_chat.id, text=message)
        # Send the passcode without other text to make the copy-paste easier
        await context.bot.send_message(chat_id=update.effective_chat.id, text=passcode)
    except sqlite3.IntegrityError:
        logger.error("Failed to create game due to passcode collision.")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Failed to create game. Please try again.")

async def join_game(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, passcode: str) -> None:
    logger.debug("User attempting to join a game.")
    user_id = update.effective_user.id
    username = context.user_data.get("username", f"User{user_id}")

    cursor.execute("SELECT game_id, moderator_id FROM Games WHERE passcode = ?", (passcode,))
    result = cursor.fetchone()
    if result:
        game_id, moderator_id = result
        context.user_data['game_id'] = game_id  # Store game_id in user_data

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

async def start_game(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, passcode: str) -> None:
    logger.debug("Starting the game.")
    user_id = update.effective_user.id

    cursor.execute("SELECT game_id, moderator_id, started, randomness_method FROM Games WHERE passcode = ?", (passcode,))
    result = cursor.fetchone()
    if not result:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Game not found with the provided passcode.")
        return
    game_id, moderator_id, started, randomness_method = result

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

    # Fetch moderator ID
    cursor.execute("SELECT moderator_id FROM Games WHERE game_id = ?", (game_id,))
    moderator_id = cursor.fetchone()[0]

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
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"Hi {username}, your role is: {role}\n\nRole Description:\n{role_description}\n\n{methodology_description}"
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
                    logger.error(f"Failed to notify moderator about user {user_id}: {ex}")
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
