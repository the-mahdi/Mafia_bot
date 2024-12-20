import sqlite3
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import logging
import uuid
import asyncio
import random
import aiohttp
from src.db import conn, cursor
from src.roles import available_roles, role_descriptions, role_templates, role_factions
from src.utils import resource_path, generate_voting_summary  
from src.config import RANDOM_ORG_API_KEY
import json
from src.handlers.game_management.base import get_random_shuffle, role_counts_lock, ROLES_PER_PAGE

logger = logging.getLogger("Mafia Bot GameManagement")


# async def show_role_buttons(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, message_id=None) -> int:
#     logger.debug("Displaying role buttons.")
#     game_id = context.user_data.get('game_id')
#     if not game_id:
#         await context.bot.send_message(chat_id=update.effective_chat.id, text="No game selected.")
#         return

#     async with role_counts_lock:
#         cursor.execute("SELECT role, count FROM GameRoles WHERE game_id = ?", (game_id,))
#         role_counts = {role: count for role, count in cursor.fetchall()}

#     # Ensure all available roles are present
#     for role in available_roles:
#         if role not in role_counts:
#             role_counts[role] = 0

#     # Get the current page from user_data, default to 0
#     current_page = context.user_data.get('current_page', 0)

#     start_index = current_page * ROLES_PER_PAGE
#     end_index = start_index + ROLES_PER_PAGE
#     roles_on_page = available_roles[start_index:end_index]

#     keyboard = []
#     for role in roles_on_page:
#         keyboard.append([
#             InlineKeyboardButton("-", callback_data=f"decrease_{role}"),
#             InlineKeyboardButton(f"{role} ({role_counts[role]})", callback_data=f"role_{role}"),
#             InlineKeyboardButton("+", callback_data=f"increase_{role}")
#         ])

#     # Navigation buttons
#     nav_buttons = []
#     if current_page > 0:
#         nav_buttons.append(InlineKeyboardButton("Previous", callback_data="prev_page"))
#     if end_index < len(available_roles):
#         nav_buttons.append(InlineKeyboardButton("Next", callback_data="next_page"))
#     if nav_buttons:
#         keyboard.append(nav_buttons)

#     # Add Reset, Confirm, and Save Template buttons
#     keyboard.append([
#         InlineKeyboardButton("Confirm Roles and Save as Template", callback_data="confirm_roles_and_save_template")
#     ])
#     keyboard.append([
#         InlineKeyboardButton("Reset Roles", callback_data="reset_roles"),
#         InlineKeyboardButton("Confirm Roles", callback_data="confirm_roles"),
#         InlineKeyboardButton("Back to Menu", callback_data="back_to_menu")
#     ])
#     reply_markup = InlineKeyboardMarkup(keyboard)
#     text = "Select roles and their counts:"

#     if message_id:
#         await context.bot.edit_message_text(
#             chat_id=update.effective_chat.id,
#             message_id=message_id,
#             text=text,
#             reply_markup=reply_markup
#         )
#         return message_id  # Return the same message_id if editing
#     else:
#         sent_message = await context.bot.send_message(
#             chat_id=update.effective_chat.id,
#             text=text,
#             reply_markup=reply_markup
#         )
#         return sent_message.message_id  # Return the new message_id

# async def confirm_and_set_roles(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, game_id: int) -> (bool, str):
#     logger.debug("Confirming and setting roles.")
#     cursor.execute("SELECT user_id FROM Roles WHERE game_id = ?", (game_id,))
#     users = [r[0] for r in cursor.fetchall()]
#     logger.debug(f"Users in game ID {game_id}: {users}")

#     if not users:
#         logger.debug("No users found in the game.")
#         await context.bot.send_message(chat_id=update.effective_chat.id, text="No players in the game.")
#         return False, "No players"

#     async with role_counts_lock:
#         cursor.execute("SELECT role, count FROM GameRoles WHERE game_id = ?", (game_id,))
#         role_counts = {role: count for role, count in cursor.fetchall()}

#     total_roles = sum(role_counts.values())
#     total_players = len(users)

#     if total_roles != total_players:
#         logger.debug(f"Number of roles does not match number of players: {total_players} users, {total_roles} roles.")
#         await context.bot.send_message(
#             chat_id=update.effective_chat.id,
#             text=f"Number of roles does not match number of players.\n{len(users)} users, {sum(role_counts.values())} roles."
#         )
#         return False, "Mismatch in roles and players"

#     # Assign roles fairly
#     user_roles = []
#     for role, count in role_counts.items():
#         user_roles.extend([role] * count)
#     logger.debug(f"Role assignments: {user_roles}")

#     # Attempt to shuffle using Random.org
#     method_used = "fallback (local random)"
#     if RANDOM_ORG_API_KEY:
#         shuffled_user_roles = await get_random_shuffle(user_roles, RANDOM_ORG_API_KEY)
#         if shuffled_user_roles:
#             user_roles = shuffled_user_roles
#             method_used = "Random.org"
#             logger.debug("Shuffled roles using Random.org")
#         else:
#             logger.warning("Failed to shuffle roles using Random.org. Falling back to local random.")

#     else:
#         random.shuffle(user_roles)
#         logger.debug("Shuffled roles using local random.")

#     # Shuffle users to randomize role assignments
#     if RANDOM_ORG_API_KEY and method_used == "Random.org":
#         shuffled_users = await get_random_shuffle(users, RANDOM_ORG_API_KEY)
#         if shuffled_users:
#             users = shuffled_users
#             logger.debug("Shuffled users using Random.org")
#         else:
#             logger.warning("Failed to shuffle users using Random.org. Falling back to local random.")
#             random.shuffle(users)
#             method_used = "fallback (local random)"
#     else:
#         random.shuffle(users)
#         logger.debug("Shuffled users using local random.")

#     # Assign roles to users
#     try:
#         cursor.execute("BEGIN TRANSACTION")
#         for user, role in zip(users, user_roles):
#             cursor.execute(
#                 "UPDATE Roles SET role = ? WHERE game_id = ? AND user_id = ?",
#                 (role, game_id, user)
#             )
#             logger.debug(f"Role {role} set for user ID {user}")
#         # Update the randomness_method in Games table
#         cursor.execute(
#             "UPDATE Games SET randomness_method = ? WHERE game_id = ?",
#             (method_used, game_id)
#         )
#         conn.commit()
#         logger.debug(f"Roles set for game ID {game_id} using {method_used}")
#     except Exception as e:
#         conn.rollback()
#         logger.error(f"Failed to set roles due to error: {e}")
#         return False, method_used

#     # -------------------- Send the roles, their count, and descriptions to all players --------------------

#     # Fetch role counts excluding roles with count 0
#     cursor.execute("SELECT role, count FROM GameRoles WHERE game_id = ? AND count > 0", (game_id,))
#     role_counts = cursor.fetchall()

#     # Count total number of players
#     total_players = len(users)

#     # Prepare the summary message
#     summary_message = f"📢 **Game Summary** 📢\n\n" \
#                       f"**Total Players:** {total_players}\n\n" \
#                       f"**Roles in the Game:**\n"

#     for role, count in role_counts:
#         description = role_descriptions.get(role, "No description available.")
#         summary_message += f"- **{role}** ({count}): {description}\n\n"

#     # Send the summary message to all players
#     cursor.execute("""
#         SELECT Roles.user_id, Users.username
#         FROM Roles
#         JOIN Users ON Roles.user_id = Users.user_id
#         WHERE Roles.game_id = ?
#     """, (game_id,))
#     player_roles = cursor.fetchall()
#     for user_id, username in player_roles:
#         try:
#             await context.bot.send_message(
#                 chat_id=user_id,
#                 text=summary_message,
#                 parse_mode='Markdown'
#             )
#         except Exception as e:
#             logger.error(f"Failed to send game summary to user {user_id}: {e}")
#             try:
#                 await context.bot.send_message(
#                     chat_id=update.effective_user.id,
#                     text=f"Failed to send game summary to user {username} (ID: {user_id}). Please check their privacy settings."
#                 )
#             except Exception as ex:
#                 logger.error(f"Failed to notify moderator about summary message for user {user_id}: {ex}")

#     return True, method_used


# async def start_game(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE) -> None:
#     logger.debug("Starting the game.")
#     user_id = update.effective_user.id

#     # Retrieve game_id from context.user_data
#     game_id = context.user_data.get('game_id')

#     if not game_id:
#         await context.bot.send_message(chat_id=update.effective_chat.id, text="Game not found.")
#         return

#     cursor.execute("SELECT moderator_id, started, randomness_method FROM Games WHERE game_id = ?", (game_id,))
#     result = cursor.fetchone()
#     if not result:
#         await context.bot.send_message(chat_id=update.effective_chat.id, text="Game not found.")
#         return
#     moderator_id, started, randomness_method = result

#     if user_id != moderator_id:
#         await context.bot.send_message(chat_id=update.effective_chat.id, text="You are not authorized to start this game.")
#         return

#     if started:
#         await context.bot.send_message(chat_id=update.effective_chat.id, text="The game has already started.")
#         return

#     cursor.execute("""
#         SELECT Roles.user_id, Roles.role, Users.username
#         FROM Roles
#         JOIN Users ON Roles.user_id = Users.user_id
#         WHERE Roles.game_id = ?
#     """, (game_id,))
#     player_roles = cursor.fetchall()
#     logger.debug(f"Player roles: {player_roles}")

#     if not player_roles or any(role is None or role == '' for _, role, _ in player_roles):
#         await context.bot.send_message(
#             chat_id=update.effective_chat.id,
#             text="Cannot start the game. Roles have not been assigned to all players."
#         )
#         return

#     role_message = "Game started! Here are the assigned roles:\n"

#     # Determine the randomness methodology based on the stored randomness_method
#     if randomness_method == "Random.org":
#         methodology_description = (
#             "Randomness Methodology: Random.org API\n\n"
#             "This game used the Random.org API to generate truly random numbers for role assignment. "
#             "Random.org uses atmospheric noise to produce high-quality random numbers, which are "
#             "considered more random than those generated by pseudo-random number algorithms typically "
#             "used in computer programs. This method ensures a fair and unbiased distribution of roles. "
#             "The same methodology is being used in national lotteries, sports events, and other scenarios, "
#             "concerning billions of dollars at stake.\n\n"
#             "If you think this is not fair, write your complaint on a paper, put it in a bottle, and throw it into the ocean. "
#             "If I find it, I will consider it. I promise!"
#         )
#         randomness_method = "Random.org"
#     else:
#         methodology_description = (
#             "Randomness Methodology: Python's random module\n\n"
#             "There was a problem with the Random.org API, so this game used Python's built-in random module for role assignment. "
#             "This module uses the Mersenne Twister algorithm, a pseudo-random number generator. While not truly random, "
#             "it provides high-quality randomness suitable for most applications, including game role "
#             "assignment. The seed for this generator is derived from the system time, ensuring "
#             "different results each time the program runs. "
#             "This method is more than enough for a game of Mafia."
#         )
#         randomness_method = "Python's random module"

#     # Notify each player of their role and the randomness methodology
#     for user_id, role, username in player_roles:
#         if role:
#             role_description = role_descriptions.get(role, "No description available.")
#             role_faction = role_factions.get(role, "Unknown Faction")
#             try:
#                 await context.bot.send_message(
#                     chat_id=user_id,
#                     text=f"Hi {username}, your role is: {role} ({role_faction})\n\nRole Description:\n{role_description}\n\n{methodology_description}"
#                 )
#                 role_message += f"{username} (ID: {user_id}): {role}\n"
#             except Exception as e:
#                 logger.error(f"Failed to send role to user {user_id}: {e}")
#                 try:
#                     await context.bot.send_message(
#                         chat_id=moderator_id,
#                         text=f"Failed to send role to user {username} (ID: {user_id}). Please check their privacy settings."
#                     )
#                 except Exception as ex:
#                     logger.error(f"Failed to notify moderator about summary message for user {user_id}: {ex}")
#         else:
#             await context.bot.send_message(
#                 chat_id=user_id,
#                 text="Error: No role assigned. Please contact the game moderator."
#             )

#     # Send roles summary and randomness methodology to moderator
#     await context.bot.send_message(
#         chat_id=moderator_id,
#         text=f"{role_message}"
#     )

#     # Mark the game as started
#     cursor.execute("UPDATE Games SET started = 1 WHERE game_id = ?", (game_id,))
#     conn.commit()
#     await context.bot.send_message(
#         chat_id=update.effective_chat.id,
#         text=f"The game has started! Roles, descriptions, and randomness methodology have been sent to all players. Method used: {randomness_method}"
#     )
#     logger.debug(f"Game {game_id} started using {randomness_method}")

# async def set_roles(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE) -> None:
#     logger.debug("Setting roles.")
#     # This function can be expanded if additional functionality is needed
#     await show_role_buttons(update, context)

# async def start_latest_game(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE) -> None:
#     logger.debug("Starting the latest game created by the moderator.")
#     user_id = update.effective_user.id

#     # Retrieve the latest game created by the moderator that hasn't been started yet
#     cursor.execute("""
#         SELECT game_id, started, randomness_method
#         FROM Games
#         WHERE moderator_id = ?
#         ORDER BY rowid DESC
#         LIMIT 1
#     """, (user_id,))
#     result = cursor.fetchone()

#     if not result:
#         await context.bot.send_message(chat_id=update.effective_chat.id, text="You have not created any games.")
#         return

#     game_id, started, randomness_method = result

#     if started:
#         await context.bot.send_message(chat_id=update.effective_chat.id, text="The latest game you created has already started.")
#         return

#     # Store game_id in context.user_data
#     context.user_data['game_id'] = game_id

#     # ------------------- Commented Out Section -------------------
#     # Previously, confirm_and_set_roles was called here, which sends the game summary.
#     # Since roles should be confirmed manually, we remove this call.

#     # success, method = await confirm_and_set_roles(update, context, game_id)
#     # if not success:
#     #     await context.bot.send_message(chat_id=update.effective_chat.id, text="Error setting roles. Please try again.")
#     # else:
#     #     await start_game(update, context)  # Call start_game without passcode
#     #     await context.bot.send_message(
#     #         chat_id=update.effective_chat.id,
#     #         text=f"The game has started successfully!\nRandomness source: {method}."
#     #     )
#     # -------------------------------------------------------------

#     # Instead, directly start the game assuming roles have already been set
#     await start_game(update, context)
#     await context.bot.send_message(
#         chat_id=update.effective_chat.id,
#         text="The game has started successfully!"
#     )
#     logger.debug(f"Game {game_id} started successfully.")