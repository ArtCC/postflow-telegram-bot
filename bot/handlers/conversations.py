"""
Conversation Handlers
Multi-step conversation flows using ConversationHandler.
"""

from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from bot.utils import is_authorized
from bot.services.post_service import PostService

# Conversation states
WAITING_POST_CONTENT = 1
WAITING_AI_PROMPT = 2
WAITING_SCHEDULE_DATE = 3


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the current conversation."""
    user_id = update.effective_user.id
    
    if not is_authorized(user_id):
        return ConversationHandler.END
    
    weekly_plan = context.user_data.get("weekly_plan")
    if weekly_plan:
        for item in weekly_plan.get("created_posts", []):
            PostService.delete_post(item["post_id"])

    context.user_data.clear()
    
    await update.message.reply_text(
        "🚫 *Cancelled*\n\n"
        "Operation cancelled\\.\n"
        "Use /menu to start again\\.",
        parse_mode="MarkdownV2"
    )
    
    return ConversationHandler.END


# Post creation conversation handler
post_conversation_handler = ConversationHandler(
    entry_points=[],  # Entries handled by callbacks
    states={},  # States handled inline in posts.py
    fallbacks=[CommandHandler("cancel", cancel_command)],
)


# Schedule conversation handler
schedule_conversation_handler = ConversationHandler(
    entry_points=[],
    states={},
    fallbacks=[CommandHandler("cancel", cancel_command)],
)
