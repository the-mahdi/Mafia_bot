from telegram.ext import MessageHandler, filters, ContextTypes
import logging
from handlers.game_management import join_game, start_game, get_player_count
from roles import role_templates, save_role_templates
from db import conn, cursor

logger = logging.getLogger("Mafia Bot PasscodeHandler")

async def handle_passcode(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.debug("Handling a text message.")
    user_input = update.message.text.strip()
    action = context.user_data.get("action")
    user_id = update.effective_user.id

    if action == "awaiting_name":
        # Check if the user already exists
        cursor.execute("SELECT username FROM Users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        if result:
            # Update the user's name if it's different
            if result[0] != user_input:
                cursor.execute("UPDATE Users SET username = ? WHERE user_id = ?", (user_input, user_id))
                conn.commit()
            context.user_data["username"] = user_input
        else:
            # Insert new user into the database
            cursor.execute("INSERT INTO Users (user_id, username) VALUES (?, ?)", (user_id, user_input))
            conn.commit()
            context.user_data["username"] = user_input
        context.user_data["action"] = "join_game"  # Now expecting a passcode
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Please enter the passcode to join the game.")
    elif action == "existing_user":
        # Check if the input is a name or a passcode
        if is_valid_passcode(user_input):
            context.user_data["action"] = "join_game"
            await join_game(update, context, user_input)
        else:
            # Update the user's name in the database
            cursor.execute("UPDATE Users SET username = ? WHERE user_id = ?", (user_input, user_id))
            conn.commit()
            context.user_data["username"] = user_input
            context.user_data["action"] = "join_game"
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Name updated. Please enter the passcode to join the game.")
    elif action == "join_game":
        await join_game(update, context, user_input)  # Pass user_input as the passcode
    elif action == "set_roles":
        # In the revised flow, roles are set via buttons, so passcode is not needed here
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Please use the role buttons to set roles.")
    elif action == "start_game":
        await start_game(update, context, user_input)
    elif action == "awaiting_template_name":
        # Handle the input as template name
        await save_template_to_json(update, context, user_input)
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Unknown action. Please use /start to begin.")

async def save_template_to_json(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE, template_name: str) -> None:
    logger.debug("Saving template.")
    game_id = context.user_data.get('game_id')
    player_count = context.user_data.get("player_count") # Get from context
    roles_for_template = context.user_data.get('roles_for_template') # Get from context
    if not template_name:
         await context.bot.send_message(chat_id=update.effective_chat.id, text="Invalid template name.")
         return

    if not game_id:
      await context.bot.send_message(chat_id=update.effective_chat.id, text="No game selected.")
      return
    if not roles_for_template:
      await context.bot.send_message(chat_id=update.effective_chat.id, text="No roles found.")
      return
    if not player_count:
        player_count = get_player_count(game_id) # Get from DB, since we might not have it in user_data
    
    template_name_with_count = f"{template_name} - {player_count}"

    # Check if the template name already exists
    
    if str(player_count) in role_templates:
      for existing_template in role_templates[str(player_count)]:
          if existing_template['name'] == template_name_with_count:
              await context.bot.send_message(chat_id=update.effective_chat.id, text="A template with this name already exists. Please use a different name.")
              return

    new_template = {
        "name": template_name_with_count,
        "roles": roles_for_template
    }
    
    # Load existing template or initialize it
    templates = role_templates
    # If there are already templates for current player count
    if str(player_count) in templates:
        templates[str(player_count)].append(new_template)
    else:
        templates[str(player_count)] = [new_template]
    
    save_role_templates(templates)
    role_templates.update(templates)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Template '{template_name_with_count}' saved.")
    # Reset action
    context.user_data['action'] = None

def is_valid_passcode(text):
    # Basic check for a UUID-like format
    import re
    pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$')
    return bool(pattern.match(text))

# Create the handler instance
passcode_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, handle_passcode)
