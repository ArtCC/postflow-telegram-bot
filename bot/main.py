#!/usr/bin/env python3
"""
PostFlow Telegram Bot
Main entry point for the bot application.
"""

import signal
import sys
from datetime import datetime, timedelta
import pytz
from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from bot.config import logger, TELEGRAM_BOT_TOKEN
from bot.database import init_db
from bot.handlers import (
    start_command,
    help_command,
    menu_command,
    chatid_command,
    status_command,
    handle_callback,
)
from bot.handlers.posts import handle_text_message, publish_scheduled_post
from bot.handlers.conversations import cancel_command
from bot.services.scheduler_service import SchedulerService
from bot.services.post_service import PostService


# Global application instance for graceful shutdown
app_instance = None


async def setup_bot_commands(application: Application) -> None:
    """Set up bot commands in Telegram UI."""
    commands = [
        BotCommand("start", "Welcome message and authorization check"),
        BotCommand("help", "Show help and available commands"),
        BotCommand("menu", "Show main menu"),
        BotCommand("status", "Check bot and API status"),
        BotCommand("chatid", "Show your Telegram User ID"),
        BotCommand("cancel", "Cancel current operation"),
    ]
    
    await application.bot.set_my_commands(commands)
    logger.info("Bot commands configured")


async def error_handler(update: object, context) -> None:
    """Handle errors in the bot."""
    logger.error(f"Exception while handling an update: {context.error}")
    
    # Optionally notify user
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "❌ *ERROR*\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "An unexpected error occurred\\.\n\n"
                "Please try again or use /menu\\.",
                parse_mode="MarkdownV2"
            )
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}. Shutting down gracefully...")
    
    if app_instance and app_instance.running:
        # Stop the bot
        import asyncio
        loop = asyncio.get_event_loop()
        loop.create_task(app_instance.stop())
    
    sys.exit(0)


def rehydrate_scheduled_posts(application: Application) -> None:
    """Recreate scheduler jobs from persisted scheduled posts."""
    scheduler_service = application.bot_data.get("scheduler_service")
    if not scheduler_service:
        logger.warning("Scheduler service not available; skipping rehydration")
        return

    scheduled = PostService.get_scheduled_posts()
    if not scheduled:
        logger.info("No scheduled posts to rehydrate")
        return

    now_utc = datetime.utcnow().replace(tzinfo=pytz.UTC)
    restored = 0

    for post, sched in scheduled:
        scheduled_for = sched.scheduled_for
        if scheduled_for.tzinfo is None:
            scheduled_for = pytz.UTC.localize(scheduled_for)

        run_time = scheduled_for
        if run_time <= now_utc:
            run_time = now_utc + timedelta(seconds=5)

        job_id = scheduler_service.schedule_post(
            post.id,
            run_time,
            publish_scheduled_post,
            post.id,
            bot=application.bot,
            job_id=sched.job_id
        )

        if job_id:
            restored += 1
            if job_id != sched.job_id:
                PostService.update_scheduled_job_id(post.id, job_id)

    logger.info(f"Rehydrated {restored} scheduled post(s)")


def main() -> None:
    """Start the bot."""
    global app_instance
    
    logger.info("Starting PostFlow Telegram Bot...")
    
    # Initialize database
    try:
        init_db()
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        sys.exit(1)
    
    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app_instance = application
    
    # Set up bot commands
    application.post_init = setup_bot_commands

    # Initialize scheduler service and rehydrate pending jobs
    application.bot_data["scheduler_service"] = SchedulerService()
    rehydrate_scheduled_posts(application)
    
    # Register command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("chatid", chatid_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    
    # Register callback handler (for inline buttons)
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Register message handlers
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_text_message
        )
    )
    
    # Register error handler
    application.add_error_handler(error_handler)
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start the bot
    logger.info("Bot is running... Press Ctrl+C to stop.")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,  # Ignore old updates on restart
    )


if __name__ == "__main__":
    main()
