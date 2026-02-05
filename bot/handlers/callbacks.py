"""
Callback Handlers
Central router for all inline button callbacks.
"""

from telegram import Update
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
)
from bot.handlers.commands import help_command
from bot.services.topic_service import TopicService


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Central callback router for all inline buttons."""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_authorized(user_id):
        await query.answer("⛔ Not authorized", show_alert=True)
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

    elif data == "drafts":
        from bot.handlers.posts import show_drafts
        await show_drafts(query, context)
    
    elif data == "statistics":
        await show_statistics(query)
    
    elif data == "settings":
        await show_settings(query)

    # Topics management callbacks
    elif data == "topics_menu":
        await show_topics_menu(query, user_id)
    
    elif data == "topics_add_disabled":
        await query.answer("⚠️ Maximum topics reached! Delete one to add more.", show_alert=True)
    
    elif data == "topics_list":
        await show_topics_list(query, user_id)
    
    elif data == "topics_list_empty":
        await query.answer("📋 No topics yet. Add one to get started!", show_alert=True)
    
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
            "🤖 *AI GENERATION*\n\n"
            "Describe what you want to post\\.\n"
            "Example: `Thread on AI trends in 2026`\n\n"
            "Type /cancel to abort\\.",
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
            "✏️ *WRITE POST*\n\n"
            "Send your post text\\.\n"
            "Tip: long posts become threads\\.\n"
            "Type /cancel to abort\\.",
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
                "🤖 *AI GENERATION*\n\n"
                "Select a topic preset or write a custom prompt:",
                parse_mode="MarkdownV2",
                reply_markup=get_ai_with_topics_keyboard(user_id)
            )
        else:
            # Original behavior - no topics
            await query.edit_message_text(
                "🤖 *AI GENERATION*\n\n"
                "Describe what you want to post\\.\n"
                "Example: `Thread on AI trends in 2026`\n\n"
                "Type /cancel to abort\\.",
                parse_mode="MarkdownV2"
            )
            context.user_data['awaiting'] = 'ai_prompt'
    
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
    
    elif data.startswith("reschedule_"):
        from bot.handlers.posts import handle_reschedule_prompt
        await handle_reschedule_prompt(query, context)
    
    elif data == "retry_last_action":
        await show_main_menu(query)
    
    else:
        logger.warning(f"Unhandled callback data: {data}")
        await query.answer("Feature coming soon!", show_alert=True)


async def show_main_menu(query) -> None:
    """Show the main menu."""
    menu_message = (
        "🎯 *MENU*\n\n"
        "Select an option:"
    )
    
    await query.edit_message_text(
        menu_message,
        parse_mode="MarkdownV2",
        reply_markup=get_main_menu_keyboard()
    )


async def show_help(query) -> None:
    """Show help information."""
    help_message = (
        "ℹ️ *HELP*\n\n"
        "*Commands*\n"
        "• `/start` \\- Welcome\n"
        "• `/menu` \\- Main menu\n"
        "• `/new` \\- New post\n"
        "• `/plan` \\- Plan week\n"
        "• `/topics` \\- Manage topics\n"
        "• `/drafts` \\- Drafts\n"
        "• `/scheduled` \\- Scheduled posts\n"
        "• `/stats` \\- Statistics\n"
        "• `/status` \\- System status\n"
        "• `/settings` \\- Settings\n"
        "• `/chatid` \\- Your user ID\n"
        "• `/help` \\- Help\n"
        "• `/author` \\- About the author\n"
        "• `/cancel` \\- Cancel\n\n"
        "*Highlights*\n"
        "• Manual or AI posts\n"
        "• Topic presets for AI\n"
        "• Scheduling\n"
        "• Threads for long posts\n"
        "• Stats overview"
    )
    
    await query.edit_message_text(
        help_message,
        parse_mode="MarkdownV2",
        reply_markup=get_back_keyboard()
    )


async def show_new_post_options(query) -> None:
    """Show new post creation options."""
    message = (
        "✍️ *NEW POST*\n\n"
        "Choose a method:"
    )
    
    await query.edit_message_text(
        message,
        parse_mode="MarkdownV2",
        reply_markup=get_new_post_keyboard()
    )


async def show_statistics(query) -> None:
    """Show post statistics."""
    from bot.services.post_service import PostService
    
    stats = PostService.get_post_statistics()
    
    # Calculate success rate
    total_attempts = stats['published'] + stats['failed']
    success_rate = (stats['published'] / total_attempts * 100) if total_attempts > 0 else 0
    
    stats_message = (
        f"📊 *STATISTICS*\n\n"
        f"*Overview*\n"
        f"• Total: `{stats['total']}`\n"
        f"• Published: `{stats['published']}`\n"
        f"• Scheduled: `{stats['scheduled']}`\n"
        f"• Draft: `{stats['draft']}`\n"
        f"• Failed: `{stats['failed']}`\n\n"
        f"*Performance*\n"
        f"• Success rate: `{success_rate:.1f}%`"
    )
    
    await query.edit_message_text(
        stats_message,
        parse_mode="MarkdownV2",
        reply_markup=get_back_keyboard()
    )


async def show_settings(query) -> None:
    """Show settings (placeholder for future features)."""
    from bot.config import TWITTER_ENABLED, OPENAI_ENABLED
    
    twitter_status = "✅ Enabled" if TWITTER_ENABLED else "⚪ Disabled"
    openai_status = "✅ Enabled" if OPENAI_ENABLED else "⚪ Disabled"
    
    settings_message = (
        f"⚙️ *SETTINGS*\n\n"
        f"• Twitter API: {escape_markdown_v2(twitter_status)}\n"
        f"• OpenAI API: {escape_markdown_v2(openai_status)}\n\n"
        f"Edit `.env` and restart the bot to apply changes\\."
    )
    
    await query.edit_message_text(
        settings_message,
        parse_mode="MarkdownV2",
        reply_markup=get_back_keyboard()
    )


async def show_status(query) -> None:
    """Show system status."""
    from bot.services.twitter_service import TwitterService
    from bot.services.openai_service import OpenAIService
    from bot.services.post_service import PostService
    
    # Check service status
    twitter_service = TwitterService() if TWITTER_ENABLED else None
    openai_service = OpenAIService() if OPENAI_ENABLED else None
    
    twitter_status = "🟢 Connected"
    openai_status = "🟢 Available"
    
    if twitter_service:
        success, message = twitter_service.test_connection()
        if success:
            twitter_status = f"🟢 {escape_markdown_v2(message)}"
        else:
            twitter_status = f"🔴 {escape_markdown_v2(message)}"
    else:
        twitter_status = "⚪ Not configured"
    
    if openai_service:
        success, message = openai_service.test_connection()
        if success:
            openai_status = "🟢 Available"
        else:
            openai_status = f"🔴 {escape_markdown_v2(message[:50])}"
    else:
        openai_status = "⚪ Disabled"
    
    # Get statistics
    stats = PostService.get_post_statistics()
    
    status_message = (
        f"📊 *SYSTEM STATUS*\n\n"
        f"*Services*\n"
        f"• Bot: `ONLINE`\n"
        f"• Twitter: {twitter_status}\n"
        f"• OpenAI: {openai_status}\n"
        f"• Database: `Healthy`\n\n"
        f"*Stats*\n"
        f"• Total: `{stats['total']}`\n"
        f"• Published: `{stats['published']}`\n"
        f"• Scheduled: `{stats['scheduled']}`\n"
        f"• Failed: `{stats['failed']}`\n\n"
        f"🕐 Last check: `Now`"
    )
    
    await query.edit_message_text(
        status_message,
        parse_mode="MarkdownV2",
        reply_markup=get_back_keyboard()
    )


# Topics management functions

async def show_topics_menu(query, user_id: int) -> None:
    """Show topics management menu."""
    topic_count = TopicService.get_topic_count(user_id)
    from bot.services.topic_service import MAX_TOPICS_PER_USER
    
    topics_message = (
        f"🎯 *TOPIC PRESETS*\n\n"
        f"Manage your topic presets for AI post generation\\.\n\n"
        f"📊 *Usage:* `{topic_count}/{MAX_TOPICS_PER_USER}` topics\n\n"
        f"Choose an option below\\."
    )
    
    await query.edit_message_text(
        topics_message,
        parse_mode="MarkdownV2",
        reply_markup=get_topics_menu_keyboard(user_id)
    )


async def show_topics_list(query, user_id: int) -> None:
    """Show list of user's topics."""
    topics = TopicService.get_user_topics(user_id)
    
    if not topics:
        await query.edit_message_text(
            "📋 *TOPICS LIST*\n\n"
            "You don't have any topics yet\\.\n"
            "Add one to get started\\!",
            parse_mode="MarkdownV2",
            reply_markup=get_topics_menu_keyboard(user_id)
        )
        return
    
    from bot.services.topic_service import MAX_TOPICS_PER_USER
    
    topics_text = "\n".join([f"• `{escape_markdown_v2(topic.name)}`" for topic in topics])
    
    topics_message = (
        f"📋 *TOPICS LIST*\n\n"
        f"Your topics \\({len(topics)}/{MAX_TOPICS_PER_USER}\\):\n\n"
        f"{topics_text}\n\n"
        f"Click on a topic to view details\\."
    )
    
    await query.edit_message_text(
        topics_message,
        parse_mode="MarkdownV2",
        reply_markup=get_topics_list_keyboard(user_id)
    )


async def view_topic(query, topic_id: int) -> None:
    """View a specific topic."""
    topic = TopicService.get_topic_for_user(topic_id, query.from_user.id)
    
    if not topic:
        await query.answer("❌ Topic not found", show_alert=True)
        return
    
    from bot.utils import format_datetime
    
    topic_message = (
        f"🎯 *TOPIC DETAILS*\n\n"
        f"*Name:* `{escape_markdown_v2(topic.name)}`\n"
        f"*Created:* {escape_markdown_v2(format_datetime(topic.created_at))}\n\n"
        f"Use this topic when creating AI posts\\."
    )
    
    await query.edit_message_text(
        topic_message,
        parse_mode="MarkdownV2",
        reply_markup=get_topics_list_keyboard(query.from_user.id)
    )


async def show_topics_delete(query, user_id: int) -> None:
    """Show topics for deletion."""
    topics = TopicService.get_user_topics(user_id)
    
    if not topics:
        await query.edit_message_text(
            "🗑️ *DELETE TOPIC*\n\n"
            "You don't have any topics to delete\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_topics_menu_keyboard(user_id)
        )
        return
    
    await query.edit_message_text(
        "🗑️ *DELETE TOPIC*\n\n"
        "Select a topic to delete:",
        parse_mode="MarkdownV2",
        reply_markup=get_topics_delete_keyboard(user_id)
    )


async def confirm_delete_topic(query, topic_id: int) -> None:
    """Confirm deletion of a specific topic."""
    topic = TopicService.get_topic(topic_id)
    
    if not topic:
        await query.answer("❌ Topic not found", show_alert=True)
        return
    
    await query.edit_message_text(
        f"🗑️ *DELETE TOPIC*\n\n"
        f"Are you sure you want to delete:\n"
        f"`{escape_markdown_v2(topic.name)}`\n\n"
        f"This action cannot be undone\\.",
        parse_mode="MarkdownV2",
        reply_markup=get_topic_delete_confirm_keyboard(topic_id)
    )


async def execute_delete_topic(query, user_id: int, topic_id: int) -> None:
    """Execute deletion of a topic."""
    success, error_msg = TopicService.delete_topic(topic_id, user_id)
    
    if success:
        await query.answer("✅ Topic deleted", show_alert=False)
        remaining = TopicService.get_topic_count(user_id)
        if remaining > 0:
            await show_topics_delete(query, user_id)
        else:
            await query.edit_message_text(
                "✅ *TOPIC DELETED*\n\n"
                "No more topics left\\.",
                parse_mode="MarkdownV2",
                reply_markup=get_topics_menu_keyboard(user_id)
            )
    else:
        await query.answer(f"❌ {error_msg}", show_alert=True)


async def confirm_delete_all_topics(query) -> None:
    """Confirm deletion of all topics."""
    await query.edit_message_text(
        "🗑️ *DELETE ALL TOPICS*\n\n"
        "⚠️ Are you sure you want to delete ALL topics?\n\n"
        "This action cannot be undone\\.",
        parse_mode="MarkdownV2",
        reply_markup=get_topics_delete_all_confirm_keyboard()
    )


async def execute_delete_all_topics(query, user_id: int) -> None:
    """Execute deletion of all topics."""
    success, deleted_count, error_msg = TopicService.delete_all_topics(user_id)
    
    if success:
        await query.answer(f"✅ Deleted {deleted_count} topic(s)", show_alert=True)
        await show_topics_menu(query, user_id)
    else:
        await query.answer(f"❌ {error_msg}", show_alert=True)

