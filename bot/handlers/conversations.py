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

from bot.utils import (
    is_authorized,
    escape_markdown_v2,
    get_topics_menu_keyboard,
    get_templates_menu_keyboard,
    get_user_locale,
    t,
)
from bot.services.post_service import PostService
from bot.services.topic_service import TopicService
from bot.services.template_service import TemplateService

# Conversation states
WAITING_POST_CONTENT = 1
WAITING_AI_PROMPT = 2
WAITING_SCHEDULE_DATE = 3
ADDING_TOPIC = 4
ADDING_TEMPLATE_NAME = 5
ADDING_TEMPLATE_CONTENT = 6
EDITING_TEMPLATE_CONTENT = 7


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
    success, topic, error_msg = TopicService.create_topic(user_id, topic_name, locale=locale)
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


async def prompt_add_template(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompt user to add a new template (callback entry point)."""
    from bot.services.template_service import MIN_TEMPLATE_NAME_LENGTH, MAX_TEMPLATE_NAME_LENGTH

    query = update.callback_query
    locale = get_user_locale(query.from_user)
    context.user_data.pop("template_name", None)
    await query.edit_message_text(
        t("templates.add_prompt_name", locale, min=MIN_TEMPLATE_NAME_LENGTH, max=MAX_TEMPLATE_NAME_LENGTH),
        parse_mode="MarkdownV2"
    )
    return ADDING_TEMPLATE_NAME


async def add_template_receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive template name and prompt for content."""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        return ConversationHandler.END

    locale = get_user_locale(update.effective_user)
    template_name = update.message.text.strip()
    from bot.services.template_service import MIN_TEMPLATE_NAME_LENGTH, MAX_TEMPLATE_NAME_LENGTH

    if len(template_name) < MIN_TEMPLATE_NAME_LENGTH:
        await update.message.reply_text(
            t("errors.template_name_too_short", locale, min=MIN_TEMPLATE_NAME_LENGTH),
            parse_mode="MarkdownV2"
        )
        return ADDING_TEMPLATE_NAME

    if len(template_name) > MAX_TEMPLATE_NAME_LENGTH:
        await update.message.reply_text(
            t("errors.template_name_too_long", locale, max=MAX_TEMPLATE_NAME_LENGTH),
            parse_mode="MarkdownV2"
        )
        return ADDING_TEMPLATE_NAME
    context.user_data["template_name"] = template_name

    await update.message.reply_text(
        t("templates.add_prompt_content", locale, name=escape_markdown_v2(template_name)),
        parse_mode="MarkdownV2"
    )

    return ADDING_TEMPLATE_CONTENT


async def add_template_receive_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive template content and create the template."""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        return ConversationHandler.END

    locale = get_user_locale(update.effective_user)
    template_name = context.user_data.get("template_name", "").strip()
    template_content = update.message.text

    success, template, error_msg = TemplateService.create_template(
        user_id,
        template_name,
        template_content,
        locale=locale
    )

    if success:
        await update.message.reply_text(
            t("templates.added", locale, name=escape_markdown_v2(template.name)),
            parse_mode="MarkdownV2",
            reply_markup=get_templates_menu_keyboard(user_id, locale)
        )
    else:
        await update.message.reply_text(
            t("templates.add_error", locale, error=escape_markdown_v2(error_msg)),
            parse_mode="MarkdownV2",
            reply_markup=get_templates_menu_keyboard(user_id, locale)
        )

    context.user_data.pop("template_name", None)
    return ConversationHandler.END


async def prompt_edit_template(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompt user to edit template content (callback entry point)."""
    query = update.callback_query
    locale = get_user_locale(query.from_user)
    template_id = int(query.data.split("_")[-1])

    template = TemplateService.get_template_for_user(template_id, query.from_user.id)
    if not template:
        await query.answer(t("templates.not_found_alert", locale), show_alert=True)
        return ConversationHandler.END

    context.user_data["editing_template_id"] = template_id
    await query.edit_message_text(
        t(
            "templates.edit_prompt",
            locale,
            name=escape_markdown_v2(template.name),
            content=escape_markdown_v2(template.content),
        ),
        parse_mode="MarkdownV2"
    )
    return EDITING_TEMPLATE_CONTENT


async def edit_template_receive_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive new template content and update."""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        return ConversationHandler.END

    locale = get_user_locale(update.effective_user)
    template_id = context.user_data.pop("editing_template_id", None)
    if not template_id:
        await update.message.reply_text(
            t("templates.not_found_alert", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_templates_menu_keyboard(user_id, locale)
        )
        return ConversationHandler.END

    success, error_msg = TemplateService.update_template_content(
        template_id,
        user_id,
        update.message.text,
        locale=locale
    )

    if success:
        await update.message.reply_text(
            t("templates.updated", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_templates_menu_keyboard(user_id, locale)
        )
    else:
        await update.message.reply_text(
            t("templates.update_error", locale, error=escape_markdown_v2(error_msg)),
            parse_mode="MarkdownV2",
            reply_markup=get_templates_menu_keyboard(user_id, locale)
        )

    return ConversationHandler.END


template_conversation_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(prompt_add_template, pattern="^templates_add$"),
        CallbackQueryHandler(prompt_edit_template, pattern="^templates_edit_\\d+$"),
    ],
    states={
        ADDING_TEMPLATE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_template_receive_name)],
        ADDING_TEMPLATE_CONTENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_template_receive_content)],
        EDITING_TEMPLATE_CONTENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_template_receive_content)],
    },
    fallbacks=[CommandHandler("cancel", cancel_command)],
)

