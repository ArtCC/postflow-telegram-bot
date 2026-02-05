"""
Post Handlers
Handlers for creating, publishing, and managing posts.
"""

from datetime import datetime, timedelta, date
from typing import Optional
from telegram import Update
from telegram.ext import ContextTypes

from bot.config import logger, MAX_TWEET_LENGTH, USER_TIMEZONE, TZ, TELEGRAM_USER_ID
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
    get_weekday_selection_keyboard,
    get_posts_per_day_keyboard,
    get_plan_post_mode_keyboard,
    get_plan_confirm_keyboard,
)
from bot.services.post_service import PostService
from bot.services.twitter_service import TwitterService
from bot.services.openai_service import OpenAIService
from bot.services.scheduler_service import SchedulerService
from bot.database import PostStatus
import pytz


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
            post_type = "Thread" if is_thread else "Post"
            message = (
                f"✅ *SCHEDULED {post_type.upper()} PUBLISHED*\n\n"
                f"Post `#{post_id}` is live\n\n"
                f"🔗 [View on Twitter]({escape_markdown_v2(tweet_url)})"
            )
        else:
            message = (
                f"❌ *SCHEDULED POST FAILED*\n\n"
                f"Post `#{post_id}` was not published\n\n"
                f"📝 {escape_markdown_v2(error or 'Unknown error')}"
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
    
    if not is_authorized(user_id):
        return
    
    text = update.message.text
    awaiting = context.user_data.get('awaiting')
    
    if awaiting == 'weekly_times':
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
            "💡 Open the menu to continue",
            reply_markup=get_back_keyboard()
        )


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


def _get_weekday_labels() -> list:
    return ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


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

    message = (
        "📆 *PLAN WEEK*\n\n"
        "Select the days you want to publish:\n"
        "Mon to Sun"
    )

    if hasattr(message_or_query, "reply_text"):
        await message_or_query.reply_text(
            message,
            parse_mode="MarkdownV2",
            reply_markup=get_weekday_selection_keyboard(weekly_plan["days"])
        )
    else:
        await message_or_query.edit_message_text(
            message,
            parse_mode="MarkdownV2",
            reply_markup=get_weekday_selection_keyboard(weekly_plan["days"])
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
        await query.answer("Select at least one day", show_alert=True)
        return

    message = (
        "📝 *POSTS PER DAY*\n\n"
        "How many posts per selected day?"
    )

    await query.edit_message_text(
        message,
        parse_mode="MarkdownV2",
        reply_markup=get_posts_per_day_keyboard()
    )


async def select_posts_per_day(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set posts per day and start time input."""
    weekly_plan = context.user_data.get("weekly_plan")
    if not weekly_plan:
        await query.answer("Start again with /menu", show_alert=True)
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

    if idx >= len(day_sequence):
        await _build_weekly_queue_and_start(message_or_query, context)
        return

    day_idx = day_sequence[idx]
    day_label = _get_weekday_labels()[day_idx]
    posts_per_day = weekly_plan["posts_per_day"]

    message = (
        f"⏰ *TIMES FOR {day_label.upper()}*\n\n"
        f"Enter {posts_per_day} time slots as `HH:MM`, separated by commas\."
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
    if not weekly_plan:
        await update.message.reply_text(
            "❌ Planning session expired\. Use /menu to start again\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
        return

    times = _parse_times_input(text)
    posts_per_day = weekly_plan.get("posts_per_day")
    day_idx = weekly_plan.get("current_day_idx")

    if not times or len(times) != posts_per_day:
        await update.message.reply_text(
            "❌ Invalid time list\. Use `HH:MM, HH:MM` with the correct count\.",
            parse_mode="MarkdownV2"
        )
        return

    day_dates = weekly_plan.get("day_dates", {})
    day_date = day_dates.get(day_idx)
    if not day_date:
        await update.message.reply_text(
            "❌ Invalid day selection\. Use /menu to start again\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
        return

    now_local = datetime.now(USER_TIMEZONE)
    if day_date == now_local.date():
        for time_obj in times:
            slot_dt = datetime.combine(day_date, time_obj)
            slot_dt = USER_TIMEZONE.localize(slot_dt)
            if slot_dt <= now_local:
                await update.message.reply_text(
                    "❌ One or more times are in the past\. Enter future times\.",
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
        if hasattr(message_or_query, "reply_text"):
            await message_or_query.reply_text(
                "❌ No valid times to schedule\. Start again with /menu\.",
                parse_mode="MarkdownV2",
                reply_markup=get_back_keyboard()
            )
        else:
            await message_or_query.edit_message_text(
                "❌ No valid times to schedule\. Start again with /menu\.",
                parse_mode="MarkdownV2",
                reply_markup=get_back_keyboard()
            )
        context.user_data.pop("weekly_plan", None)
        return

    await _show_weekly_post_mode(message_or_query, context)


async def _show_weekly_post_mode(message_or_query, context: ContextTypes.DEFAULT_TYPE) -> None:
    weekly_plan = context.user_data.get("weekly_plan")
    queue = weekly_plan.get("queue", [])
    idx = weekly_plan.get("current_index", 0)

    if idx >= len(queue):
        await _show_weekly_summary(message_or_query, context)
        return

    item = queue[idx]
    day_label = escape_markdown_v2(_get_weekday_labels()[item["day_idx"]])
    time_str = escape_markdown_v2(item["time_str"])
    total = len(queue)

    message = (
        f"📆 *PLAN WEEK*\n\n"
        f"Post {idx + 1}/{total} \\- {day_label} {time_str}\n\n"
        "Choose how to create this post:"
    )

    if hasattr(message_or_query, "reply_text"):
        await message_or_query.reply_text(
            message,
            parse_mode="MarkdownV2",
            reply_markup=get_plan_post_mode_keyboard()
        )
    else:
        await message_or_query.edit_message_text(
            message,
            parse_mode="MarkdownV2",
            reply_markup=get_plan_post_mode_keyboard()
        )


async def prompt_weekly_manual(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Prompt manual content for current planned post."""
    weekly_plan = context.user_data.get("weekly_plan")
    if not weekly_plan:
        await query.edit_message_text(
            "❌ Planning session expired\. Use /menu to start again\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
        return

    queue = weekly_plan.get("queue", [])
    idx = weekly_plan.get("current_index", 0)
    item = queue[idx]
    day_label = _get_weekday_labels()[item["day_idx"]]

    context.user_data["awaiting"] = "weekly_manual_content"

    await query.edit_message_text(
        f"✏️ *WRITE POST*\n\n"
        f"{day_label} {item['time_str']}\n\n"
        "Send the post text\. Type /cancel to abort\.",
        parse_mode="MarkdownV2"
    )


async def prompt_weekly_ai(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Prompt AI input for current planned post."""
    weekly_plan = context.user_data.get("weekly_plan")
    if not weekly_plan:
        await query.edit_message_text(
            "❌ Planning session expired\. Use /menu to start again\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
        return

    queue = weekly_plan.get("queue", [])
    idx = weekly_plan.get("current_index", 0)
    item = queue[idx]
    day_label = _get_weekday_labels()[item["day_idx"]]

    context.user_data["awaiting"] = "weekly_ai_prompt"

    await query.edit_message_text(
        f"🤖 *AI PROMPT*\n\n"
        f"{day_label} {item['time_str']}\n\n"
        "Describe the post you want\. Type /cancel to abort\.",
        parse_mode="MarkdownV2"
    )


async def process_weekly_manual_content(update: Update, context: ContextTypes.DEFAULT_TYPE, content: str) -> None:
    """Save manual post content for the weekly plan."""
    context.user_data["awaiting"] = None
    weekly_plan = context.user_data.get("weekly_plan")
    if not weekly_plan:
        await update.message.reply_text(
            "❌ Planning session expired\. Use /menu to start again\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
        return

    if not content or len(content.strip()) == 0:
        await update.message.reply_text(
            "⚠️ *EMPTY CONTENT*\n\n"
            "Write something to create the post\.",
            parse_mode="MarkdownV2"
        )
        return

    post = PostService.create_post(content=content, created_by_ai=False)
    if not post:
        await update.message.reply_text(
            "❌ Failed to create the post\.",
            parse_mode="MarkdownV2"
        )
        return

    await _store_weekly_post_and_continue(update.message, context, post.id)


async def process_weekly_ai_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE, prompt: str) -> None:
    """Generate AI content for the weekly plan."""
    context.user_data["awaiting"] = None
    weekly_plan = context.user_data.get("weekly_plan")
    if not weekly_plan:
        await update.message.reply_text(
            "❌ Planning session expired\. Use /menu to start again\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
        return

    generating_msg = await update.message.reply_text(
        "🤖 *GENERATING*\n\n"
        "⏳ Creating content with AI\.",
        parse_mode="MarkdownV2"
    )

    success, content, error = openai_service.generate_post(prompt)
    if not success:
        await generating_msg.edit_text(
            f"🤖 *AI FAILED*\n\n"
            f"❌ {escape_markdown_v2(error)}\n\n"
            "Write the post manually\.",
            parse_mode="MarkdownV2"
        )
        context.user_data["awaiting"] = "weekly_manual_content"
        return

    post = PostService.create_post(content=content, created_by_ai=True, ai_prompt=prompt)
    if not post:
        await generating_msg.edit_text(
            "❌ Failed to save the post\.",
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

    message = (
        "✅ *REVIEW PLAN*\n\n"
        f"Total posts: `{len(created)}`\n\n"
        + "\n".join(lines)
    )

    if hasattr(message_or_query, "reply_text"):
        await message_or_query.reply_text(
            message,
            parse_mode="MarkdownV2",
            reply_markup=get_plan_confirm_keyboard()
        )
    else:
        await message_or_query.edit_message_text(
            message,
            parse_mode="MarkdownV2",
            reply_markup=get_plan_confirm_keyboard()
        )


async def confirm_weekly_plan(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Schedule all posts in the weekly plan."""
    weekly_plan = context.user_data.get("weekly_plan")
    if not weekly_plan:
        await query.edit_message_text(
            "❌ Planning session expired\. Use /menu to start again\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
        return

    scheduler_service = get_scheduler_service(context)
    if not scheduler_service:
        await query.edit_message_text(
            "❌ Scheduler service not available\. Restart the bot\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
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
        message = f"✅ *SCHEDULED*\n\nAll posts scheduled: `{scheduled}`"
    else:
        message = (
            f"⚠️ *PARTIAL SCHEDULE*\n\n"
            f"Scheduled: `{scheduled}`\n"
            f"Failed: `{failed}`\n\n"
            "Failed posts remain as drafts\."
        )

    await query.edit_message_text(
        message,
        parse_mode="MarkdownV2",
        reply_markup=get_back_keyboard()
    )


async def cancel_weekly_plan(message_or_query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cancel weekly plan and delete created drafts."""
    weekly_plan = context.user_data.get("weekly_plan")
    if weekly_plan:
        for item in weekly_plan.get("created_posts", []):
            PostService.delete_post(item["post_id"])

    context.user_data.pop("weekly_plan", None)
    context.user_data["awaiting"] = None

    message = (
        "🚫 *Cancelled*\n\n"
        "Planning discarded\."
    )

    if hasattr(message_or_query, "reply_text"):
        await message_or_query.reply_text(
            message,
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
    else:
        await message_or_query.edit_message_text(
            message,
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )


async def process_manual_post(update: Update, context: ContextTypes.DEFAULT_TYPE, content: str) -> None:
    """Process manually written post content."""
    context.user_data['awaiting'] = None
    
    if not content or len(content.strip()) == 0:
        await update.message.reply_text(
            "⚠️ *EMPTY CONTENT*\n\n"
            "Write something to create a post\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
        return
    
    # Create post in database
    post = PostService.create_post(content=content, created_by_ai=False)
    
    if not post:
        await update.message.reply_text(
            "❌ Failed to create the post\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
        return
    
    # Show preview
    await show_post_preview(update.message, post.id)


async def process_edit_post(update: Update, context: ContextTypes.DEFAULT_TYPE, content: str) -> None:
    """Process edited post content."""
    context.user_data['awaiting'] = None
    post_id = context.user_data.pop('editing_post_id', None)
    
    if not post_id:
        await update.message.reply_text(
            "❌ No post to edit\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
        return
    
    if not content or len(content.strip()) == 0:
        await update.message.reply_text(
            "⚠️ *EMPTY CONTENT*\n\n"
            "Write something to update the post\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
        return
    
    # Update post in database
    success = PostService.update_post_content(post_id, content)
    
    if not success:
        await update.message.reply_text(
            "❌ Failed to update the post\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
        return
    
    await update.message.reply_text(
        "✅ *POST UPDATED*",
        parse_mode="MarkdownV2"
    )
    
    # Show updated preview
    await show_post_preview(update.message, post_id)


async def process_ai_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE, prompt: str) -> None:
    """Process AI prompt and generate content."""
    context.user_data['awaiting'] = None
    
    # Send "generating" message
    generating_msg = await update.message.reply_text(
        "🤖 *GENERATING*\n\n"
        "⏳ Creating content with AI\\.\\.",
        parse_mode="MarkdownV2"
    )
    
    # Generate content
    success, content, error = openai_service.generate_post(prompt)
    
    if not success:
        await generating_msg.edit_text(
            f"🤖 *AI FAILED*\n\n"
            f"❌ {escape_markdown_v2(error)}\n\n"
            f"Try a shorter or clearer prompt\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_error_keyboard(show_retry=True)
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
            "❌ Failed to save the post\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
        return
    
    # Delete generating message and show preview
    await generating_msg.delete()
    await show_post_preview(update.message, post.id)


async def show_post_preview(message, post_id: int) -> None:
    """Show preview of a post with action buttons."""
    post = PostService.get_post(post_id)
    
    if not post:
        await message.reply_text(
            "❌ Post not found\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
        return
    
    is_thread = post.is_thread()
    char_count = len(post.content)
    
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

        preview_message = (
            f"🧵 *THREAD PREVIEW*\n\n"
            f"*Summary*\n"
            f"• Tweets: `{len(tweets)}`\n"
            f"• Chars: `{char_count}`\n"
            f"• Created: {'`AI`' if post.created_by_ai else '`Manual`'}\n\n"
            f"*Content*\n"
            f"{thread_preview}\n\n"
            f"Select an action:"
        )
    else:
        preview_message = (
            f"👁️ *POST PREVIEW*\n\n"
            f"*Summary*\n"
            f"• Chars: `{char_count}/{MAX_TWEET_LENGTH}` {'✅' if char_count <= MAX_TWEET_LENGTH else '⚠️'}\n"
            f"• Type: `Single`\n"
            f"• Created: {'`AI`' if post.created_by_ai else '`Manual`'}\n\n"
            f"*Content*\n"
            f"{escape_markdown_v2(post.content)}\n\n"
            f"Select an action:"
        )
    
    await message.reply_text(
        preview_message,
        parse_mode="MarkdownV2",
        reply_markup=get_post_preview_keyboard(post_id, is_thread)
    )


async def handle_publish_post(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle publishing a post immediately."""
    post_id = int(query.data.split("_")[1])
    
    post = PostService.get_post(post_id)
    if not post:
        await query.edit_message_text(
            "❌ Post not found\\.",
            parse_mode="MarkdownV2"
        )
        return
    
    # Update message to show publishing status
        await query.edit_message_text(
            "🚀 *PUBLISHING*\n\n"
            "⏳ Posting to Twitter",
            parse_mode="MarkdownV2"
        )
    
    # Publish based on post type
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
                f"✅ *THREAD PUBLISHED*\n\n"
                f"• Tweets: `{len(tweet_ids)}`\n"
                f"• Post ID: `#{post_id}`\n\n"
                f"🔗 [View on Twitter]({escape_markdown_v2(first_tweet_url)})",
                parse_mode="MarkdownV2",
                reply_markup=get_back_keyboard(),
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
                f"❌ *PUBLISH FAILED*\n\n"
                f"⚠️ {escape_markdown_v2(error or 'Unknown error')}\n\n"
                f"Saved as `#{post_id}`\\. You can retry\\.",
                parse_mode="MarkdownV2",
                reply_markup=get_error_keyboard(show_retry=True)
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
                f"✅ *PUBLISHED*\n\n"
                f"• Post ID: `#{post_id}`\n"
                f"• Tweet ID: `{tweet_id}`\n\n"
                f"🔗 [View on Twitter]({escape_markdown_v2(tweet_url)})",
                parse_mode="MarkdownV2",
                reply_markup=get_back_keyboard(),
                disable_web_page_preview=True
            )
        else:
            PostService.update_post_status(
                post_id,
                PostStatus.FAILED,
                error_message=error
            )
            
            await query.edit_message_text(
                f"❌ *PUBLISH FAILED*\n\n"
                f"⚠️ {escape_markdown_v2(error or 'Unknown error')}\n\n"
                f"Saved as `#{post_id}`\\. You can retry\\.",
                parse_mode="MarkdownV2",
                reply_markup=get_error_keyboard(show_retry=True)
            )


async def handle_schedule_menu(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show schedule options menu."""
    post_id = int(query.data.split("_")[1])
    
    schedule_message = (
        "📅 *SCHEDULE POST*\n\n"
        "Choose a time or enter a custom date\\."
    )
    
    await query.edit_message_text(
        schedule_message,
        parse_mode="MarkdownV2",
        reply_markup=get_schedule_keyboard(post_id)
    )


async def show_scheduled_posts(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show list of scheduled posts."""
    message, keyboard = build_scheduled_posts_list(page=0)
    await query.edit_message_text(
        message,
        parse_mode="MarkdownV2",
        reply_markup=keyboard
    )


def build_scheduled_posts_list(page: int = 0, per_page: int = 5):
    """Build scheduled posts list message and keyboard."""
    scheduled = PostService.get_scheduled_posts()

    if not scheduled:
        message = (
            "📅 *NO SCHEDULED POSTS*\n\n"
            "Create a post and choose Schedule to get started\\."
        )
        return message, get_back_keyboard()

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
        f"📌 *Post \\#{pid}*\n"
        f"{escape_markdown_v2(preview)}\n"
        f"⏰ {escape_markdown_v2(format_datetime(scheduled_for))} \\({escape_markdown_v2(TZ)}\\)\n"
        f"⏳ {escape_markdown_v2(format_relative_time(scheduled_for))}"
        for pid, preview, scheduled_for in posts_data[start:end]
    ])

    message = (
        f"📅 *SCHEDULED POSTS* \\(`{count}`\\)\n\n"
        f"{posts_list}\n\n"
        f"Select a post to view details\\."
    )

    return message, get_scheduled_posts_keyboard(posts_data, page=page, per_page=per_page)


def build_drafts_list(page: int = 0, per_page: int = 5):
    """Build drafts list message and keyboard."""
    drafts = PostService.get_draft_posts()

    if not drafts:
        message = (
            "📝 *NO DRAFTS*\n\n"
            "Create a post and save it as a draft\\."
        )
        return message, get_back_keyboard()

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
        f"📝 *Draft \\#{pid}*\n"
        f"{escape_markdown_v2(preview)}\n"
        f"⏰ {escape_markdown_v2(format_datetime(created_at))} \\({escape_markdown_v2(TZ)}\\)"
        for pid, preview, created_at in drafts_data[start:end]
    ])

    message = (
        f"📝 *DRAFTS* \\(`{count}`\\)\n\n"
        f"{drafts_list}\n\n"
        f"Select a draft to view details\\."
    )

    return message, get_drafts_keyboard(drafts_data, page=page, per_page=per_page)


async def show_drafts(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show list of drafts."""
    message, keyboard = build_drafts_list(page=0)
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
    await query.edit_message_text("Loading preview...")
    # This is a workaround - in production you'd refactor this
    pass


async def handle_delete_post(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle post deletion."""
    data = query.data
    
    if data.startswith("confirm_delete_"):
        # Actually delete
        parts = data.split("_")
        post_id = int(parts[-1])
        
        success = PostService.delete_post(post_id)
        
        if success:
            await query.edit_message_text(
                "✅ *POST DELETED*\n\n"
                "Post removed\\.",
                parse_mode="MarkdownV2",
                reply_markup=get_back_keyboard()
            )
        else:
            await query.edit_message_text(
                "❌ Failed to delete the post\\.",
                parse_mode="MarkdownV2",
                reply_markup=get_back_keyboard()
            )
    else:
        # Show confirmation
        post_id = int(data.split("_")[1])
        
        await query.edit_message_text(
            "⚠️ *CONFIRM DELETE*\n\n"
            "This action cannot be undone\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_confirm_delete_keyboard(post_id)
        )


async def handle_edit_post(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle editing a post's content."""
    post_id = int(query.data.split("_")[1])
    
    post = PostService.get_post(post_id)
    if not post:
        await query.edit_message_text(
            "❌ Post not found\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
        return
    
    # Store post ID for editing
    context.user_data['editing_post_id'] = post_id
    context.user_data['awaiting'] = 'edit_post'
    
    await query.edit_message_text(
        "✏️ *EDIT POST*\n\n"
        f"*Current content*\n"
        f"{escape_markdown_v2(post.content)}\n\n"
        "Send the updated text\\.\n"
        "Type /cancel to abort\\.",
        parse_mode="MarkdownV2"
    )


async def show_post_preview_edit(query, post_id: int) -> None:
    """Show preview of a post with action buttons (for edit_message)."""
    post = PostService.get_post(post_id)
    
    if not post:
        await query.edit_message_text(
            "❌ Post not found\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
        return
    
    is_thread = post.is_thread()
    char_count = len(post.content)
    
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

        preview_message = (
            f"🧵 *THREAD PREVIEW*\n\n"
            f"*Summary*\n"
            f"• Tweets: `{len(tweets)}`\n"
            f"• Chars: `{char_count}`\n"
            f"• Created: {'`AI`' if post.created_by_ai else '`Manual`'}\n\n"
            f"*Content*\n"
            f"{thread_preview}\n\n"
            f"Select an action:"
        )
    else:
        preview_message = (
            f"👁️ *POST PREVIEW*\n\n"
            f"*Summary*\n"
            f"• Chars: `{char_count}/{MAX_TWEET_LENGTH}` {'✅' if char_count <= MAX_TWEET_LENGTH else '⚠️'}\n"
            f"• Type: `Single`\n"
            f"• Created: {'`AI`' if post.created_by_ai else '`Manual`'}\n\n"
            f"*Content*\n"
            f"{escape_markdown_v2(post.content)}\n\n"
            f"Select an action:"
        )
    
    await query.edit_message_text(
        preview_message,
        parse_mode="MarkdownV2",
        reply_markup=get_post_preview_keyboard(post_id, is_thread)
    )


async def handle_quick_schedule(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle quick scheduling options (1h, 3h, tomorrow)."""
    data = query.data
    parts = data.split("_")
    post_id = int(parts[-1])
    schedule_type = parts[2]  # "1h", "3h", or "tomorrow"
    
    # Work in user's timezone
    now_local = datetime.now(USER_TIMEZONE)
    
    if schedule_type == "1h":
        scheduled_time_local = now_local + timedelta(hours=1)
        time_label = "in 1 hour"
    elif schedule_type == "3h":
        scheduled_time_local = now_local + timedelta(hours=3)
        time_label = "in 3 hours"
    elif schedule_type == "tomorrow":
        # Tomorrow at 9:00 AM in user's timezone
        tomorrow = now_local + timedelta(days=1)
        scheduled_time_local = tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)
        time_label = "tomorrow at 9:00 AM"
    else:
        await query.edit_message_text(
            "❌ Invalid schedule option\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
        return
    
    # Convert to UTC for storage and scheduling
    scheduled_time_utc = scheduled_time_local.astimezone(pytz.UTC)
    
    # Schedule the post
    post = PostService.get_post(post_id)
    if not post:
        await query.edit_message_text(
            "❌ Post not found\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
        return
    
    scheduler_service = get_scheduler_service(context)
    if not scheduler_service:
        await query.edit_message_text(
            "❌ Scheduler service not available\. Restart the bot\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
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
            f"✅ *POST SCHEDULED*\n\n"
            f"⏰ {escape_markdown_v2(format_datetime(scheduled_time_local))} \\({escape_markdown_v2(TZ)}\\)\n"
            f"⏳ {escape_markdown_v2(time_label)}",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
    else:
        await query.edit_message_text(
            "❌ Failed to schedule the post\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )


async def handle_custom_schedule_prompt(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Prompt user for custom schedule date/time."""
    post_id = int(query.data.split("_")[-1])
    
    context.user_data['scheduling_post_id'] = post_id
    context.user_data['awaiting'] = 'custom_schedule'
    
    await query.edit_message_text(
        f"📆 *CUSTOM SCHEDULE*\n\n"
        f"Format: `YYYY\\-MM\\-DD HH:MM`\n"
        f"Example: `2026\\-02\\-05 14:30`\n"
        f"Timezone: `{escape_markdown_v2(TZ)}`\n\n"
        f"Type /cancel to abort\\.",
        parse_mode="MarkdownV2"
    )


async def process_custom_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    """Process custom schedule date input."""
    context.user_data['awaiting'] = None
    post_id = context.user_data.pop('scheduling_post_id', None)
    
    if not post_id:
        await update.message.reply_text(
            "❌ No post to schedule\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
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
            "❌ *INVALID FORMAT*\n\n"
            "Use: `YYYY\\-MM\\-DD HH:MM`\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
        return
    
    # Validate it's in the future (compare in user's timezone)
    now_local = datetime.now(USER_TIMEZONE)
    if scheduled_time <= now_local:
        await update.message.reply_text(
            "❌ Scheduled time must be in the future\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
        return
    
    # Schedule the post
    post = PostService.get_post(post_id)
    if not post:
        await update.message.reply_text(
            "❌ Post not found\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
        return
    
    scheduler_service = get_scheduler_service(context)
    if not scheduler_service:
        await update.message.reply_text(
            "❌ Scheduler service not available\. Restart the bot\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
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
            f"✅ *POST SCHEDULED*\n\n"
            f"⏰ {escape_markdown_v2(format_datetime(scheduled_time))} \\({escape_markdown_v2(TZ)}\\)",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
    else:
        await update.message.reply_text(
            "❌ Failed to schedule the post\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )


async def handle_view_scheduled_post(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View details of a scheduled post."""
    post_id = int(query.data.split("_")[-1])
    
    post = PostService.get_post(post_id)
    if not post or not post.scheduled_post:
        await query.edit_message_text(
            "❌ Scheduled post not found\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
        return
    
    # Convert UTC to user's timezone for display
    scheduled_for_utc = post.scheduled_post.scheduled_for
    if scheduled_for_utc.tzinfo is None:
        scheduled_for_utc = pytz.UTC.localize(scheduled_for_utc)
    scheduled_for_local = scheduled_for_utc.astimezone(USER_TIMEZONE)
    
    await query.edit_message_text(
        f"📅 *SCHEDULED POST*\n\n"
        f"*Content*\n"
        f"{escape_markdown_v2(truncate_text(post.content, 200))}\n\n"
        f"*Schedule*\n"
        f"⏰ {escape_markdown_v2(format_datetime(scheduled_for_local))} \\({escape_markdown_v2(TZ)}\\)\n"
        f"⏳ {escape_markdown_v2(format_relative_time(scheduled_for_local))}\n\n"
        f"Select an action:",
        parse_mode="MarkdownV2",
        reply_markup=get_scheduled_post_actions_keyboard(post_id)
    )


async def handle_scheduled_page(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle pagination for scheduled posts."""
    page = int(query.data.split("_")[-1])

    message, keyboard = build_scheduled_posts_list(page=page)
    await query.edit_message_text(
        message,
        parse_mode="MarkdownV2",
        reply_markup=keyboard
    )


async def handle_drafts_page(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle pagination for drafts list."""
    page = int(query.data.split("_")[-1])
    message, keyboard = build_drafts_list(page=page)
    await query.edit_message_text(
        message,
        parse_mode="MarkdownV2",
        reply_markup=keyboard
    )


async def handle_reschedule_prompt(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Prompt user to reschedule a post."""
    post_id = int(query.data.split("_")[-1])
    
    context.user_data['rescheduling_post_id'] = post_id
    context.user_data['awaiting'] = 'reschedule'
    
    await query.edit_message_text(
        f"📆 *RESCHEDULE POST*\n\n"
        f"Format: `YYYY\\-MM\\-DD HH:MM`\n"
        f"Example: `2026\\-02\\-05 14:30`\n"
        f"Timezone: `{escape_markdown_v2(TZ)}`\n\n"
        f"Type /cancel to abort\\.",
        parse_mode="MarkdownV2"
    )


async def process_reschedule(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    """Process reschedule date input."""
    context.user_data['awaiting'] = None
    post_id = context.user_data.pop('rescheduling_post_id', None)
    
    if not post_id:
        await update.message.reply_text(
            "❌ No post to reschedule\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
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
            "❌ *INVALID FORMAT*\n\n"
            "Use: `YYYY\\-MM\\-DD HH:MM`\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
        return
    
    # Validate it's in the future (compare in user's timezone)
    now_local = datetime.now(USER_TIMEZONE)
    if new_time_local <= now_local:
        await update.message.reply_text(
            "❌ Scheduled time must be in the future\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
        return
    
    # Get the post to find the job_id
    post = PostService.get_post(post_id)
    if not post or not post.scheduled_post:
        await update.message.reply_text(
            "❌ Scheduled post not found\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
        return
    
    job_id = post.scheduled_post.job_id
    
    scheduler_service = get_scheduler_service(context)
    if not scheduler_service:
        await update.message.reply_text(
            "❌ Scheduler service not available\. Restart the bot\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
        return

    # Reschedule in APScheduler (use UTC time)
    success = scheduler_service.reschedule_post(job_id, new_time_utc)
    
    if success:
        # Update in database (store UTC)
        PostService.reschedule_post(post_id, new_time_utc)
        
        # Show confirmation with time in user's timezone
        await update.message.reply_text(
            f"✅ *POST RESCHEDULED*\n\n"
            f"⏰ {escape_markdown_v2(format_datetime(new_time_local))} \\({escape_markdown_v2(TZ)}\\)",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
    else:
        await update.message.reply_text(
            "❌ Failed to reschedule the post\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
