"""
Command Handlers
Basic bot commands (start, help, menu, chatid, status).
"""

from telegram import Update
from telegram.ext import ContextTypes

from bot.config import logger, TELEGRAM_USER_ID, TWITTER_ENABLED, OPENAI_ENABLED
from bot.utils import is_authorized, escape_markdown_v2, get_main_menu_keyboard, get_back_keyboard
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
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✍️ *POSTFLOW BOT*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👋 Welcome *{escape_markdown_v2(user_name)}*\\!\n\n"
        f"Manage and schedule your social\n"
        f"media posts with AI support\\.\n\n"
        f"┏━━━━━━━━━━━━━━━━━━━━┓\n"
        f"  🔑 *Authorization*\n"
        f"     {auth_emoji} {'`AUTHORIZED`' if is_auth else '`NOT AUTHORIZED`'}\n"
        f"┗━━━━━━━━━━━━━━━━━━━━┛\n\n"
        f"💡 Use the menu below to get started\\!"
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
            f"⚠️ *Your User ID:* `{user_id}`\n\n"
            f"Add this ID to `TELEGRAM\\_USER\\_ID`\n"
            f"in your `.env` file to gain access\\."
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
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "ℹ️ *HELP & COMMANDS*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "*Basic Commands:*\n"
        "• `/start` \\- Welcome message\n"
        "• `/help` \\- Show this help\n"
        "• `/menu` \\- Show main menu\n"
        "• `/status` \\- Check bot status\n"
        "• `/chatid` \\- Show your chat ID\n\n"
        "*Features:*\n"
        "✍️ Create posts manually\n"
        "🤖 Generate posts with AI\n"
        "📅 Schedule posts for later\n"
        "🧵 Auto\\-create threads\n"
        "📊 View statistics\n\n"
        "*How it works:*\n"
        "1\\. Click 'New Post' in menu\n"
        "2\\. Choose manual or AI\n"
        "3\\. Preview your post\n"
        "4\\. Publish now or schedule\n\n"
        "💡 *Tip:* Posts over 280 chars\n"
        "   are automatically split into\n"
        "   threads\\!"
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
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🎯 *POSTFLOW MENU*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Select an option below:"
    )
    
    await update.message.reply_text(
        menu_message,
        parse_mode="MarkdownV2",
        reply_markup=get_main_menu_keyboard()
    )


async def chatid_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /chatid command."""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "User"
    
    chat_id_message = (
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔑 *YOUR USER ID*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 *User:* {escape_markdown_v2(user_name)}\n"
        f"🆔 *User ID:* `{user_id}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💡 *Usage:*\n\n"
        f"Add this ID to the\n"
        f"`TELEGRAM\\_USER\\_ID` variable\n"
        f"in your `.env` file\\.\n\n"
        f"Example:\n"
        f"`TELEGRAM\\_USER\\_ID={user_id}`\n\n"
        f"⚠️ Keep this ID private\\!"
    )
    
    await update.message.reply_text(
        chat_id_message,
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
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 *SYSTEM STATUS*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🤖 *Bot:* `ONLINE`\n"
        f"🐦 *Twitter:* {twitter_status}\n"
        f"🤖 *OpenAI:* {openai_status}\n"
        f"💾 *Database:* `Healthy`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 *Statistics:*\n"
        f"   • Total posts: `{stats['total']}`\n"
        f"   • Published: `{stats['published']}`\n"
        f"   • Scheduled: `{stats['scheduled']}`\n"
        f"   • Failed: `{stats['failed']}`\n\n"
        f"🕐 Last check: `Now`"
    )
    
    await update.message.reply_text(
        status_message,
        parse_mode="MarkdownV2",
        reply_markup=get_back_keyboard()
    )
