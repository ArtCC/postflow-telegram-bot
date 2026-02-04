"""
Command Handlers
Basic bot commands (start, help, menu, chatid, status).
"""

from telegram import Update
from telegram.ext import ContextTypes

from bot.config import logger, TELEGRAM_USER_ID, TWITTER_ENABLED, OPENAI_ENABLED
from bot.utils import is_authorized, escape_markdown_v2, get_main_menu_keyboard, get_back_keyboard, get_new_post_keyboard
from bot.services.post_service import PostService
from bot.services.twitter_service import TwitterService
from bot.services.openai_service import OpenAIService


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "User"
    
    logger.info(f"Start command received from user ID: {user_id}")
    
    is_auth = is_authorized(user_id)
    auth_emoji = "✅" if is_auth else "⚠️"
    
    welcome_message = (
        f"✍️ *POSTFLOW*\n\n"
        f"👋 Hi *{escape_markdown_v2(user_name)}*\\!\n"
        f"Create, schedule, and publish posts\\.\n\n"
        f"🔐 *Authorization*\n"
        f"• Status: {auth_emoji} {'`AUTHORIZED`' if is_auth else '`NOT AUTHORIZED`'}\n\n"
        f"Choose an option below\\."
    )
    
    if is_auth:
        await update.message.reply_text(
            welcome_message,
            parse_mode="MarkdownV2",
            reply_markup=get_main_menu_keyboard()
        )
    else:
        unauthorized_message = (
            f"{welcome_message}\n\n"
            f"⚠️ *Your User ID:* `{user_id}`\n"
            f"Add it to `TELEGRAM\\_USER\\_ID` in `.env`\\."
        )
        await update.message.reply_text(
            unauthorized_message,
            parse_mode="MarkdownV2"
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    user_id = update.effective_user.id
    
    if not is_authorized(user_id):
        await update.message.reply_text(
            "⛔ You are not authorized to use this bot\\.",
            parse_mode="MarkdownV2"
        )
        return
    
    help_message = (
        "ℹ️ *HELP*\n\n"
        "*Commands*\n"
        "• `/start` \\- Welcome\n"
        "• `/menu` \\- Main menu\n"
        "• `/new` \\- New post\n"
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
        "• Scheduling\n"
        "• Threads for long posts\n"
        "• Stats overview"
    )
    
    await update.message.reply_text(
        help_message,
        parse_mode="MarkdownV2",
        reply_markup=get_back_keyboard()
    )


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /menu command."""
    user_id = update.effective_user.id
    
    if not is_authorized(user_id):
        await update.message.reply_text(
            "⛔ You are not authorized to use this bot\\.",
            parse_mode="MarkdownV2"
        )
        return
    
    menu_message = (
        "🎯 *MENU*\n\n"
        "Select an option:"
    )
    
    await update.message.reply_text(
        menu_message,
        parse_mode="MarkdownV2",
        reply_markup=get_main_menu_keyboard()
    )


async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /new command."""
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text(
            "⛔ You are not authorized to use this bot\.",
            parse_mode="MarkdownV2"
        )
        return

    message = (
        "✍️ *NEW POST*\n\n"
        "Choose a method:"
    )

    await update.message.reply_text(
        message,
        parse_mode="MarkdownV2",
        reply_markup=get_new_post_keyboard()
    )


async def chatid_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /chatid command."""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "User"
    
    chat_id_message = (
        f"🔑 *YOUR USER ID*\n\n"
        f"• User: {escape_markdown_v2(user_name)}\n"
        f"• ID: `{user_id}`\n\n"
        f"Add it to `TELEGRAM\\_USER\\_ID` in `.env`\\."
    )
    
    await update.message.reply_text(
        chat_id_message,
        parse_mode="MarkdownV2",
        reply_markup=get_back_keyboard()
    )


async def author_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /author command."""
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text(
            "⛔ You are not authorized to use this bot\.",
            parse_mode="MarkdownV2"
        )
        return

    author_message = (
        "👤 *AUTHOR*\n\n"
        f"• GitHub: {escape_markdown_v2('https://github.com/ArtCC')}"
    )

    await update.message.reply_text(
        author_message,
        parse_mode="MarkdownV2",
        reply_markup=get_back_keyboard()
    )


async def drafts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /drafts command."""
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text(
            "⛔ You are not authorized to use this bot\.",
            parse_mode="MarkdownV2"
        )
        return

    from bot.handlers.posts import build_drafts_list

    message, keyboard = build_drafts_list(page=0)
    await update.message.reply_text(
        message,
        parse_mode="MarkdownV2",
        reply_markup=keyboard
    )


async def scheduled_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /scheduled command."""
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text(
            "⛔ You are not authorized to use this bot\.",
            parse_mode="MarkdownV2"
        )
        return

    from bot.handlers.posts import build_scheduled_posts_list

    message, keyboard = build_scheduled_posts_list(page=0)
    await update.message.reply_text(
        message,
        parse_mode="MarkdownV2",
        reply_markup=keyboard
    )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /stats command."""
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text(
            "⛔ You are not authorized to use this bot\.",
            parse_mode="MarkdownV2"
        )
        return

    stats = PostService.get_post_statistics()

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

    await update.message.reply_text(
        stats_message,
        parse_mode="MarkdownV2",
        reply_markup=get_back_keyboard()
    )


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /settings command."""
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text(
            "⛔ You are not authorized to use this bot\.",
            parse_mode="MarkdownV2"
        )
        return

    twitter_status = "✅ Enabled" if TWITTER_ENABLED else "⚪ Disabled"
    openai_status = "✅ Enabled" if OPENAI_ENABLED else "⚪ Disabled"

    settings_message = (
        f"⚙️ *SETTINGS*\n\n"
        f"• Twitter API: {escape_markdown_v2(twitter_status)}\n"
        f"• OpenAI API: {escape_markdown_v2(openai_status)}\n\n"
        f"Edit `.env` and restart the bot to apply changes\."
    )

    await update.message.reply_text(
        settings_message,
        parse_mode="MarkdownV2",
        reply_markup=get_back_keyboard()
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command."""
    user_id = update.effective_user.id
    
    if not is_authorized(user_id):
        await update.message.reply_text(
            "⛔ You are not authorized to use this bot\\.",
            parse_mode="MarkdownV2"
        )
        return
    
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
    
    await update.message.reply_text(
        status_message,
        parse_mode="MarkdownV2",
        reply_markup=get_back_keyboard()
    )
