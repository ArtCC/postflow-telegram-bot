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
    CallbackQueryHandler,
    filters,
)

from bot.utils import is_authorized, escape_markdown_v2, get_topics_menu_keyboard, get_user_locale, t
from bot.services.post_service import PostService
from bot.services.topic_service import TopicService

# Conversation states
WAITING_POST_CONTENT = 1
WAITING_AI_PROMPT = 2
WAITING_SCHEDULE_DATE = 3
ADDING_TOPIC = 4


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
    
    locale = get_user_locale(update.effective_user)
    await update.message.reply_text(
        t("conversation.cancelled", locale),
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


async def add_topic_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the add topic conversation (called from callback)."""
    # This message is sent from the callback handler
    return ADDING_TOPIC


async def prompt_add_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompt user to add a new topic (callback entry point)."""
    from bot.services.topic_service import MIN_TOPIC_NAME_LENGTH, MAX_TOPIC_NAME_LENGTH

    query = update.callback_query
    locale = get_user_locale(query.from_user)
    await query.edit_message_text(
        t("topics.add_prompt", locale, min=MIN_TOPIC_NAME_LENGTH, max=MAX_TOPIC_NAME_LENGTH),
        parse_mode="MarkdownV2"
    )

    return ADDING_TOPIC


async def add_topic_receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive and save the topic name."""
    user_id = update.effective_user.id
    
    if not is_authorized(user_id):
        return ConversationHandler.END
    
    topic_name = update.message.text.strip()
    
    # Create the topic
    success, topic, error_msg = TopicService.create_topic(user_id, topic_name)
    locale = get_user_locale(update.effective_user)
    
    if success:
        await update.message.reply_text(
            t("topics.added", locale, name=escape_markdown_v2(topic.name)),
            parse_mode="MarkdownV2",
            reply_markup=get_topics_menu_keyboard(user_id, locale)
        )
    else:
        await update.message.reply_text(
            t("topics.add_error", locale, error=escape_markdown_v2(error_msg)),
            parse_mode="MarkdownV2",
            reply_markup=get_topics_menu_keyboard(user_id, locale)
        )
    
    return ConversationHandler.END


# Topic conversation handler
topic_conversation_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(prompt_add_topic, pattern="^topics_add$")],
    states={
        ADDING_TOPIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_topic_receive_name)],
    },
    fallbacks=[CommandHandler("cancel", cancel_command)],
)

