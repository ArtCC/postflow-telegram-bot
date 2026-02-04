"""
Callback Handlers
Central router for all inline button callbacks.
"""

from telegram import Update
from telegram.ext import ContextTypes

from bot.config import logger, TWITTER_ENABLED, OPENAI_ENABLED
from bot.utils import is_authorized, escape_markdown_v2, get_main_menu_keyboard, get_back_keyboard, get_new_post_keyboard
from bot.handlers.commands import help_command


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
    
    elif data == "scheduled":
        from bot.handlers.posts import show_scheduled_posts
        await show_scheduled_posts(query, context)
    
    elif data == "statistics":
        await show_statistics(query)
    
    elif data == "settings":
        await show_settings(query)
    
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
    
    elif data == "post_ai":
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
        "• `/help` \\- Help\n"
        "• `/menu` \\- Main menu\n"
        "• `/status` \\- System status\n\n"
        "*Highlights*\n"
        "• Manual or AI posts\n"
        "• Scheduling\n"
        "• Threads for long posts"
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
