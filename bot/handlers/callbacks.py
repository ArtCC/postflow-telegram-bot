"""
Callback Handlers
Central router for all inline button callbacks.
"""

from telegram import Update
from telegram.ext import ContextTypes

from bot.config import logger
from bot.utils import is_authorized, escape_markdown_v2, get_main_menu_keyboard, get_back_keyboard, get_new_post_keyboard
from bot.handlers.commands import help_command, status_command


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
        # Reuse status_command logic
        await status_command(update, context)
    
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
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "✏️ *WRITE POST*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📝 Type your post content:\n\n"
            "💡 Tips:\n"
            "   • Max 280 chars for single tweet\n"
            "   • Longer = auto thread\n"
            "   • Type /cancel to abort",
            parse_mode="MarkdownV2"
        )
        context.user_data['awaiting'] = 'manual_post'
    
    elif data == "post_ai":
        await query.edit_message_text(
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🤖 *AI GENERATION*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "💡 Describe what you want to post:\n\n"
            "Examples:\n"
            "• 'Post about Python advantages'\n"
            "• 'Thread on AI trends in 2026'\n"
            "• 'Motivational Monday post'\n\n"
            "Type /cancel to abort",
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
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🎯 *POSTFLOW MENU*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Select an option below:"
    )
    
    await query.edit_message_text(
        menu_message,
        parse_mode="MarkdownV2",
        reply_markup=get_main_menu_keyboard()
    )


async def show_help(query) -> None:
    """Show help information."""
    help_message = (
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "ℹ️ *HELP & COMMANDS*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "*Basic Commands:*\n"
        "• `/start` \\- Welcome message\n"
        "• `/help` \\- Show this help\n"
        "• `/menu` \\- Show main menu\n"
        "• `/status` \\- Check bot status\n\n"
        "*Features:*\n"
        "✍️ Create posts manually\n"
        "🤖 Generate posts with AI\n"
        "📅 Schedule posts for later\n"
        "🧵 Auto\\-create threads\n\n"
        "💡 Posts over 280 chars\n"
        "   are automatically split\\!"
    )
    
    await query.edit_message_text(
        help_message,
        parse_mode="MarkdownV2",
        reply_markup=get_back_keyboard()
    )


async def show_new_post_options(query) -> None:
    """Show new post creation options."""
    message = (
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "✍️ *CREATE NEW POST*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Choose creation method:"
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
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 *STATISTICS*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📝 *Posts Overview:*\n"
        f"   • Total: `{stats['total']}`\n"
        f"   • Published: `{stats['published']}`\n"
        f"   • Scheduled: `{stats['scheduled']}`\n"
        f"   • Draft: `{stats['draft']}`\n"
        f"   • Failed: `{stats['failed']}`\n\n"
        f"📈 *Performance:*\n"
        f"   • Success Rate: `{success_rate:.1f}%`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 Keep posting consistently\\!"
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
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚙️ *SETTINGS*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🐦 Twitter API: {escape_markdown_v2(twitter_status)}\n"
        f"🤖 OpenAI API: {escape_markdown_v2(openai_status)}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💡 Settings are configured via\n"
        f"   the `.env` file\\.\n\n"
        f"🔧 To change settings:\n"
        f"   1\\. Edit `.env` file\n"
        f"   2\\. Restart the bot container"
    )
    
    await query.edit_message_text(
        settings_message,
        parse_mode="MarkdownV2",
        reply_markup=get_back_keyboard()
    )
