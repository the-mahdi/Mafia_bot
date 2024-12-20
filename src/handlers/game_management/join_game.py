from telegram.ext import ContextTypes
import logging
from src.db import conn, cursor

logger = logging.getLogger("Mafia Bot GameManagement.JoinGame")

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