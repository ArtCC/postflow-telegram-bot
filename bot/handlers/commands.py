"""
Command Handlers
Basic bot commands (start, help, menu, chatid, status).
"""

from telegram import Update
from telegram.ext import ContextTypes

from bot.config import logger, TELEGRAM_USER_ID, TWITTER_ENABLED, OPENAI_ENABLED
from bot.utils import is_authorized, escape_markdown_v2, get_main_menu_keyboard, get_back_keyboard, get_new_post_keyboard, get_topics_menu_keyboard, get_user_locale, t
from bot.services.post_service import PostService
from bot.services.twitter_service import TwitterService
from bot.services.openai_service import OpenAIService
from bot.services.topic_service import TopicService


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    user_id = update.effective_user.id
    locale = get_user_locale(update.effective_user)
    user_name = update.effective_user.first_name or t("common.user_fallback", locale)
    
    logger.info(f"Start command received from user ID: {user_id}")
    
    is_auth = is_authorized(user_id)
    auth_status = t(
        "start.auth_status_authorized",
        locale,
    ) if is_auth else t("start.auth_status_unauthorized", locale)
    welcome_message = t(
        "start.welcome",
        locale,
        user_name=escape_markdown_v2(user_name),
        auth_status=auth_status,
    )
    
    if is_auth:
        await update.message.reply_text(
            welcome_message,
            parse_mode="MarkdownV2",
            reply_markup=get_main_menu_keyboard(locale)
        )
    else:
        unauthorized_message = f"{welcome_message}\n\n{t('start.unauthorized_suffix', locale, user_id=user_id)}"
        await update.message.reply_text(
            unauthorized_message,
            parse_mode="MarkdownV2"
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    user_id = update.effective_user.id
    locale = get_user_locale(update.effective_user)
    
    if not is_authorized(user_id):
        await update.message.reply_text(
            t("errors.not_authorized_md", locale),
            parse_mode="MarkdownV2"
        )
        return

    help_message = t("help.message", locale)
    
    await update.message.reply_text(
        help_message,
        parse_mode="MarkdownV2",
        reply_markup=get_back_keyboard(locale)
    )


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /menu command."""
    user_id = update.effective_user.id
    locale = get_user_locale(update.effective_user)
    
    if not is_authorized(user_id):
        await update.message.reply_text(
            t("errors.not_authorized_md", locale),
            parse_mode="MarkdownV2"
        )
        return

    menu_message = f"{t('menu.title', locale)}\n\n{t('menu.select_option', locale)}"
    
    await update.message.reply_text(
        menu_message,
        parse_mode="MarkdownV2",
        reply_markup=get_main_menu_keyboard(locale)
    )


async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /new command."""
    user_id = update.effective_user.id
    locale = get_user_locale(update.effective_user)

    if not is_authorized(user_id):
        await update.message.reply_text(
            t("errors.not_authorized_md", locale),
            parse_mode="MarkdownV2"
        )
        return

    message = f"{t('new_post.title', locale)}\n\n{t('new_post.choose_method', locale)}"

    await update.message.reply_text(
        message,
        parse_mode="MarkdownV2",
        reply_markup=get_new_post_keyboard(locale)
    )


async def plan_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /plan command."""
    user_id = update.effective_user.id
    locale = get_user_locale(update.effective_user)

    if not is_authorized(user_id):
        await update.message.reply_text(
            t("errors.not_authorized_md", locale),
            parse_mode="MarkdownV2"
        )
        return

    from bot.handlers.posts import start_weekly_plan

    await start_weekly_plan(update.message, context)


async def chatid_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /chatid command."""
    user_id = update.effective_user.id
    locale = get_user_locale(update.effective_user)
    user_name = update.effective_user.first_name or t("common.user_fallback", locale)
    
    chat_id_message = t(
        "chatid.message",
        locale,
        user_name=escape_markdown_v2(user_name),
        user_id=user_id,
    )
    
    await update.message.reply_text(
        chat_id_message,
        parse_mode="MarkdownV2",
        reply_markup=get_back_keyboard(locale)
    )


async def author_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /author command."""
    user_id = update.effective_user.id
    locale = get_user_locale(update.effective_user)

    if not is_authorized(user_id):
        await update.message.reply_text(
            t("errors.not_authorized_md", locale),
            parse_mode="MarkdownV2"
        )
        return

    author_message = t(
        "author.message",
        locale,
        github_url=escape_markdown_v2("https://github.com/ArtCC"),
    )

    await update.message.reply_text(
        author_message,
        parse_mode="MarkdownV2",
        reply_markup=get_back_keyboard(locale)
    )


async def drafts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /drafts command."""
    user_id = update.effective_user.id
    locale = get_user_locale(update.effective_user)

    if not is_authorized(user_id):
        await update.message.reply_text(
            t("errors.not_authorized_md", locale),
            parse_mode="MarkdownV2"
        )
        return

    from bot.handlers.posts import build_drafts_list

    message, keyboard = build_drafts_list(page=0, locale=locale)
    await update.message.reply_text(
        message,
        parse_mode="MarkdownV2",
        reply_markup=keyboard
    )


async def scheduled_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /scheduled command."""
    user_id = update.effective_user.id
    locale = get_user_locale(update.effective_user)

    if not is_authorized(user_id):
        await update.message.reply_text(
            t("errors.not_authorized_md", locale),
            parse_mode="MarkdownV2"
        )
        return

    from bot.handlers.posts import build_scheduled_posts_list

    message, keyboard = build_scheduled_posts_list(page=0, locale=locale)
    await update.message.reply_text(
        message,
        parse_mode="MarkdownV2",
        reply_markup=keyboard
    )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /stats command."""
    user_id = update.effective_user.id
    locale = get_user_locale(update.effective_user)

    if not is_authorized(user_id):
        await update.message.reply_text(
            t("errors.not_authorized_md", locale),
            parse_mode="MarkdownV2"
        )
        return

    stats = PostService.get_post_statistics()

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

    await update.message.reply_text(
        stats_message,
        parse_mode="MarkdownV2",
        reply_markup=get_back_keyboard(locale)
    )


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /settings command."""
    user_id = update.effective_user.id
    locale = get_user_locale(update.effective_user)

    if not is_authorized(user_id):
        await update.message.reply_text(
            t("errors.not_authorized_md", locale),
            parse_mode="MarkdownV2"
        )
        return

    twitter_status = t("settings.enabled", locale) if TWITTER_ENABLED else t("settings.disabled", locale)
    openai_status = t("settings.enabled", locale) if OPENAI_ENABLED else t("settings.disabled", locale)

    settings_message = t(
        "settings.message",
        locale,
        twitter_status=escape_markdown_v2(twitter_status),
        openai_status=escape_markdown_v2(openai_status),
    )

    await update.message.reply_text(
        settings_message,
        parse_mode="MarkdownV2",
        reply_markup=get_back_keyboard(locale)
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command."""
    user_id = update.effective_user.id
    locale = get_user_locale(update.effective_user)
    
    if not is_authorized(user_id):
        await update.message.reply_text(
            t("errors.not_authorized_md", locale),
            parse_mode="MarkdownV2"
        )
        return
    
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
    
    await update.message.reply_text(
        status_message,
        parse_mode="MarkdownV2",
        reply_markup=get_back_keyboard(locale)
    )


async def topics_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /topics command."""
    user_id = update.effective_user.id
    locale = get_user_locale(update.effective_user)
    
    if not is_authorized(user_id):
        await update.message.reply_text(
                t("errors.not_authorized_md", locale),
            parse_mode="MarkdownV2"
        )
        return
    
    # Check if OpenAI is enabled
    if not OPENAI_ENABLED:
        await update.message.reply_text(
            t("topics.openai_required", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(locale)
        )
        return
    
    # Get topics count
    topic_count = TopicService.get_topic_count(user_id)
    from bot.services.topic_service import MAX_TOPICS_PER_USER
    
    topics_message = t(
        "topics.menu",
        locale,
        count=topic_count,
        max=MAX_TOPICS_PER_USER,
    )
    
    await update.message.reply_text(
        topics_message,
        parse_mode="MarkdownV2",
        reply_markup=get_topics_menu_keyboard(user_id, locale)
    )

