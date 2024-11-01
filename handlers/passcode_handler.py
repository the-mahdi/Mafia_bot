from telegram.ext import MessageHandler, filters, ContextTypes
import logging
from handlers.game_management import join_game, start_game

logger = logging.getLogger("Mafia Bot PasscodeHandler")

async def handle_passcode(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.debug("Handling a text message.")
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

# Create the handler instance
passcode_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, handle_passcode)
