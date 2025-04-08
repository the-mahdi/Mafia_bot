import sqlite3
from telegram.ext import ContextTypes
import logging
import uuid
from src.db import conn, cursor
from src.roles import available_roles
from telegram.helpers import escape_markdown
from src.utils import clear_user_data

logger = logging.getLogger("Mafia Bot GameManagement.CreateGame")

async def create_game(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.debug("Creating a new game.")
    user_id = update.effective_user.id
    
    # Clear user data but keep username before creating a new game
    clear_user_data(context)
    
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
            safe_message = escape_markdown(message, version=2)
            await context.bot.send_message(chat_id=update.effective_chat.id, text=safe_message, parse_mode='MarkdownV2')
            # Escape the passcode message as well
            safe_passcode = escape_markdown(passcode, version=2)
            await context.bot.send_message(chat_id=update.effective_chat.id, text=safe_passcode, parse_mode='MarkdownV2')
            return  # Exit the loop if game creation is successful
        except sqlite3.IntegrityError:
            logger.error(f"Failed to create game due to game_id collision. Attempt {attempts + 1}/{max_attempts}")
            attempts += 1

    # If the loop completes without creating a game
    logger.error("Failed to create game after multiple attempts.")
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Failed to create game. Please try again.")
