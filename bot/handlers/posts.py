"""
Post Handlers
Handlers for creating, publishing, and managing posts.
"""

from datetime import datetime, timedelta, date
from typing import Optional
from telegram import Update
from telegram.ext import ContextTypes

from bot.config import logger, MAX_TWEET_LENGTH, USER_TIMEZONE, TZ, TELEGRAM_USER_ID, MEDIA_PATH
from bot.utils import (
    is_authorized,
    escape_markdown_v2,
    format_datetime,
    format_relative_time,
    split_into_tweets,
    truncate_text,
    get_post_preview_keyboard,
    get_schedule_keyboard,
    get_scheduled_posts_keyboard,
    get_scheduled_post_actions_keyboard,
    get_confirm_delete_keyboard,
    get_error_keyboard,
    get_back_keyboard,
    get_drafts_keyboard,
    get_weekly_calendar_keyboard,
    get_weekday_selection_keyboard,
    get_posts_per_day_keyboard,
    get_plan_post_mode_keyboard,
    get_plan_confirm_keyboard,
    get_user_locale,
    t,
)
from bot.services.post_service import PostService
from bot.services.twitter_service import TwitterService
from bot.services.openai_service import OpenAIService
from bot.services.scheduler_service import SchedulerService
from bot.services.topic_service import TopicService
from bot.services.template_service import TemplateService
from bot.database import PostStatus
import pytz
import os
from pathlib import Path


# Initialize services (singleton pattern)
twitter_service = TwitterService()
openai_service = OpenAIService()


def get_scheduler_service(context: ContextTypes.DEFAULT_TYPE) -> Optional[SchedulerService]:
    """Get scheduler service from application bot data."""
    return context.application.bot_data.get("scheduler_service")


async def publish_scheduled_post(post_id: int, bot=None) -> None:
    """Publish a scheduled post when the scheduler fires."""
    post = PostService.get_post(post_id)
    if not post or post.status != PostStatus.SCHEDULED:
        logger.info(f"Skipping scheduled publish for post {post_id}: not scheduled")
        return

    if post.media_path:
        if post.is_thread():
            media_thread_error = t("errors.media_posts_cannot_be_threads")
            PostService.update_post_status(post_id, PostStatus.FAILED, error_message=media_thread_error)
            await notify_scheduled_post_result(bot, post_id, False, error=media_thread_error)
            return

        success, tweet_id, error = twitter_service.post_tweet_with_media(post.content, post.media_path)
        if success:
            PostService.update_post_status(post_id, PostStatus.PUBLISHED, twitter_id=tweet_id)
            await notify_scheduled_post_result(bot, post_id, True, tweet_id=tweet_id)
        else:
            PostService.update_post_status(post_id, PostStatus.FAILED, error_message=error)
            await notify_scheduled_post_result(bot, post_id, False, error=error)

        if os.path.exists(post.media_path):
            try:
                os.remove(post.media_path)
            except OSError as e:
                logger.warning(f"Failed to remove media file {post.media_path}: {e}")
        return

    if post.is_thread():
        tweets = split_into_tweets(post.content)
        success, tweet_ids, error = twitter_service.post_thread(tweets)
        if success:
            PostService.update_post_status(
                post_id,
                PostStatus.PUBLISHED,
                twitter_id=tweet_ids[0] if tweet_ids else None
            )
            await notify_scheduled_post_result(
                bot,
                post_id,
                True,
                tweet_id=tweet_ids[0] if tweet_ids else None,
                is_thread=True
            )
        else:
            PostService.update_post_status(post_id, PostStatus.FAILED, error_message=error)
            await notify_scheduled_post_result(bot, post_id, False, error=error, is_thread=True)
    else:
        success, tweet_id, error = twitter_service.post_tweet(post.content)
        if success:
            PostService.update_post_status(post_id, PostStatus.PUBLISHED, twitter_id=tweet_id)
            await notify_scheduled_post_result(bot, post_id, True, tweet_id=tweet_id)
        else:
            PostService.update_post_status(post_id, PostStatus.FAILED, error_message=error)
            await notify_scheduled_post_result(bot, post_id, False, error=error)


async def notify_scheduled_post_result(bot, post_id: int, success: bool, tweet_id: str = None, error: str = None, is_thread: bool = False) -> None:
    """Send notification to user about scheduled post result."""
    try:
        if success:
            tweet_url = f"https://twitter.com/i/web/status/{tweet_id}" if tweet_id else ""
            post_type = t("posts.type_thread") if is_thread else t("posts.type_post")
            message = t(
                "scheduled.notify_success",
                post_type=post_type.upper(),
                post_id=post_id,
                tweet_url=escape_markdown_v2(tweet_url),
            )
        else:
            message = t(
                "scheduled.notify_failed",
                post_id=post_id,
                error=escape_markdown_v2(error or t("errors.unknown_error")),
            )
        
        await bot.send_message(
            chat_id=TELEGRAM_USER_ID,
            text=message,
            parse_mode="MarkdownV2",
            disable_web_page_preview=True
        )
        logger.info(f"Notification sent for post {post_id} (success={success})")
    except Exception as e:
        logger.error(f"Failed to send notification for post {post_id}: {e}")


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages based on current context."""
    user_id = update.effective_user.id
    locale = get_user_locale(update.effective_user)
    
    if not is_authorized(user_id):
        return
    
    text = update.message.text
    awaiting = context.user_data.get('awaiting')
    
    if awaiting == 'image_caption':
        await process_image_caption(update, context, text)
    elif awaiting == 'weekly_times':
        await process_weekly_times(update, context, text)
    elif awaiting == 'weekly_manual_content':
        await process_weekly_manual_content(update, context, text)
    elif awaiting == 'weekly_ai_prompt':
        await process_weekly_ai_prompt(update, context, text)
    elif awaiting == 'manual_post':
        await process_manual_post(update, context, text)
    elif awaiting == 'ai_prompt':
        await process_ai_prompt(update, context, text)
    elif awaiting == 'custom_schedule':
        await process_custom_schedule(update, context, text)
    elif awaiting == 'edit_post':
        await process_edit_post(update, context, text)
    elif awaiting == 'reschedule':
        await process_reschedule(update, context, text)
    else:
        # No specific action expected, show helpful message
        await update.message.reply_text(
            t("menu.help", locale),
            reply_markup=get_back_keyboard(locale)
        )


async def handle_photo_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle photo messages for image posts."""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        return

    locale = get_user_locale(update.effective_user)

    awaiting = context.user_data.get('awaiting')
    if awaiting != 'image_post':
        await update.message.reply_text(
            t("posts.image_use_new", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(locale)
        )
        return

    if not update.message.photo:
        await update.message.reply_text(
            t("posts.image_no_received", locale),
            parse_mode="MarkdownV2"
        )
        return

    photo = update.message.photo[-1]
    caption = update.message.caption or ""

    if caption and len(caption) > MAX_TWEET_LENGTH:
        context.user_data['pending_image_file_id'] = photo.file_id
        context.user_data['pending_image_unique_id'] = photo.file_unique_id
        context.user_data['awaiting'] = 'image_caption'
        await update.message.reply_text(
            t("posts.image_caption_too_long", locale),
            parse_mode="MarkdownV2"
        )
        return

    await _create_image_post(update, context, photo.file_id, photo.file_unique_id, caption)


async def process_image_caption(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    """Handle caption input after an image was received."""
    file_id = context.user_data.get('pending_image_file_id')
    unique_id = context.user_data.get('pending_image_unique_id')
    locale = get_user_locale(update.effective_user)

    if not file_id or not unique_id:
        await update.message.reply_text(
            t("posts.image_data_missing", locale),
            parse_mode="MarkdownV2"
        )
        context.user_data['awaiting'] = None
        return

    if len(text) > MAX_TWEET_LENGTH:
        await update.message.reply_text(
            t("posts.image_caption_too_long", locale),
            parse_mode="MarkdownV2"
        )
        return

    await _create_image_post(update, context, file_id, unique_id, text)


async def prompt_image_post(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Prompt user to send an image with optional caption."""
    context.user_data['awaiting'] = 'image_post'
    locale = get_user_locale(query.from_user)
    await query.edit_message_text(
        t("posts.image_prompt", locale),
        parse_mode="MarkdownV2"
    )


async def _create_image_post(update: Update, context: ContextTypes.DEFAULT_TYPE, file_id: str, unique_id: str, caption: str) -> None:
    """Download image and create a post with media."""
    context.user_data['awaiting'] = None
    context.user_data.pop('pending_image_file_id', None)
    context.user_data.pop('pending_image_unique_id', None)
    locale = get_user_locale(update.effective_user)

    try:
        telegram_file = await context.bot.get_file(file_id)
    except Exception as e:
        await update.message.reply_text(
            t("posts.image_fetch_failed", locale),
            parse_mode="MarkdownV2"
        )
        logger.error(f"Failed to fetch Telegram file: {e}")
        return

    extension = ".jpg"
    if telegram_file.file_path and "." in telegram_file.file_path:
        extension = os.path.splitext(telegram_file.file_path)[1] or ".jpg"

    filename = f"{unique_id}{extension}"
    media_path = str(Path(MEDIA_PATH) / filename)

    try:
        await telegram_file.download_to_drive(custom_path=media_path)
    except Exception as e:
        await update.message.reply_text(
            t("posts.image_download_failed", locale),
            parse_mode="MarkdownV2"
        )
        logger.error(f"Failed to download Telegram file: {e}")
        return

    post = PostService.create_post(
        content=caption or "",
        created_by_ai=False,
        media_path=media_path
    )

    if not post:
        await update.message.reply_text(
            t("posts.create_failed", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(locale)
        )
        return

    await show_post_preview(update.message, post.id)


def _init_weekly_plan(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Initialize weekly planning state."""
    context.user_data["weekly_plan"] = {
        "days": [],
        "posts_per_day": None,
        "times_by_day": {},
        "day_dates": {},
        "queue": [],
        "created_posts": [],
        "current_index": 0,
    }


def _get_weekday_labels(locale: Optional[str] = None) -> list:
    locale = locale or "en"
    return [
        t("weekdays.mon", locale),
        t("weekdays.tue", locale),
        t("weekdays.wed", locale),
        t("weekdays.thu", locale),
        t("weekdays.fri", locale),
        t("weekdays.sat", locale),
        t("weekdays.sun", locale),
    ]


def _build_day_dates(selected_days: list, start_date: date) -> dict:
    """Map selected weekday indexes to actual dates within the 7-day window."""
    day_dates = {}
    for offset in range(7):
        day = start_date + timedelta(days=offset)
        weekday = day.weekday()
        if weekday in selected_days and weekday not in day_dates:
            day_dates[weekday] = day
    return day_dates


def _parse_times_input(text: str) -> Optional[list]:
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if not parts:
        return None

    times = []
    for part in parts:
        try:
            time_obj = datetime.strptime(part, "%H:%M").time()
        except ValueError:
            return None
        times.append(time_obj)

    if len(set(times)) != len(times):
        return None

    return sorted(times)


async def start_weekly_plan(message_or_query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start weekly planning wizard."""
    _init_weekly_plan(context)
    await show_weekly_days(message_or_query, context)


async def show_weekly_days(message_or_query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show weekday selection step."""
    weekly_plan = context.user_data.get("weekly_plan")
    if not weekly_plan:
        _init_weekly_plan(context)
        weekly_plan = context.user_data["weekly_plan"]

    locale = get_user_locale(message_or_query.from_user)
    message = t("weekly.plan", locale)

    if hasattr(message_or_query, "reply_text"):
        await message_or_query.reply_text(
            message,
            parse_mode="MarkdownV2",
            reply_markup=get_weekday_selection_keyboard(weekly_plan["days"], locale)
        )
    else:
        await message_or_query.edit_message_text(
            message,
            parse_mode="MarkdownV2",
            reply_markup=get_weekday_selection_keyboard(weekly_plan["days"], locale)
        )


async def toggle_weekly_day(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggle selected weekdays."""
    weekly_plan = context.user_data.get("weekly_plan")
    if not weekly_plan:
        _init_weekly_plan(context)
        weekly_plan = context.user_data["weekly_plan"]

    day_idx = int(query.data.split("_")[-1])
    selected = weekly_plan["days"]
    if day_idx in selected:
        selected.remove(day_idx)
    else:
        selected.append(day_idx)

    weekly_plan["days"] = sorted(selected)

    await show_weekly_days(query, context)


async def confirm_weekly_days(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Confirm weekday selection and ask posts per day."""
    weekly_plan = context.user_data.get("weekly_plan")
    if not weekly_plan or not weekly_plan["days"]:
        locale = get_user_locale(query.from_user)
        await query.answer(t("weekly.select_one_day_alert", locale), show_alert=True)
        return

    locale = get_user_locale(query.from_user)
    message = t("weekly.posts_per_day", locale)

    await query.edit_message_text(
        message,
        parse_mode="MarkdownV2",
        reply_markup=get_posts_per_day_keyboard(locale)
    )


async def select_posts_per_day(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set posts per day and start time input."""
    weekly_plan = context.user_data.get("weekly_plan")
    if not weekly_plan:
        locale = get_user_locale(query.from_user)
        await query.answer(t("weekly.start_again_alert", locale), show_alert=True)
        return

    posts_per_day = int(query.data.split("_")[-1])
    weekly_plan["posts_per_day"] = posts_per_day

    now_local = datetime.now(USER_TIMEZONE)
    weekly_plan["window_start"] = now_local.date().isoformat()
    weekly_plan["day_dates"] = _build_day_dates(weekly_plan["days"], now_local.date())

    weekly_plan["day_sequence"] = [
        day.weekday() for day in sorted(weekly_plan["day_dates"].values())
    ]
    weekly_plan["day_index"] = 0

    await _prompt_times_for_current_day(query, context)


async def _prompt_times_for_current_day(message_or_query, context: ContextTypes.DEFAULT_TYPE) -> None:
    weekly_plan = context.user_data.get("weekly_plan")
    day_sequence = weekly_plan.get("day_sequence", [])
    idx = weekly_plan.get("day_index", 0)

    locale = get_user_locale(message_or_query.from_user)

    if idx >= len(day_sequence):
        await _build_weekly_queue_and_start(message_or_query, context)
        return

    day_idx = day_sequence[idx]
    day_label = _get_weekday_labels(locale)[day_idx]
    posts_per_day = weekly_plan["posts_per_day"]

    message = t(
        "weekly.times_prompt",
        locale,
        day_label=escape_markdown_v2(day_label.upper()),
        count=posts_per_day,
    )

    context.user_data["awaiting"] = "weekly_times"
    weekly_plan["current_day_idx"] = day_idx

    if hasattr(message_or_query, "reply_text"):
        await message_or_query.reply_text(
            message,
            parse_mode="MarkdownV2"
        )
    else:
        await message_or_query.edit_message_text(
            message,
            parse_mode="MarkdownV2"
        )


async def process_weekly_times(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    """Process time list input for a selected day."""
    weekly_plan = context.user_data.get("weekly_plan")
    locale = get_user_locale(update.effective_user)
    if not weekly_plan:
        await update.message.reply_text(
            t("weekly.expired", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(locale)
        )
        return

    times = _parse_times_input(text)
    posts_per_day = weekly_plan.get("posts_per_day")
    day_idx = weekly_plan.get("current_day_idx")

    if not times or len(times) != posts_per_day:
        await update.message.reply_text(
            t("weekly.invalid_time_list", locale),
            parse_mode="MarkdownV2"
        )
        return

    day_dates = weekly_plan.get("day_dates", {})
    day_date = day_dates.get(day_idx)
    if not day_date:
        await update.message.reply_text(
            t("weekly.invalid_day_selection", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(locale)
        )
        return

    now_local = datetime.now(USER_TIMEZONE)
    if day_date == now_local.date():
        for time_obj in times:
            slot_dt = datetime.combine(day_date, time_obj)
            slot_dt = USER_TIMEZONE.localize(slot_dt)
            if slot_dt <= now_local:
                await update.message.reply_text(
                    t("weekly.times_in_past", locale),
                    parse_mode="MarkdownV2"
                )
                return

    weekly_plan["times_by_day"][day_idx] = [t.strftime("%H:%M") for t in times]
    weekly_plan["day_index"] += 1

    await _prompt_times_for_current_day(update.message, context)


async def _build_weekly_queue_and_start(message_or_query, context: ContextTypes.DEFAULT_TYPE) -> None:
    weekly_plan = context.user_data.get("weekly_plan")
    day_dates = weekly_plan.get("day_dates", {})
    times_by_day = weekly_plan.get("times_by_day", {})

    now_local = datetime.now(USER_TIMEZONE)
    queue = []
    for day_idx, day_date in sorted(day_dates.items(), key=lambda x: x[1]):
        time_list = times_by_day.get(day_idx, [])
        for time_str in time_list:
            time_obj = datetime.strptime(time_str, "%H:%M").time()
            dt_local = USER_TIMEZONE.localize(datetime.combine(day_date, time_obj))
            if dt_local <= now_local:
                continue
            queue.append({
                "day_idx": day_idx,
                "time_str": time_str,
                "datetime_local": dt_local,
                "datetime_utc": dt_local.astimezone(pytz.UTC),
            })

    queue.sort(key=lambda x: x["datetime_local"])
    weekly_plan["queue"] = queue
    weekly_plan["current_index"] = 0

    if not queue:
        locale = get_user_locale(message_or_query.from_user)
        if hasattr(message_or_query, "reply_text"):
            await message_or_query.reply_text(
                t("weekly.no_valid_times", locale),
                parse_mode="MarkdownV2",
                reply_markup=get_back_keyboard(locale)
            )
        else:
            await message_or_query.edit_message_text(
                t("weekly.no_valid_times", locale),
                parse_mode="MarkdownV2",
                reply_markup=get_back_keyboard(locale)
            )
        context.user_data.pop("weekly_plan", None)
        return

    await _show_weekly_post_mode(message_or_query, context)


async def _show_weekly_post_mode(message_or_query, context: ContextTypes.DEFAULT_TYPE) -> None:
    weekly_plan = context.user_data.get("weekly_plan")
    queue = weekly_plan.get("queue", [])
    idx = weekly_plan.get("current_index", 0)

    locale = get_user_locale(message_or_query.from_user)

    if idx >= len(queue):
        await _show_weekly_summary(message_or_query, context)
        return

    item = queue[idx]
    day_label = escape_markdown_v2(_get_weekday_labels(locale)[item["day_idx"]])
    time_str = escape_markdown_v2(item["time_str"])
    total = len(queue)

    message = t(
        "weekly.post_mode",
        locale,
        index=idx + 1,
        total=total,
        day_label=day_label,
        time_str=time_str,
    )

    if hasattr(message_or_query, "reply_text"):
        await message_or_query.reply_text(
            message,
            parse_mode="MarkdownV2",
            reply_markup=get_plan_post_mode_keyboard(locale)
        )
    else:
        await message_or_query.edit_message_text(
            message,
            parse_mode="MarkdownV2",
            reply_markup=get_plan_post_mode_keyboard(locale)
        )


async def prompt_weekly_manual(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Prompt manual content for current planned post."""
    weekly_plan = context.user_data.get("weekly_plan")
    if not weekly_plan:
        await query.edit_message_text(
            t("weekly.expired", get_user_locale(query.from_user)),
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(get_user_locale(query.from_user))
        )
        return

    queue = weekly_plan.get("queue", [])
    idx = weekly_plan.get("current_index", 0)
    item = queue[idx]
    locale = get_user_locale(query.from_user)
    day_label = _get_weekday_labels(locale)[item["day_idx"]]

    context.user_data["awaiting"] = "weekly_manual_content"

    await query.edit_message_text(
        t(
            "weekly.manual_prompt",
            locale,
            day_label=escape_markdown_v2(day_label),
            time_str=escape_markdown_v2(item['time_str']),
        ),
        parse_mode="MarkdownV2"
    )


async def prompt_weekly_ai(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Prompt AI input for current planned post."""
    weekly_plan = context.user_data.get("weekly_plan")
    if not weekly_plan:
        await query.edit_message_text(
            t("weekly.expired", get_user_locale(query.from_user)),
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(get_user_locale(query.from_user))
        )
        return

    queue = weekly_plan.get("queue", [])
    idx = weekly_plan.get("current_index", 0)
    item = queue[idx]
    locale = get_user_locale(query.from_user)
    day_label = _get_weekday_labels(locale)[item["day_idx"]]

    context.user_data["awaiting"] = "weekly_ai_prompt"

    await query.edit_message_text(
        t(
            "weekly.ai_prompt",
            locale,
            day_label=escape_markdown_v2(day_label),
            time_str=escape_markdown_v2(item['time_str']),
        ),
        parse_mode="MarkdownV2"
    )


async def process_weekly_manual_content(update: Update, context: ContextTypes.DEFAULT_TYPE, content: str) -> None:
    """Save manual post content for the weekly plan."""
    context.user_data["awaiting"] = None
    weekly_plan = context.user_data.get("weekly_plan")
    locale = get_user_locale(update.effective_user)
    if not weekly_plan:
        await update.message.reply_text(
            t("weekly.expired", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(locale)
        )
        return

    if not content or len(content.strip()) == 0:
        await update.message.reply_text(
            t("posts.empty_content", locale),
            parse_mode="MarkdownV2"
        )
        return

    post = PostService.create_post(content=content, created_by_ai=False)
    if not post:
        await update.message.reply_text(
            t("posts.create_failed", locale),
            parse_mode="MarkdownV2"
        )
        return

    await _store_weekly_post_and_continue(update.message, context, post.id)


async def process_weekly_ai_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE, prompt: str) -> None:
    """Generate AI content for the weekly plan."""
    context.user_data["awaiting"] = None
    weekly_plan = context.user_data.get("weekly_plan")
    locale = get_user_locale(update.effective_user)
    if not weekly_plan:
        await update.message.reply_text(
            t("weekly.expired", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(locale)
        )
        return

    generating_msg = await update.message.reply_text(
        t("ai.generating", locale),
        parse_mode="MarkdownV2"
    )

    success, content, error = openai_service.generate_post(prompt, locale=locale)
    if not success:
        await generating_msg.edit_text(
            t("ai.failed_weekly", locale, error=escape_markdown_v2(error)),
            parse_mode="MarkdownV2"
        )
        context.user_data["awaiting"] = "weekly_manual_content"
        return

    post = PostService.create_post(content=content, created_by_ai=True, ai_prompt=prompt)
    if not post:
        await generating_msg.edit_text(
            t("posts.save_failed", locale),
            parse_mode="MarkdownV2"
        )
        return

    await generating_msg.delete()
    await _store_weekly_post_and_continue(update.message, context, post.id)


async def _store_weekly_post_and_continue(message, context: ContextTypes.DEFAULT_TYPE, post_id: int) -> None:
    weekly_plan = context.user_data.get("weekly_plan")
    queue = weekly_plan.get("queue", [])
    idx = weekly_plan.get("current_index", 0)
    item = queue[idx]

    weekly_plan["created_posts"].append({
        "post_id": post_id,
        "scheduled_time_utc": item["datetime_utc"],
        "scheduled_time_local": item["datetime_local"],
    })

    weekly_plan["current_index"] += 1

    await _show_weekly_post_mode(message, context)


async def _show_weekly_summary(message_or_query, context: ContextTypes.DEFAULT_TYPE) -> None:
    weekly_plan = context.user_data.get("weekly_plan")
    created = weekly_plan.get("created_posts", [])

    if not created:
        await cancel_weekly_plan(message_or_query, context)
        return

    summary_by_day = {}
    for item in created:
        dt_local = item["scheduled_time_local"]
        day_key = escape_markdown_v2(dt_local.strftime("%a %d %b"))
        summary_by_day.setdefault(day_key, []).append(dt_local.strftime("%H:%M"))

    lines = []
    for day, times in summary_by_day.items():
        time_list = escape_markdown_v2(", ".join(times))
        line = f"*{day}*: {time_list}"
        lines.append(line)

    locale = get_user_locale(message_or_query.from_user)
    message = t(
        "weekly.summary",
        locale,
        count=len(created),
        lines="\n".join(lines),
    )

    if hasattr(message_or_query, "reply_text"):
        await message_or_query.reply_text(
            message,
            parse_mode="MarkdownV2",
            reply_markup=get_plan_confirm_keyboard(locale)
        )
    else:
        await message_or_query.edit_message_text(
            message,
            parse_mode="MarkdownV2",
            reply_markup=get_plan_confirm_keyboard(locale)
        )


async def confirm_weekly_plan(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Schedule all posts in the weekly plan."""
    weekly_plan = context.user_data.get("weekly_plan")
    locale = get_user_locale(query.from_user)
    if not weekly_plan:
        await query.edit_message_text(
            t("weekly.expired", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(locale)
        )
        return

    scheduler_service = get_scheduler_service(context)
    if not scheduler_service:
        await query.edit_message_text(
            t("posts.scheduler_unavailable", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(locale)
        )
        return

    scheduled = 0
    failed = 0
    for item in weekly_plan.get("created_posts", []):
        post_id = item["post_id"]
        scheduled_time_utc = item["scheduled_time_utc"]
        job_id = scheduler_service.schedule_post(
            post_id,
            scheduled_time_utc,
            publish_scheduled_post,
            post_id,
            bot=context.bot
        )
        if job_id:
            PostService.schedule_post(post_id, scheduled_time_utc, job_id)
            scheduled += 1
        else:
            failed += 1

    context.user_data.pop("weekly_plan", None)
    context.user_data["awaiting"] = None

    if failed == 0:
        message = t("weekly.scheduled_all", locale, count=scheduled)
    else:
        message = t(
            "weekly.scheduled_partial",
            locale,
            scheduled=scheduled,
            failed=failed,
        )

    await query.edit_message_text(
        message,
        parse_mode="MarkdownV2",
        reply_markup=get_back_keyboard(locale)
    )


async def cancel_weekly_plan(message_or_query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cancel weekly plan and delete created drafts."""
    weekly_plan = context.user_data.get("weekly_plan")
    if weekly_plan:
        for item in weekly_plan.get("created_posts", []):
            PostService.delete_post(item["post_id"])

    context.user_data.pop("weekly_plan", None)
    context.user_data["awaiting"] = None

    locale = get_user_locale(message_or_query.from_user)
    message = t("weekly.cancelled", locale)

    if hasattr(message_or_query, "reply_text"):
        await message_or_query.reply_text(
            message,
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(locale)
        )
    else:
        await message_or_query.edit_message_text(
            message,
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(locale)
        )


async def process_manual_post(update: Update, context: ContextTypes.DEFAULT_TYPE, content: str) -> None:
    """Process manually written post content."""
    context.user_data['awaiting'] = None
    locale = get_user_locale(update.effective_user)
    
    if not content or len(content.strip()) == 0:
        await update.message.reply_text(
            t("posts.empty_content", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(locale)
        )
        return
    
    # Create post in database
    post = PostService.create_post(content=content, created_by_ai=False)
    
    if not post:
        await update.message.reply_text(
            t("posts.create_failed", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(locale)
        )
        return
    
    # Show preview
    await show_post_preview(update.message, post.id)


async def process_edit_post(update: Update, context: ContextTypes.DEFAULT_TYPE, content: str) -> None:
    """Process edited post content."""
    context.user_data['awaiting'] = None
    post_id = context.user_data.pop('editing_post_id', None)
    locale = get_user_locale(update.effective_user)
    
    if not post_id:
        await update.message.reply_text(
            t("posts.no_post_to_edit", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(locale)
        )
        return
    
    if not content or len(content.strip()) == 0:
        await update.message.reply_text(
            t("posts.empty_content_update", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(locale)
        )
        return
    
    # Update post in database
    success = PostService.update_post_content(post_id, content)
    
    if not success:
        await update.message.reply_text(
            t("posts.update_failed", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(locale)
        )
        return
    
    await update.message.reply_text(
        t("posts.updated", locale),
        parse_mode="MarkdownV2"
    )
    
    # Show updated preview
    await show_post_preview(update.message, post_id)


async def handle_ai_with_topic(query, context: ContextTypes.DEFAULT_TYPE, topic_id: int) -> None:
    """Handle AI post generation with a topic preset."""
    topic = TopicService.get_topic_for_user(topic_id, query.from_user.id)
    locale = get_user_locale(query.from_user)
    
    if not topic:
        await query.answer(t("topics.not_found_alert", locale), show_alert=True)
        return
    
    # Send "generating" message
    await query.edit_message_text(
        t(
            "ai.generating_topic",
            locale,
            topic=escape_markdown_v2(topic.name),
        ),
        parse_mode="MarkdownV2"
    )
    
    # Generate content with topic
    success, content, error = openai_service.generate_post_with_topic(topic.name, locale=locale)
    
    if not success:
        await query.edit_message_text(
            t("ai.failed_topic", locale, error=escape_markdown_v2(error)),
            parse_mode="MarkdownV2",
            reply_markup=get_error_keyboard(show_retry=True, locale=locale)
        )
        return
    
    # Create post in database
    post = PostService.create_post(
        content=content,
        created_by_ai=True,
        ai_prompt=f"Topic: {topic.name}"
    )
    
    if not post:
        await query.edit_message_text(
            t("posts.save_failed", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(locale)
        )
        return
    
    # Show preview
    await show_post_preview_edit(query, post.id)


async def create_post_from_template(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create a post from a template and show preview."""
    template_id = int(query.data.split("_")[-1])
    locale = get_user_locale(query.from_user)

    template = TemplateService.get_template_for_user(template_id, query.from_user.id)
    if not template:
        await query.answer(t("templates.not_found_alert", locale), show_alert=True)
        return

    post = PostService.create_post(content=template.content, created_by_ai=False)
    if not post:
        await query.edit_message_text(
            t("posts.create_failed", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(locale)
        )
        return

    await show_post_preview_edit(query, post.id)


async def process_ai_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE, prompt: str) -> None:
    """Process AI prompt and generate content."""
    context.user_data['awaiting'] = None
    locale = get_user_locale(update.effective_user)
    
    # Send "generating" message
    generating_msg = await update.message.reply_text(
        t("ai.generating", locale),
        parse_mode="MarkdownV2"
    )
    
    # Generate content
    success, content, error = openai_service.generate_post(prompt, locale=locale)
    
    if not success:
        await generating_msg.edit_text(
            t("ai.failed_prompt", locale, error=escape_markdown_v2(error)),
            parse_mode="MarkdownV2",
            reply_markup=get_error_keyboard(show_retry=True, locale=locale)
        )
        return
    
    # Create post in database
    post = PostService.create_post(
        content=content,
        created_by_ai=True,
        ai_prompt=prompt
    )
    
    if not post:
        await generating_msg.edit_text(
            t("posts.save_failed", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(locale)
        )
        return
    
    # Delete generating message and show preview
    await generating_msg.delete()
    await show_post_preview(update.message, post.id)


async def show_post_preview(message, post_id: int) -> None:
    """Show preview of a post with action buttons."""
    post = PostService.get_post(post_id)
    locale = get_user_locale(message.from_user)
    
    if not post:
        await message.reply_text(
            t("posts.not_found", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(locale)
        )
        return
    
    is_thread = post.is_thread()
    char_count = len(post.content)
    
    media_label = t("posts.media_image", locale) if post.media_path else t("posts.media_none", locale)

    if is_thread:
        tweets = split_into_tweets(post.content)
        visible = tweets[:3]
        remaining = len(tweets) - len(visible)
        thread_preview = "\n".join([
            f"{i}/{len(tweets)} {escape_markdown_v2(tweet)}"
            for i, tweet in enumerate(visible, 1)
        ])
        if remaining > 0:
            thread_preview += f"\n\.\.\. \\+{remaining} more"

        created_label = t("posts.created_ai", locale) if post.created_by_ai else t("posts.created_manual", locale)
        preview_message = t(
            "preview.thread",
            locale,
            tweets=len(tweets),
            chars=char_count,
            created=created_label,
            media=media_label,
            content=thread_preview,
        )
    else:
        created_label = t("posts.created_ai", locale) if post.created_by_ai else t("posts.created_manual", locale)
        preview_message = t(
            "preview.single",
            locale,
            chars=char_count,
            max_chars=MAX_TWEET_LENGTH,
            char_status="✅" if char_count <= MAX_TWEET_LENGTH else "⚠️",
            post_type=t("posts.type_single", locale),
            created=created_label,
            media=media_label,
            content=escape_markdown_v2(post.content),
        )
    
    await message.reply_text(
        preview_message,
        parse_mode="MarkdownV2",
        reply_markup=get_post_preview_keyboard(post_id, is_thread, locale)
    )


async def handle_publish_post(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle publishing a post immediately."""
    post_id = int(query.data.split("_")[1])
    locale = get_user_locale(query.from_user)
    
    post = PostService.get_post(post_id)
    if not post:
        await query.edit_message_text(
            t("posts.not_found", locale),
            parse_mode="MarkdownV2"
        )
        return
    
    # Update message to show publishing status
    await query.edit_message_text(
        t("posts.publishing", locale),
        parse_mode="MarkdownV2"
    )
    
    # Publish based on post type
    if post.media_path:
        if post.is_thread():
            await query.edit_message_text(
                t("posts.media_thread_blocked", locale),
                parse_mode="MarkdownV2",
                reply_markup=get_back_keyboard(locale)
            )
            return

        success, tweet_id, error = twitter_service.post_tweet_with_media(post.content, post.media_path)
        if success and tweet_id:
            PostService.update_post_status(
                post_id,
                PostStatus.PUBLISHED,
                twitter_id=tweet_id
            )

            tweet_url = f"https://twitter.com/i/web/status/{tweet_id}"

            await query.edit_message_text(
                t(
                    "posts.published",
                    locale,
                    post_id=post_id,
                    tweet_id=tweet_id,
                    tweet_url=escape_markdown_v2(tweet_url),
                ),
                parse_mode="MarkdownV2",
                reply_markup=get_back_keyboard(locale),
                disable_web_page_preview=True
            )
        else:
            PostService.update_post_status(
                post_id,
                PostStatus.FAILED,
                error_message=error
            )

            await query.edit_message_text(
                t(
                    "posts.publish_failed",
                    locale,
                    error=escape_markdown_v2(error or t("errors.unknown_error", locale)),
                    post_id=post_id,
                ),
                parse_mode="MarkdownV2",
                reply_markup=get_error_keyboard(show_retry=True, locale=locale)
            )
        return

    if post.is_thread():
        tweets = split_into_tweets(post.content)
        success, tweet_ids, error = twitter_service.post_thread(tweets)
        
        if success and tweet_ids:
            # Update post status
            PostService.update_post_status(
                post_id,
                PostStatus.PUBLISHED,
                twitter_id=tweet_ids[0]  # Store first tweet ID
            )
            
            first_tweet_url = f"https://twitter.com/i/web/status/{tweet_ids[0]}"
            
            await query.edit_message_text(
                t(
                    "posts.thread_published",
                    locale,
                    tweet_count=len(tweet_ids),
                    post_id=post_id,
                    tweet_url=escape_markdown_v2(first_tweet_url),
                ),
                parse_mode="MarkdownV2",
                reply_markup=get_back_keyboard(locale),
                disable_web_page_preview=True
            )
        else:
            # Failed
            PostService.update_post_status(
                post_id,
                PostStatus.FAILED,
                error_message=error
            )
            
            await query.edit_message_text(
                t(
                    "posts.publish_failed",
                    locale,
                    error=escape_markdown_v2(error or t("errors.unknown_error", locale)),
                    post_id=post_id,
                ),
                parse_mode="MarkdownV2",
                reply_markup=get_error_keyboard(show_retry=True, locale=locale)
            )
    else:
        # Single tweet
        success, tweet_id, error = twitter_service.post_tweet(post.content)
        
        if success and tweet_id:
            PostService.update_post_status(
                post_id,
                PostStatus.PUBLISHED,
                twitter_id=tweet_id
            )
            
            tweet_url = f"https://twitter.com/i/web/status/{tweet_id}"
            
            await query.edit_message_text(
                t(
                    "posts.published",
                    locale,
                    post_id=post_id,
                    tweet_id=tweet_id,
                    tweet_url=escape_markdown_v2(tweet_url),
                ),
                parse_mode="MarkdownV2",
                reply_markup=get_back_keyboard(locale),
                disable_web_page_preview=True
            )
        else:
            PostService.update_post_status(
                post_id,
                PostStatus.FAILED,
                error_message=error
            )
            
            await query.edit_message_text(
                t(
                    "posts.publish_failed",
                    locale,
                    error=escape_markdown_v2(error or t("errors.unknown_error", locale)),
                    post_id=post_id,
                ),
                parse_mode="MarkdownV2",
                reply_markup=get_error_keyboard(show_retry=True, locale=locale)
            )


async def handle_schedule_menu(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show schedule options menu."""
    post_id = int(query.data.split("_")[1])
    locale = get_user_locale(query.from_user)
    
    schedule_message = t("posts.schedule_menu", locale)
    
    await query.edit_message_text(
        schedule_message,
        parse_mode="MarkdownV2",
        reply_markup=get_schedule_keyboard(post_id, locale)
    )


async def show_scheduled_posts(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show list of scheduled posts."""
    locale = get_user_locale(query.from_user)
    message, keyboard = build_scheduled_posts_list(page=0, locale=locale)
    await query.edit_message_text(
        message,
        parse_mode="MarkdownV2",
        reply_markup=keyboard
    )


def build_scheduled_posts_list(page: int = 0, per_page: int = 5, locale: Optional[str] = None):
    """Build scheduled posts list message and keyboard."""
    locale = locale or "en"
    scheduled = PostService.get_scheduled_posts()

    if not scheduled:
        message = t("scheduled.none", locale)
        return message, get_scheduled_posts_keyboard([], page=0, per_page=per_page, locale=locale)

    posts_data = []
    for post, sched in scheduled:
        preview = truncate_text(post.content, 40)
        scheduled_for_utc = sched.scheduled_for
        if scheduled_for_utc.tzinfo is None:
            scheduled_for_utc = pytz.UTC.localize(scheduled_for_utc)
        scheduled_for_local = scheduled_for_utc.astimezone(USER_TIMEZONE)
        posts_data.append((post.id, preview, scheduled_for_local))

    count = len(posts_data)
    start = page * per_page
    end = start + per_page

    posts_list = "\n\n".join([
        t(
            "scheduled.item",
            locale,
            id=pid,
            preview=escape_markdown_v2(preview),
            datetime=escape_markdown_v2(format_datetime(scheduled_for, locale=locale)),
            tz=escape_markdown_v2(TZ),
            relative=escape_markdown_v2(format_relative_time(scheduled_for, locale)),
        )
        for pid, preview, scheduled_for in posts_data[start:end]
    ])

    message = t(
        "scheduled.list",
        locale,
        count=count,
        posts=posts_list,
    )

    return message, get_scheduled_posts_keyboard(posts_data, page=page, per_page=per_page, locale=locale)


def _get_week_start(date_local: date) -> date:
    return date_local - timedelta(days=date_local.weekday())


def _format_date_only(date_local: date, locale: str) -> str:
    return date_local.strftime(t("datetime.formats.date_only", locale))


def _build_weekly_calendar_message(week_offset: int, locale: str) -> str:
    today_local = datetime.now(USER_TIMEZONE).date()
    week_start = _get_week_start(today_local) + timedelta(weeks=week_offset)
    week_end = week_start + timedelta(days=6)

    start_local = USER_TIMEZONE.localize(datetime.combine(week_start, datetime.min.time()))
    end_local = USER_TIMEZONE.localize(datetime.combine(week_end + timedelta(days=1), datetime.min.time()))

    scheduled = PostService.get_scheduled_posts_between(
        start_local.astimezone(pytz.UTC),
        end_local.astimezone(pytz.UTC),
    )

    posts_by_date = {}
    for post, sched in scheduled:
        scheduled_for_utc = sched.scheduled_for
        if scheduled_for_utc.tzinfo is None:
            scheduled_for_utc = pytz.UTC.localize(scheduled_for_utc)
        scheduled_for_local = scheduled_for_utc.astimezone(USER_TIMEZONE)
        day_date = scheduled_for_local.date()
        posts_by_date.setdefault(day_date, []).append((scheduled_for_local, post))

    day_sections = []
    for day_date in sorted(posts_by_date.keys()):
        day_label = _get_weekday_labels(locale)[day_date.weekday()]
        date_str = _format_date_only(day_date, locale)
        header = escape_markdown_v2(f"{day_label} {date_str}")

        lines = [f"*{header}*"]
        for scheduled_for_local, post in sorted(posts_by_date[day_date], key=lambda x: x[0]):
            time_str = escape_markdown_v2(scheduled_for_local.strftime("%H:%M"))
            preview = truncate_text(post.content or "", 34)
            if not preview.strip():
                preview = t("calendar.image_only", locale)
            preview = escape_markdown_v2(preview)
            lines.append(f"\\- {time_str} \\#{post.id} {preview}")
        day_sections.append("\n".join(lines))

    days_text = "\n\n".join(day_sections) if day_sections else t("calendar.empty", locale)

    range_label = t(
        "calendar.week_range",
        locale,
        start=escape_markdown_v2(_format_date_only(week_start, locale)),
        end=escape_markdown_v2(_format_date_only(week_end, locale)),
    )

    return t(
        "calendar.weekly_view",
        locale,
        range=range_label,
        days=days_text,
        tz=escape_markdown_v2(TZ),
    )


async def show_weekly_calendar(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show weekly publication calendar view."""
    locale = get_user_locale(query.from_user)
    week_offset = 0
    if query.data.startswith("calendar_week_"):
        try:
            week_offset = int(query.data.split("_")[-1])
        except ValueError:
            week_offset = 0

    message = _build_weekly_calendar_message(week_offset, locale)
    await query.edit_message_text(
        message,
        parse_mode="MarkdownV2",
        reply_markup=get_weekly_calendar_keyboard(week_offset, locale),
    )


def build_drafts_list(page: int = 0, per_page: int = 5, locale: Optional[str] = None):
    """Build drafts list message and keyboard."""
    locale = locale or "en"
    drafts = PostService.get_draft_posts()

    if not drafts:
        message = t("drafts.none", locale)
        return message, get_back_keyboard(locale)

    drafts_data = []
    for post in drafts:
        preview = truncate_text(post.content, 40)
        created_at_utc = post.created_at
        if created_at_utc.tzinfo is None:
            created_at_utc = pytz.UTC.localize(created_at_utc)
        created_at_local = created_at_utc.astimezone(USER_TIMEZONE)
        drafts_data.append((post.id, preview, created_at_local))

    count = len(drafts_data)
    start = page * per_page
    end = start + per_page

    drafts_list = "\n\n".join([
        t(
            "drafts.item",
            locale,
            id=pid,
            preview=escape_markdown_v2(preview),
            datetime=escape_markdown_v2(format_datetime(created_at, locale=locale)),
            tz=escape_markdown_v2(TZ),
        )
        for pid, preview, created_at in drafts_data[start:end]
    ])

    message = t(
        "drafts.list",
        locale,
        count=count,
        drafts=drafts_list,
    )
    return message, get_drafts_keyboard(drafts_data, page=page, per_page=per_page, locale=locale)


async def show_drafts(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show list of drafts."""
    locale = get_user_locale(query.from_user)
    message, keyboard = build_drafts_list(page=0, locale=locale)
    await query.edit_message_text(
        message,
        parse_mode="MarkdownV2",
        reply_markup=keyboard
    )


async def handle_preview_post(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show post preview again."""
    post_id = int(query.data.split("_")[1])
    # Reuse the preview function
    # We need to create a fake message object for this
    locale = get_user_locale(query.from_user)
    await query.edit_message_text(t("posts.preview_loading", locale))
    # This is a workaround - in production you'd refactor this
    pass


async def handle_delete_post(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle post deletion."""
    data = query.data
    locale = get_user_locale(query.from_user)
    
    if data.startswith("confirm_delete_"):
        # Actually delete
        parts = data.split("_")
        post_id = int(parts[-1])
        
        success = PostService.delete_post(post_id)
        
        if success:
            await query.edit_message_text(
                t("posts.delete_success", locale),
                parse_mode="MarkdownV2",
                reply_markup=get_back_keyboard(locale)
            )
        else:
            await query.edit_message_text(
                t("posts.delete_failed", locale),
                parse_mode="MarkdownV2",
                reply_markup=get_back_keyboard(locale)
            )
    else:
        # Show confirmation
        post_id = int(data.split("_")[1])
        
        await query.edit_message_text(
            t("posts.delete_confirm", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_confirm_delete_keyboard(post_id, locale=locale)
        )


async def handle_edit_post(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle editing a post's content."""
    post_id = int(query.data.split("_")[1])
    locale = get_user_locale(query.from_user)
    
    post = PostService.get_post(post_id)
    if not post:
        await query.edit_message_text(
            t("posts.not_found", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(locale)
        )
        return
    
    # Store post ID for editing
    context.user_data['editing_post_id'] = post_id
    context.user_data['awaiting'] = 'edit_post'
    
    await query.edit_message_text(
        t(
            "posts.edit_prompt",
            locale,
            content=escape_markdown_v2(post.content),
        ),
        parse_mode="MarkdownV2"
    )


async def show_post_preview_edit(query, post_id: int) -> None:
    """Show preview of a post with action buttons (for edit_message)."""
    post = PostService.get_post(post_id)
    locale = get_user_locale(query.from_user)
    
    if not post:
        await query.edit_message_text(
            t("posts.not_found", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(locale)
        )
        return
    
    is_thread = post.is_thread()
    char_count = len(post.content)
    media_label = t("posts.media_image", locale) if post.media_path else t("posts.media_none", locale)
    
    if is_thread:
        tweets = split_into_tweets(post.content)
        visible = tweets[:3]
        remaining = len(tweets) - len(visible)
        thread_preview = "\n".join([
            f"{i}/{len(tweets)} {escape_markdown_v2(tweet)}"
            for i, tweet in enumerate(visible, 1)
        ])
        if remaining > 0:
            thread_preview += f"\n\.\.\. \\+{remaining} more"

        created_label = t("posts.created_ai", locale) if post.created_by_ai else t("posts.created_manual", locale)
        preview_message = t(
            "preview.thread",
            locale,
            tweets=len(tweets),
            chars=char_count,
            created=created_label,
            media=media_label,
            content=thread_preview,
        )
    else:
        created_label = t("posts.created_ai", locale) if post.created_by_ai else t("posts.created_manual", locale)
        preview_message = t(
            "preview.single",
            locale,
            chars=char_count,
            max_chars=MAX_TWEET_LENGTH,
            char_status="✅" if char_count <= MAX_TWEET_LENGTH else "⚠️",
            post_type=t("posts.type_single", locale),
            created=created_label,
            media=media_label,
            content=escape_markdown_v2(post.content),
        )
    
    await query.edit_message_text(
        preview_message,
        parse_mode="MarkdownV2",
        reply_markup=get_post_preview_keyboard(post_id, is_thread, locale)
    )


async def handle_quick_schedule(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle quick scheduling options (1h, 3h, tomorrow)."""
    data = query.data
    parts = data.split("_")
    post_id = int(parts[-1])
    schedule_type = parts[2]  # "1h", "3h", or "tomorrow"
    locale = get_user_locale(query.from_user)
    
    # Work in user's timezone
    now_local = datetime.now(USER_TIMEZONE)
    
    if schedule_type == "1h":
        scheduled_time_local = now_local + timedelta(hours=1)
        time_label = t("posts.schedule_time_in_1h", locale)
    elif schedule_type == "3h":
        scheduled_time_local = now_local + timedelta(hours=3)
        time_label = t("posts.schedule_time_in_3h", locale)
    elif schedule_type == "tomorrow":
        # Tomorrow at 9:00 AM in user's timezone
        tomorrow = now_local + timedelta(days=1)
        scheduled_time_local = tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)
        time_label = t("posts.schedule_time_tomorrow_9am", locale)
    else:
        await query.edit_message_text(
            t("posts.schedule_invalid_option", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(locale)
        )
        return
    
    # Convert to UTC for storage and scheduling
    scheduled_time_utc = scheduled_time_local.astimezone(pytz.UTC)
    
    # Schedule the post
    post = PostService.get_post(post_id)
    if not post:
        await query.edit_message_text(
            t("posts.not_found", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(locale)
        )
        return
    
    scheduler_service = get_scheduler_service(context)
    if not scheduler_service:
        await query.edit_message_text(
            t("posts.scheduler_unavailable", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(locale)
        )
        return

    job_id = scheduler_service.schedule_post(
        post_id,
        scheduled_time_utc,
        publish_scheduled_post,
        post_id,
        bot=context.bot
    )
    
    if job_id:
        PostService.schedule_post(post_id, scheduled_time_utc, job_id)
        
        await query.edit_message_text(
            t(
                "posts.schedule_success",
                locale,
                datetime=escape_markdown_v2(format_datetime(scheduled_time_local, locale=locale)),
                tz=escape_markdown_v2(TZ),
                relative=escape_markdown_v2(time_label),
            ),
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(locale)
        )
    else:
        await query.edit_message_text(
            t("posts.schedule_failed", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(locale)
        )


async def handle_custom_schedule_prompt(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Prompt user for custom schedule date/time."""
    post_id = int(query.data.split("_")[-1])
    locale = get_user_locale(query.from_user)
    
    context.user_data['scheduling_post_id'] = post_id
    context.user_data['awaiting'] = 'custom_schedule'
    
    await query.edit_message_text(
        t("posts.custom_schedule_prompt", locale, tz=escape_markdown_v2(TZ)),
        parse_mode="MarkdownV2"
    )


async def process_custom_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    """Process custom schedule date input."""
    context.user_data['awaiting'] = None
    post_id = context.user_data.pop('scheduling_post_id', None)
    locale = get_user_locale(update.effective_user)
    
    if not post_id:
        await update.message.reply_text(
            t("posts.schedule_not_found", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(locale)
        )
        return
    
    # Parse the date (user inputs in their local timezone)
    try:
        scheduled_time = datetime.strptime(text.strip(), "%Y-%m-%d %H:%M")
        # Localize to user's timezone, then convert to UTC for storage
        scheduled_time = USER_TIMEZONE.localize(scheduled_time)
        scheduled_time_utc = scheduled_time.astimezone(pytz.UTC)
    except ValueError:
        await update.message.reply_text(
            t("posts.invalid_datetime_format", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(locale)
        )
        return
    
    # Validate it's in the future (compare in user's timezone)
    now_local = datetime.now(USER_TIMEZONE)
    if scheduled_time <= now_local:
        await update.message.reply_text(
            t("posts.schedule_time_past", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(locale)
        )
        return
    
    # Schedule the post
    post = PostService.get_post(post_id)
    if not post:
        await update.message.reply_text(
            t("posts.not_found", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(locale)
        )
        return
    
    scheduler_service = get_scheduler_service(context)
    if not scheduler_service:
        await update.message.reply_text(
            t("posts.scheduler_unavailable", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(locale)
        )
        return

    job_id = scheduler_service.schedule_post(
        post_id,
        scheduled_time_utc,
        publish_scheduled_post,
        post_id,
        bot=context.bot
    )
    
    if job_id:
        PostService.schedule_post(post_id, scheduled_time_utc, job_id)
        
        # Show confirmation with time in user's timezone
        await update.message.reply_text(
            t(
                "posts.schedule_success_simple",
                locale,
                datetime=escape_markdown_v2(format_datetime(scheduled_time, locale=locale)),
                tz=escape_markdown_v2(TZ),
            ),
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(locale)
        )
    else:
        await update.message.reply_text(
            t("posts.schedule_failed", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(locale)
        )


async def handle_view_scheduled_post(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View details of a scheduled post."""
    post_id = int(query.data.split("_")[-1])
    locale = get_user_locale(query.from_user)
    
    post = PostService.get_post(post_id)
    if not post or not post.scheduled_post:
        await query.edit_message_text(
            t("posts.scheduled_not_found", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(locale)
        )
        return
    
    # Convert UTC to user's timezone for display
    scheduled_for_utc = post.scheduled_post.scheduled_for
    if scheduled_for_utc.tzinfo is None:
        scheduled_for_utc = pytz.UTC.localize(scheduled_for_utc)
    scheduled_for_local = scheduled_for_utc.astimezone(USER_TIMEZONE)
    
    await query.edit_message_text(
        t(
            "posts.scheduled_view",
            locale,
            content=escape_markdown_v2(truncate_text(post.content, 200)),
            datetime=escape_markdown_v2(format_datetime(scheduled_for_local, locale=locale)),
            tz=escape_markdown_v2(TZ),
            relative=escape_markdown_v2(format_relative_time(scheduled_for_local, locale)),
        ),
        parse_mode="MarkdownV2",
        reply_markup=get_scheduled_post_actions_keyboard(post_id, locale)
    )


async def handle_scheduled_page(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle pagination for scheduled posts."""
    page = int(query.data.split("_")[-1])

    locale = get_user_locale(query.from_user)
    message, keyboard = build_scheduled_posts_list(page=page, locale=locale)
    await query.edit_message_text(
        message,
        parse_mode="MarkdownV2",
        reply_markup=keyboard
    )


async def handle_drafts_page(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle pagination for drafts list."""
    page = int(query.data.split("_")[-1])
    locale = get_user_locale(query.from_user)
    message, keyboard = build_drafts_list(page=page, locale=locale)
    await query.edit_message_text(
        message,
        parse_mode="MarkdownV2",
        reply_markup=keyboard
    )


async def handle_reschedule_prompt(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Prompt user to reschedule a post."""
    post_id = int(query.data.split("_")[-1])
    locale = get_user_locale(query.from_user)
    
    context.user_data['rescheduling_post_id'] = post_id
    context.user_data['awaiting'] = 'reschedule'
    
    await query.edit_message_text(
        t("posts.reschedule_prompt", locale, tz=escape_markdown_v2(TZ)),
        parse_mode="MarkdownV2"
    )


async def process_reschedule(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    """Process reschedule date input."""
    context.user_data['awaiting'] = None
    post_id = context.user_data.pop('rescheduling_post_id', None)
    locale = get_user_locale(update.effective_user)
    
    if not post_id:
        await update.message.reply_text(
            t("posts.reschedule_not_found", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(locale)
        )
        return
    
    # Parse the date (user inputs in their local timezone)
    try:
        new_time = datetime.strptime(text.strip(), "%Y-%m-%d %H:%M")
        # Localize to user's timezone, then convert to UTC
        new_time_local = USER_TIMEZONE.localize(new_time)
        new_time_utc = new_time_local.astimezone(pytz.UTC)
    except ValueError:
        await update.message.reply_text(
            t("posts.invalid_datetime_format", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(locale)
        )
        return
    
    # Validate it's in the future (compare in user's timezone)
    now_local = datetime.now(USER_TIMEZONE)
    if new_time_local <= now_local:
        await update.message.reply_text(
            t("posts.schedule_time_past", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(locale)
        )
        return
    
    # Get the post to find the job_id
    post = PostService.get_post(post_id)
    if not post or not post.scheduled_post:
        await update.message.reply_text(
            t("posts.scheduled_not_found", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(locale)
        )
        return
    
    job_id = post.scheduled_post.job_id
    
    scheduler_service = get_scheduler_service(context)
    if not scheduler_service:
        await update.message.reply_text(
            t("posts.scheduler_unavailable", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(locale)
        )
        return

    # Reschedule in APScheduler (use UTC time)
    success = scheduler_service.reschedule_post(job_id, new_time_utc)
    
    if success:
        # Update in database (store UTC)
        PostService.reschedule_post(post_id, new_time_utc)
        
        # Show confirmation with time in user's timezone
        await update.message.reply_text(
            t(
                "posts.reschedule_success",
                locale,
                datetime=escape_markdown_v2(format_datetime(new_time_local, locale=locale)),
                tz=escape_markdown_v2(TZ),
            ),
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(locale)
        )
    else:
        await update.message.reply_text(
            t("posts.reschedule_failed", locale),
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard(locale)
        )
