"""
Callback Handlers
Central router for all inline button callbacks.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.config import logger, TWITTER_ENABLED, OPENAI_ENABLED
from bot.utils import (
    is_authorized, 
    escape_markdown_v2, 
    get_main_menu_keyboard, 
    get_back_keyboard, 
    get_new_post_keyboard,
    get_topics_menu_keyboard,
    get_topics_list_keyboard,
    get_topics_delete_keyboard,
    get_topic_delete_confirm_keyboard,
    get_topics_delete_all_confirm_keyboard,
    get_ai_with_topics_keyboard,
    get_templates_menu_keyboard,
    get_templates_list_keyboard,
    get_templates_use_keyboard,
    get_templates_delete_keyboard,
    get_template_delete_confirm_keyboard,
    get_templates_delete_all_confirm_keyboard,
    get_template_view_keyboard,
    get_user_locale,
    t,
)
from bot.handlers.commands import help_command
from bot.services.topic_service import TopicService
from bot.services.template_service import TemplateService


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Central callback router for all inline buttons."""
    query = update.callback_query
    user_id = query.from_user.id
    locale = get_user_locale(query.from_user)
    
    if not is_authorized(user_id):
        await query.answer(t("errors.not_authorized_alert", locale), show_alert=True)
        return
    
    await query.answer()  # Acknowledge the callback
    
    data = query.data
    logger.info(f"Callback received: {data} from user {user_id}")
    
    # Main menu callbacks
    if data == "menu":
        await show_main_menu(query)
    
    elif data == "help":
        await show_help(query)
    
    elif data == "status":
        await show_status(query)
    
    elif data == "new_post":
        await show_new_post_options(query)

    elif data == "plan_week":
        from bot.handlers.posts import start_weekly_plan
        await start_weekly_plan(query, context)
    
    elif data == "scheduled":
        from bot.handlers.posts import show_scheduled_posts
        await show_scheduled_posts(query, context)

    elif data.startswith("calendar_week_"):
        from bot.handlers.posts import show_weekly_calendar
        await show_weekly_calendar(query, context)

    elif data == "drafts":
        from bot.handlers.posts import show_drafts
        await show_drafts(query, context)
    
    elif data == "statistics":
        await show_statistics(query)
    
    elif data == "settings":
        await show_settings(query)

    # Templates management callbacks
    elif data == "templates_menu":
        await show_templates_menu(query, user_id)

    elif data == "templates_add_disabled":
        await query.answer(t("templates.max_reached_alert", locale), show_alert=True)

    elif data == "templates_list":
        await show_templates_list(query, user_id)

    elif data == "templates_list_empty":
        await query.answer(t("templates.list_empty_alert", locale), show_alert=True)

    elif data == "templates_use":
        await show_templates_use(query, user_id, back_callback="templates_menu")

    elif data == "templates_use_empty":
        await query.answer(t("templates.use_empty_alert", locale), show_alert=True)

    elif data.startswith("templates_view_"):
        template_id = int(data.split("_")[-1])
        await view_template(query, template_id)

    elif data == "templates_delete":
        await show_templates_delete(query, user_id)

    elif data.startswith("templates_delete_confirm_"):
        template_id = int(data.split("_")[-1])
        await confirm_delete_template(query, template_id)

    elif data.startswith("templates_delete_execute_"):
        template_id = int(data.split("_")[-1])
        await execute_delete_template(query, user_id, template_id)

    elif data == "templates_delete_all":
        await confirm_delete_all_templates(query)

    elif data == "templates_delete_all_execute":
        await execute_delete_all_templates(query, user_id)

    # Topics management callbacks
    elif data == "topics_menu":
        await show_topics_menu(query, user_id)
    
    elif data == "topics_add_disabled":
        await query.answer(t("topics.max_reached_alert", locale), show_alert=True)
    
    elif data == "topics_list":
        await show_topics_list(query, user_id)
    
    elif data == "topics_list_empty":
        await query.answer(t("topics.list_empty_alert", locale), show_alert=True)
    
    elif data.startswith("topics_view_"):
        topic_id = int(data.split("_")[-1])
        await view_topic(query, topic_id)
    
    elif data == "topics_delete":
        await show_topics_delete(query, user_id)
    
    elif data.startswith("topics_delete_confirm_"):
        topic_id = int(data.split("_")[-1])
        await confirm_delete_topic(query, topic_id)
    
    elif data.startswith("topics_delete_execute_"):
        topic_id = int(data.split("_")[-1])
        await execute_delete_topic(query, user_id, topic_id)
    
    elif data == "topics_delete_all":
        await confirm_delete_all_topics(query)
    
    elif data == "topics_delete_all_execute":
        await execute_delete_all_topics(query, user_id)
    
    elif data.startswith("ai_topic_"):
        topic_id = int(data.split("_")[-1])
        from bot.handlers.posts import handle_ai_with_topic
        await handle_ai_with_topic(query, context, topic_id)
    
    elif data == "ai_custom":
        await query.edit_message_text(
            t("topics.ai_custom", locale),
            parse_mode="MarkdownV2"
        )
        context.user_data['awaiting'] = 'ai_prompt'

    elif data.startswith("plan_day_"):
        from bot.handlers.posts import toggle_weekly_day
        await toggle_weekly_day(query, context)

    elif data == "plan_days_next":
        from bot.handlers.posts import confirm_weekly_days
        await confirm_weekly_days(query, context)

    elif data == "plan_days_back":
        from bot.handlers.posts import show_weekly_days
        await show_weekly_days(query, context)

    elif data.startswith("plan_ppd_"):
        from bot.handlers.posts import select_posts_per_day
        await select_posts_per_day(query, context)

    elif data == "plan_mode_manual":
        from bot.handlers.posts import prompt_weekly_manual
        await prompt_weekly_manual(query, context)

    elif data == "plan_mode_ai":
        from bot.handlers.posts import prompt_weekly_ai
        await prompt_weekly_ai(query, context)

    elif data == "plan_confirm":
        from bot.handlers.posts import confirm_weekly_plan
        await confirm_weekly_plan(query, context)

    elif data in {"plan_cancel", "plan_cancel_all"}:
        from bot.handlers.posts import cancel_weekly_plan
        await cancel_weekly_plan(query, context)
    
    # Post creation callbacks
    elif data == "post_manual":
        await query.edit_message_text(
            t("posts.manual_prompt", locale),
            parse_mode="MarkdownV2"
        )
        context.user_data['awaiting'] = 'manual_post'

    elif data == "post_image":
        from bot.handlers.posts import prompt_image_post
        await prompt_image_post(query, context)
    
    elif data == "post_ai":
        # Check if user has topics
        topic_count = TopicService.get_topic_count(user_id)
        
        if topic_count > 0:
            # Show topics selection
            await query.edit_message_text(
                t("topics.ai_intro", locale),
                parse_mode="MarkdownV2",
                reply_markup=get_ai_with_topics_keyboard(user_id, locale)
            )
        else:
            # Original behavior - no topics
            await query.edit_message_text(
                t("ai.prompt", locale),
                parse_mode="MarkdownV2"
            )
            context.user_data['awaiting'] = 'ai_prompt'

    elif data == "post_template":
        await show_templates_use(query, user_id, back_callback="new_post")
    
    # Handle other callback patterns
    elif data.startswith("publish_"):
        from bot.handlers.posts import handle_publish_post
        await handle_publish_post(query, context)
    
    elif data.startswith("schedule_") and not data.startswith("scheduled"):
        from bot.handlers.posts import handle_schedule_menu
        await handle_schedule_menu(query, context)
    
    elif data.startswith("quick_schedule_"):
        from bot.handlers.posts import handle_quick_schedule
        await handle_quick_schedule(query, context)
    
    elif data.startswith("custom_schedule_"):
        from bot.handlers.posts import handle_custom_schedule_prompt
        await handle_custom_schedule_prompt(query, context)
    
    elif data.startswith("edit_"):
        from bot.handlers.posts import handle_edit_post
        await handle_edit_post(query, context)
    
    elif data.startswith("cancel_delete_"):
        # User cancelled deletion - go back to preview
        post_id = int(data.split("_")[-1])
        from bot.handlers.posts import show_post_preview_edit
        await show_post_preview_edit(query, post_id)
    
    elif data.startswith("delete_") or data.startswith("confirm_delete_"):
        from bot.handlers.posts import handle_delete_post
        await handle_delete_post(query, context)
    
    elif data.startswith("preview_"):
        from bot.handlers.posts import show_post_preview_edit
        post_id = int(data.split("_")[1])
        await show_post_preview_edit(query, post_id)
    
    elif data.startswith("view_scheduled_"):
        from bot.handlers.posts import handle_view_scheduled_post
        await handle_view_scheduled_post(query, context)
    
    elif data.startswith("scheduled_page_"):
        from bot.handlers.posts import handle_scheduled_page
        await handle_scheduled_page(query, context)

    elif data.startswith("drafts_page_"):
        from bot.handlers.posts import handle_drafts_page
        await handle_drafts_page(query, context)

    elif data.startswith("templates_use_"):
        from bot.handlers.posts import create_post_from_template
        await create_post_from_template(query, context)
    
    elif data.startswith("reschedule_"):
        from bot.handlers.posts import handle_reschedule_prompt
        await handle_reschedule_prompt(query, context)
    
    elif data == "retry_last_action":
        await show_main_menu(query)
    
    else:
        logger.warning(f"Unhandled callback data: {data}")
        await query.answer(t("errors.feature_coming_soon", locale), show_alert=True)


async def show_main_menu(query) -> None:
    """Show the main menu."""
    locale = get_user_locale(query.from_user)
    menu_message = f"{t('menu.title', locale)}\n\n{t('menu.select_option', locale)}"
    
    await query.edit_message_text(
        menu_message,
        parse_mode="MarkdownV2",
        reply_markup=get_main_menu_keyboard(locale)
    )


async def show_help(query) -> None:
    """Show help information."""
    locale = get_user_locale(query.from_user)
    help_message = t("help.message", locale)
    
    await query.edit_message_text(
        help_message,
        parse_mode="MarkdownV2",
        reply_markup=get_back_keyboard(locale)
    )


async def show_new_post_options(query) -> None:
    """Show new post creation options."""
    locale = get_user_locale(query.from_user)
    message = f"{t('new_post.title', locale)}\n\n{t('new_post.choose_method', locale)}"
    
    await query.edit_message_text(
        message,
        parse_mode="MarkdownV2",
        reply_markup=get_new_post_keyboard(locale)
    )


async def show_statistics(query) -> None:
    """Show post statistics."""
    from bot.services.post_service import PostService
    locale = get_user_locale(query.from_user)
    
    stats = PostService.get_post_statistics()
    
    # Calculate success rate
    total_attempts = stats['published'] + stats['failed']
    success_rate = (stats['published'] / total_attempts * 100) if total_attempts > 0 else 0
    
    stats_message = t(
        "stats.message",
        locale,
        total=stats['total'],
        published=stats['published'],
        scheduled=stats['scheduled'],
        draft=stats['draft'],
        failed=stats['failed'],
        success_rate=f"{success_rate:.1f}",
    )
    
    await query.edit_message_text(
        stats_message,
        parse_mode="MarkdownV2",
        reply_markup=get_back_keyboard(locale)
    )


async def show_settings(query) -> None:
    """Show settings (placeholder for future features)."""
    from bot.config import TWITTER_ENABLED, OPENAI_ENABLED
    locale = get_user_locale(query.from_user)
    
    twitter_status = t("settings.enabled", locale) if TWITTER_ENABLED else t("settings.disabled", locale)
    openai_status = t("settings.enabled", locale) if OPENAI_ENABLED else t("settings.disabled", locale)
    
    settings_message = t(
        "settings.message",
        locale,
        twitter_status=escape_markdown_v2(twitter_status),
        openai_status=escape_markdown_v2(openai_status),
    )
    
    await query.edit_message_text(
        settings_message,
        parse_mode="MarkdownV2",
        reply_markup=get_back_keyboard(locale)
    )


async def show_status(query) -> None:
    """Show system status."""
    from bot.services.twitter_service import TwitterService
    from bot.services.openai_service import OpenAIService
    from bot.services.post_service import PostService
    locale = get_user_locale(query.from_user)
    
    # Check service status
    twitter_service = TwitterService() if TWITTER_ENABLED else None
    openai_service = OpenAIService() if OPENAI_ENABLED else None
    
    twitter_status = t("status.twitter_connected", locale)
    openai_status = t("status.openai_available", locale)
    
    if twitter_service:
        success, message = twitter_service.test_connection(locale=locale)
        if success:
            twitter_status = f"🟢 {escape_markdown_v2(message)}"
        else:
            twitter_status = f"🔴 {escape_markdown_v2(message)}"
    else:
        twitter_status = t("status.twitter_not_configured", locale)
    
    if openai_service:
        success, message = openai_service.test_connection(locale=locale)
        if success:
            openai_status = t("status.openai_available", locale)
        else:
            openai_status = f"🔴 {escape_markdown_v2(message[:50])}"
    else:
        openai_status = t("status.openai_disabled", locale)
    
    # Get statistics
    stats = PostService.get_post_statistics()
    
    status_message = t(
        "status.message",
        locale,
        bot_status=t("status.bot_online", locale),
        twitter_status=twitter_status,
        openai_status=openai_status,
        db_status=t("status.db_healthy", locale),
        total=stats['total'],
        published=stats['published'],
        scheduled=stats['scheduled'],
        failed=stats['failed'],
        last_check=t("status.last_check_now", locale),
    )
    
    await query.edit_message_text(
        status_message,
        parse_mode="MarkdownV2",
        reply_markup=get_back_keyboard(locale)
    )


# Topics management functions

async def show_topics_menu(query, user_id: int) -> None:
    """Show topics management menu."""
    locale = get_user_locale(query.from_user)
    topic_count = TopicService.get_topic_count(user_id)
    from bot.services.topic_service import MAX_TOPICS_PER_USER
    
    topics_message = t(
        "topics.menu",
        locale,
        count=topic_count,
        max=MAX_TOPICS_PER_USER,
    )
    
    await query.edit_message_text(
        topics_message,
        parse_mode="MarkdownV2",
        reply_markup=get_topics_menu_keyboard(user_id, locale)
    )


async def show_topics_list(query, user_id: int) -> None:
    """Show list of user's topics."""
    locale = get_user_locale(query.from_user)
    topics = TopicService.get_user_topics(user_id)
    
    if not topics:
        await query.edit_message_text(
            t("topics.list_empty", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_topics_menu_keyboard(user_id, locale)
        )
        return
    
    from bot.services.topic_service import MAX_TOPICS_PER_USER
    
    topics_text = "\n".join([
        f"• `{escape_markdown_v2(topic.name)}`"
        for topic in topics
    ])
    topics_message = t(
        "topics.list_title",
        locale,
        count=len(topics),
        max=MAX_TOPICS_PER_USER,
        topics=topics_text,
    )
    
    await query.edit_message_text(
        topics_message,
        parse_mode="MarkdownV2",
        reply_markup=get_topics_list_keyboard(user_id, locale)
    )


async def view_topic(query, topic_id: int) -> None:
    """View a specific topic."""
    topic = TopicService.get_topic_for_user(topic_id, query.from_user.id)
    locale = get_user_locale(query.from_user)
    
    if not topic:
        await query.answer(t("topics.not_found_alert", locale), show_alert=True)
        return
    
    from bot.utils import format_datetime
    
    topic_message = t(
        "topics.details",
        locale,
        name=escape_markdown_v2(topic.name),
        created=escape_markdown_v2(format_datetime(topic.created_at, locale=locale)),
    )
    
    await query.edit_message_text(
        topic_message,
        parse_mode="MarkdownV2",
        reply_markup=get_topics_list_keyboard(query.from_user.id, locale)
    )


async def show_topics_delete(query, user_id: int) -> None:
    """Show topics for deletion."""
    locale = get_user_locale(query.from_user)
    topics = TopicService.get_user_topics(user_id)
    
    if not topics:
        await query.edit_message_text(
            t("topics.delete_empty", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_topics_menu_keyboard(user_id, locale)
        )
        return
    
    await query.edit_message_text(
        t("topics.delete_select", locale),
        parse_mode="MarkdownV2",
        reply_markup=get_topics_delete_keyboard(user_id, locale)
    )


async def confirm_delete_topic(query, topic_id: int) -> None:
    """Confirm deletion of a specific topic."""
    topic = TopicService.get_topic(topic_id)
    locale = get_user_locale(query.from_user)
    
    if not topic:
        await query.answer(t("topics.not_found_alert", locale), show_alert=True)
        return
    
    await query.edit_message_text(
        t("topics.delete_confirm", locale, name=escape_markdown_v2(topic.name)),
        parse_mode="MarkdownV2",
        reply_markup=get_topic_delete_confirm_keyboard(topic_id, locale)
    )


async def execute_delete_topic(query, user_id: int, topic_id: int) -> None:
    """Execute deletion of a topic."""
    locale = get_user_locale(query.from_user)
    success, error_msg = TopicService.delete_topic(topic_id, user_id, locale=locale)
    
    if success:
        await query.answer(t("topics.deleted_alert", locale), show_alert=False)
        remaining = TopicService.get_topic_count(user_id)
        if remaining > 0:
            await show_topics_delete(query, user_id)
        else:
            await query.edit_message_text(
                t("topics.deleted_empty", locale),
                parse_mode="MarkdownV2",
                reply_markup=get_topics_menu_keyboard(user_id, locale)
            )
    else:
        await query.answer(f"❌ {error_msg}", show_alert=True)


async def confirm_delete_all_topics(query) -> None:
    """Confirm deletion of all topics."""
    locale = get_user_locale(query.from_user)
    await query.edit_message_text(
        t("topics.delete_all_confirm", locale),
        parse_mode="MarkdownV2",
        reply_markup=get_topics_delete_all_confirm_keyboard(locale)
    )


async def execute_delete_all_topics(query, user_id: int) -> None:
    """Execute deletion of all topics."""
    locale = get_user_locale(query.from_user)
    success, deleted_count, error_msg = TopicService.delete_all_topics(user_id, locale=locale)
    
    if success:
        await query.answer(t("topics.deleted_all_alert", locale, count=deleted_count), show_alert=True)
        await show_topics_menu(query, user_id)
    else:
        await query.answer(f"❌ {error_msg}", show_alert=True)


# Templates management functions

async def show_templates_menu(query, user_id: int) -> None:
    """Show templates management menu."""
    locale = get_user_locale(query.from_user)
    template_count = TemplateService.get_template_count(user_id)
    from bot.services.template_service import MAX_TEMPLATES_PER_USER

    templates_message = t(
        "templates.menu",
        locale,
        count=template_count,
        max=MAX_TEMPLATES_PER_USER,
    )

    await query.edit_message_text(
        templates_message,
        parse_mode="MarkdownV2",
        reply_markup=get_templates_menu_keyboard(user_id, locale)
    )


async def show_templates_list(query, user_id: int) -> None:
    """Show list of user's templates."""
    locale = get_user_locale(query.from_user)
    templates = TemplateService.get_user_templates(user_id)

    if not templates:
        await query.edit_message_text(
            t("templates.list_empty", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_templates_menu_keyboard(user_id, locale)
        )
        return

    from bot.services.template_service import MAX_TEMPLATES_PER_USER

    templates_text = "\n".join([
        f"• `{escape_markdown_v2(template.name)}`"
        for template in templates
    ])
    templates_message = t(
        "templates.list_title",
        locale,
        count=len(templates),
        max=MAX_TEMPLATES_PER_USER,
        templates=templates_text,
    )

    await query.edit_message_text(
        templates_message,
        parse_mode="MarkdownV2",
        reply_markup=get_templates_list_keyboard(user_id, locale)
    )


async def show_templates_use(query, user_id: int, back_callback: str) -> None:
    """Show templates list for creating a post."""
    locale = get_user_locale(query.from_user)
    templates = TemplateService.get_user_templates(user_id)

    if not templates:
        await query.edit_message_text(
            t("templates.list_empty", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_templates_menu_keyboard(user_id, locale)
        )
        return

    await query.edit_message_text(
        t("templates.use_title", locale),
        parse_mode="MarkdownV2",
        reply_markup=get_templates_use_keyboard(user_id, locale, back_callback=back_callback)
    )


async def view_template(query, template_id: int) -> None:
    """View a specific template."""
    template = TemplateService.get_template_for_user(template_id, query.from_user.id)
    locale = get_user_locale(query.from_user)

    if not template:
        await query.answer(t("templates.not_found_alert", locale), show_alert=True)
        return

    from bot.utils import format_datetime

    template_message = t(
        "templates.details",
        locale,
        name=escape_markdown_v2(template.name),
        created=escape_markdown_v2(format_datetime(template.created_at, locale=locale)),
        updated=escape_markdown_v2(format_datetime(template.updated_at, locale=locale)),
        content=escape_markdown_v2(template.content),
    )

    await query.edit_message_text(
        template_message,
        parse_mode="MarkdownV2",
        reply_markup=get_template_view_keyboard(template_id, locale)
    )


async def show_templates_delete(query, user_id: int) -> None:
    """Show templates for deletion."""
    locale = get_user_locale(query.from_user)
    templates = TemplateService.get_user_templates(user_id)

    if not templates:
        await query.edit_message_text(
            t("templates.delete_empty", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_templates_menu_keyboard(user_id, locale)
        )
        return

    await query.edit_message_text(
        t("templates.delete_select", locale),
        parse_mode="MarkdownV2",
        reply_markup=get_templates_delete_keyboard(user_id, locale)
    )


async def confirm_delete_template(query, template_id: int) -> None:
    """Confirm deletion of a specific template."""
    template = TemplateService.get_template_for_user(template_id, query.from_user.id)
    locale = get_user_locale(query.from_user)

    if not template:
        await query.answer(t("templates.not_found_alert", locale), show_alert=True)
        return

    await query.edit_message_text(
        t("templates.delete_confirm", locale, name=escape_markdown_v2(template.name)),
        parse_mode="MarkdownV2",
        reply_markup=get_template_delete_confirm_keyboard(template_id, locale)
    )


async def execute_delete_template(query, user_id: int, template_id: int) -> None:
    """Execute deletion of a template."""
    locale = get_user_locale(query.from_user)
    success, error_msg = TemplateService.delete_template(template_id, user_id, locale=locale)

    if success:
        await query.answer(t("templates.deleted_alert", locale), show_alert=False)
        remaining = TemplateService.get_template_count(user_id)
        if remaining > 0:
            await show_templates_delete(query, user_id)
        else:
            await query.edit_message_text(
                t("templates.deleted_empty", locale),
                parse_mode="MarkdownV2",
                reply_markup=get_templates_menu_keyboard(user_id, locale)
            )
    else:
        await query.answer(f"❌ {error_msg}", show_alert=True)


async def confirm_delete_all_templates(query) -> None:
    """Confirm deletion of all templates."""
    locale = get_user_locale(query.from_user)
    await query.edit_message_text(
        t("templates.delete_all_confirm", locale),
        parse_mode="MarkdownV2",
        reply_markup=get_templates_delete_all_confirm_keyboard(locale)
    )


async def execute_delete_all_templates(query, user_id: int) -> None:
    """Execute deletion of all templates."""
    locale = get_user_locale(query.from_user)
    success, deleted_count, error_msg = TemplateService.delete_all_templates(user_id, locale=locale)

    if success:
        await query.answer(t("templates.deleted_all_alert", locale, count=deleted_count), show_alert=True)
        await show_templates_menu(query, user_id)
    else:
        await query.answer(f"❌ {error_msg}", show_alert=True)

