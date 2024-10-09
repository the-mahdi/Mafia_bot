import sqlite3
import uuid
import asyncio
import random
import aiohttp
import json
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
import logging

# Create a logger for your application
logger = logging.getLogger("Mafia Bot")
logger.setLevel(logging.DEBUG)

# Set up basic configuration for the logger
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Read the API tokens from token.txt
with open('token.txt', 'r') as file:
    lines = [line.strip() for line in file.readlines()]
    if len(lines) < 2:
        logger.error("token.txt must contain at least two lines: Telegram token and Random.org API key.")
        exit(1)
    TOKEN = lines[0]
    RANDOM_ORG_API_KEY = lines[1]

# Connect to the SQLite database with WAL mode for better concurrency
conn = sqlite3.connect('mafia_game.db', check_same_thread=False)
conn.execute("PRAGMA journal_mode=WAL;")
cursor = conn.cursor()

# Create tables for Users, Games, Roles, and GameRoles
cursor.execute('''
    CREATE TABLE IF NOT EXISTS Users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS Games (
        game_id INTEGER PRIMARY KEY AUTOINCREMENT,
        passcode TEXT UNIQUE,
        moderator_id INTEGER,
        started INTEGER DEFAULT 0,
        randomness_method TEXT DEFAULT 'fallback (local random)',
        FOREIGN KEY (moderator_id) REFERENCES Users(user_id)
    )
''')


cursor.execute('''
    CREATE TABLE IF NOT EXISTS Roles (
        game_id INTEGER,
        user_id INTEGER,
        role TEXT,
        FOREIGN KEY (game_id) REFERENCES Games(game_id),
        FOREIGN KEY (user_id) REFERENCES Users(user_id),
        PRIMARY KEY (game_id, user_id)
    )
''')


cursor.execute('''
    CREATE TABLE IF NOT EXISTS GameRoles (
        game_id INTEGER,
        role TEXT,
        count INTEGER,
        FOREIGN KEY (game_id) REFERENCES Games(game_id),
        PRIMARY KEY (game_id, role)
    )
''')

conn.commit()

# Ensure randomness_method column exists
cursor.execute("""
    PRAGMA table_info(Games)
""")
columns = [info[1] for info in cursor.fetchall()]
if 'randomness_method' not in columns:
    cursor.execute("ALTER TABLE Games ADD COLUMN randomness_method TEXT DEFAULT 'fallback (local random)'")
    conn.commit()

# Initialize an asyncio lock for synchronization
role_counts_lock = asyncio.Lock()

# Read the available roles from list_roles.txt
with open('list_roles.txt', 'r') as file:
    available_roles = [line.strip() for line in file if line.strip()]
logger.debug(f"Available roles: {available_roles}")

def read_role_descriptions():
    descriptions = {}
    with open('role_descriptions.txt', 'r') as file:
        for line in file:
            if ':' in line:
                role, description = line.strip().split(':', 1)
                descriptions[role.strip()] = description.strip()
    return descriptions

role_descriptions = read_role_descriptions()

# Ensure every available role has a description
for role in available_roles:
    if role not in role_descriptions:
        role_descriptions[role] = "No description available for this role."

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

async def start(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.debug("In async def start")
    keyboard = [
        [InlineKeyboardButton("Create Game", callback_data="create_game")],
        [InlineKeyboardButton("Join Game", callback_data="join_game")],
        [InlineKeyboardButton("Set Roles", callback_data="set_roles")],
        [InlineKeyboardButton("Start Game", callback_data="start_game")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = "Welcome to the Mafia Game Bot!"
    await context.bot.send_message(chat_id=update.effective_chat.id, text=message, reply_markup=reply_markup)

async def show_role_buttons(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, message_id=None) -> int:
    logger.debug("In async def show_role_buttons")
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
    logger.debug("In async def confirm_and_set_roles")
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
        return True, method_used
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to set roles due to error: {e}")
        return False, method_used


async def button_handler(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.debug("In async def button_handler")
    query = update.callback_query
    await query.answer()
    data = query.data
    message_id = query.message.message_id
    user_id = update.effective_user.id

    # Retrieve game_id from user_data
    game_id = context.user_data.get('game_id')

    if data == "back_to_menu":
        logger.debug("back_to_menu button pressed")
        await start(update, context)  # Return to the main menu

    elif data == "reset_roles":
        logger.debug("reset_roles button pressed")
        if not game_id:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="No game selected.")
            return
        async with role_counts_lock:
            cursor.execute("DELETE FROM GameRoles WHERE game_id = ?", (game_id,))
            # Initialize role counts to 0 for all roles
            for role in available_roles:
                cursor.execute(
                    "INSERT INTO GameRoles (game_id, role, count) VALUES (?, ?, 0) ON CONFLICT(game_id, role) DO UPDATE SET count=0",
                    (game_id, role)
                )
            conn.commit()
        await show_role_buttons(update, context, message_id)

    elif data == "create_game":
        logger.debug("create_game button pressed")
        await create_game(update, context)

    elif data == "join_game":
        logger.debug("join_game button pressed")
        context.user_data["action"] = "awaiting_name"
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Please enter your name.")

    elif data == "set_roles":
        logger.debug("set_roles button pressed")
        if not game_id:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="No game selected.")
            return
        # Check if the user is the moderator
        cursor.execute("SELECT moderator_id FROM Games WHERE game_id = ?", (game_id,))
        result = cursor.fetchone()
        if not result or result[0] != user_id:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="You are not authorized to set roles.")
            return
        context.user_data["action"] = "set_roles"
        await show_role_buttons(update, context)

    elif data == "start_game":
        logger.debug("start_game button pressed")
        if not game_id:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="No game selected.")
            return
        # Check if the user is the moderator
        cursor.execute("SELECT moderator_id FROM Games WHERE game_id = ?", (game_id,))
        result = cursor.fetchone()
        if not result or result[0] != user_id:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="You are not authorized to start the game.")
            return
        context.user_data["action"] = "start_game"
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Please enter the passcode to start the game.")

    # Handle increase role count
    elif data.startswith("increase_"):
        logger.debug(f"{data} button pressed")
        role = data.split("_", 1)[1]
        if role not in available_roles:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Invalid role.")
            return
        if not game_id:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="No game selected.")
            return
        async with role_counts_lock:
            cursor.execute(
                "INSERT INTO GameRoles (game_id, role, count) VALUES (?, ?, 0) ON CONFLICT(game_id, role) DO UPDATE SET count = count + 1",
                (game_id, role)
            )
            conn.commit()
        await show_role_buttons(update, context, message_id)

    # Handle decrease role count
    elif data.startswith("decrease_"):
        logger.debug(f"{data} button pressed")
        role = data.split("_", 1)[1]
        if role not in available_roles:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Invalid role.")
            return
        if not game_id:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="No game selected.")
            return
        async with role_counts_lock:
            cursor.execute("SELECT count FROM GameRoles WHERE game_id = ? AND role = ?", (game_id, role))
            result = cursor.fetchone()
            current_count = result[0] if result else 0
            if current_count > 0:
                cursor.execute(
                    "UPDATE GameRoles SET count = count - 1 WHERE game_id = ? AND role = ?",
                    (game_id, role)
                )
                logger.debug(f"Role count for {role} decreased to {current_count - 1}")
            else:
                logger.debug(f"Role count for {role} is already 0. Cannot decrease further.")
            conn.commit()
        await show_role_buttons(update, context, message_id)

    # Handle confirm roles action
    elif data == "confirm_roles":
        logger.debug("confirm_roles button pressed")
        if not game_id:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="No game selected.")
            return
        success, method = await confirm_and_set_roles(update, context, game_id)
        if not success:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Error setting roles. Please try again.")
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Roles have been confirmed and set successfully!\nRandomness source: {method}."
            )

    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Unknown action.")

async def passcode_handler(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.debug("In async def passcode_handler")
    user_input = update.message.text.strip()
    action = context.user_data.get("action")

    if action == "awaiting_name":
        context.user_data["username"] = user_input
        context.user_data["action"] = "join_game"  # Now expecting a passcode
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Please enter the passcode to join the game.")
    elif action == "join_game":
        await join_game(update, context, user_input)  # Pass user_input as the passcode
    elif action == "set_roles":
        # In the revised flow, roles are set via buttons, so passcode is not needed here
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Please use the role buttons to set roles.")
    elif action == "start_game":
        await start_game(update, context, user_input)
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Unknown action. Please use /start to begin.")

async def create_game(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.debug("In async def create_game")
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
    logger.debug("In async def join_game")
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
    logger.debug("In async def start_game")
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
            "The same methodology is being used in national lotteries, sports events, and other scenarios,"
            "concerning billions of dollars at stake.\n\n"
            "If you think this is not fair, write your complaint on a paper, put it in a bottle, and throw it into the ocean. "
            "If I find it, I will consider it. I promise!"
        )
    else:
        methodology_description = (
            "Randomness Methodology: Python's random module\n\n"
            "There was a problem with the Random.org API, so this game used Python's built-in random module for role assignment."
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
    logger.debug("In async def set_roles")
    # This function can be expanded if additional functionality is needed
    await show_role_buttons(update, context)

def main():
    application = Application.builder().token(TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, passcode_handler))

    # Run the bot
    application.run_polling()

if __name__ == "__main__":
    main()
