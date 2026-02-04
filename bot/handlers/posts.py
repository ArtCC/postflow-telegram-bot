"""
Post Handlers
Handlers for creating, publishing, and managing posts.
"""

from datetime import datetime, timedelta
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
scheduler_service = SchedulerService()


async def notify_scheduled_post_result(bot, post_id: int, success: bool, tweet_id: str = None, error: str = None, is_thread: bool = False) -> None:
    """Send notification to user about scheduled post result."""
    try:
        if success:
            tweet_url = f"https://twitter.com/i/web/status/{tweet_id}" if tweet_id else ""
            post_type = "Thread" if is_thread else "Post"
            message = (
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🎉 *SCHEDULED {post_type.upper()} PUBLISHED*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"✅ Your scheduled post \\#`{post_id}` has been\n"
                f"   published successfully\\!\n\n"
                f"🔗 [View on Twitter]({escape_markdown_v2(tweet_url)})"
            )
        else:
            message = (
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"❌ *SCHEDULED POST FAILED*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"⚠️ Your scheduled post \\#`{post_id}` could\n"
                f"   not be published\\.\n\n"
                f"📝 Error: {escape_markdown_v2(error or 'Unknown error')}\n\n"
                f"💡 Check /menu to retry or reschedule\\."
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
    
    if awaiting == 'manual_post':
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
            "💡 Use /menu to see available options",
            reply_markup=get_back_keyboard()
        )


async def process_manual_post(update: Update, context: ContextTypes.DEFAULT_TYPE, content: str) -> None:
    """Process manually written post content."""
    context.user_data['awaiting'] = None
    
    if not content or len(content.strip()) == 0:
        await update.message.reply_text(
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ *EMPTY CONTENT*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Cannot create empty post\\!\n\n"
            "Please write some content\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
        return
    
    # Create post in database
    post = PostService.create_post(content=content, created_by_ai=False)
    
    if not post:
        await update.message.reply_text(
            "❌ Failed to create post\\. Please try again\\.",
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
            "❌ No post to edit\\. Please try again\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
        return
    
    if not content or len(content.strip()) == 0:
        await update.message.reply_text(
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ *EMPTY CONTENT*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Cannot update with empty content\\!\n\n"
            "Please write some content\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
        return
    
    # Update post in database
    success = PostService.update_post_content(post_id, content)
    
    if not success:
        await update.message.reply_text(
            "❌ Failed to update post\\. Please try again\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
        return
    
    await update.message.reply_text(
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "✅ *POST UPDATED*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Your post has been updated\\!",
        parse_mode="MarkdownV2"
    )
    
    # Show updated preview
    await show_post_preview(update.message, post_id)


async def process_ai_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE, prompt: str) -> None:
    """Process AI prompt and generate content."""
    context.user_data['awaiting'] = None
    
    # Send "generating" message
    generating_msg = await update.message.reply_text(
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🤖 *GENERATING\\.\\.\\.*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "⏳ Creating content with AI\\.\\.\\.\n\n"
        "This may take a few seconds\\.",
        parse_mode="MarkdownV2"
    )
    
    # Generate content
    success, content, error = openai_service.generate_post(prompt)
    
    if not success:
        await generating_msg.edit_text(
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🤖 *AI GENERATION FAILED*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"❌ {escape_markdown_v2(error)}\n\n"
            f"💡 You can try:\n"
            f"   • Rephrasing your prompt\n"
            f"   • Writing manually\n"
            f"   • Checking your API key",
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
            "❌ Failed to save post\\. Please try again\\.",
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
        # Show thread preview
        tweets = split_into_tweets(post.content)
        thread_preview = "\n\n".join([
            f"📌 *Tweet {i}/{len(tweets)}:*\n{escape_markdown_v2(tweet)}"
            for i, tweet in enumerate(tweets, 1)
        ])
        
        preview_message = (
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🧵 *THREAD PREVIEW*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{thread_preview}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📊 *Stats:*\n"
            f"   • Total chars: `{char_count}`\n"
            f"   • Tweets: `{len(tweets)}`\n"
            f"   • Created: {'`AI`' if post.created_by_ai else '`Manually`'}\n\n"
            f"Choose an action:"
        )
    else:
        # Show single post preview
        preview_message = (
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👁️ *POST PREVIEW*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📝 *Content:*\n"
            f"{escape_markdown_v2(post.content)}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📊 *Stats:*\n"
            f"   • Characters: `{char_count}/{MAX_TWEET_LENGTH}` {'✅' if char_count <= MAX_TWEET_LENGTH else '⚠️'}\n"
            f"   • Type: `Single tweet`\n"
            f"   • Created: {'`AI`' if post.created_by_ai else '`Manually`'}\n\n"
            f"Choose an action:"
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
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🚀 *PUBLISHING\\.\\.\\.*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "⏳ Posting to Twitter\\.\\.\\.",
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
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"✅ *THREAD PUBLISHED*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🧵 Thread posted successfully\\!\n\n"
                f"📊 *Details:*\n"
                f"   • Tweets: `{len(tweet_ids)}`\n"
                f"   • Post ID: `#{post_id}`\n\n"
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
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"❌ *PUBLISH FAILED*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"⚠️ {escape_markdown_v2(error or 'Unknown error')}\n\n"
                f"💡 Your post is saved \\(ID: `#{post_id}`\\)\n"
                f"   You can retry later\\.",
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
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"✅ *PUBLISHED*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🎉 Post published successfully\\!\n\n"
                f"📊 *Details:*\n"
                f"   • Post ID: `#{post_id}`\n"
                f"   • Tweet ID: `{tweet_id}`\n\n"
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
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"❌ *PUBLISH FAILED*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"⚠️ {escape_markdown_v2(error or 'Unknown error')}\n\n"
                f"💡 Your post is saved \\(ID: `#{post_id}`\\)\n"
                f"   You can retry later\\.",
                parse_mode="MarkdownV2",
                reply_markup=get_error_keyboard(show_retry=True)
            )


async def handle_schedule_menu(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show schedule options menu."""
    post_id = int(query.data.split("_")[1])
    
    schedule_message = (
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📅 *SCHEDULE POST*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "When do you want to publish?\n\n"
        "Choose a quick option or\n"
        "enter a custom date\\."
    )
    
    await query.edit_message_text(
        schedule_message,
        parse_mode="MarkdownV2",
        reply_markup=get_schedule_keyboard(post_id)
    )


async def show_scheduled_posts(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show list of scheduled posts."""
    scheduled = PostService.get_scheduled_posts()
    
    if not scheduled:
        await query.edit_message_text(
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📅 *NO SCHEDULED POSTS*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "⚠️ You haven't scheduled any\n"
            "   posts yet\\!\n\n"
            "💡 Create a new post and\n"
            "   choose 'Schedule' to get started\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
        return
    
    # Format scheduled posts for display (convert UTC to user's timezone)
    posts_data = []
    for post, sched in scheduled:
        preview = truncate_text(post.content, 40)
        # Convert UTC to user's timezone for display
        scheduled_for_utc = sched.scheduled_for
        if scheduled_for_utc.tzinfo is None:
            scheduled_for_utc = pytz.UTC.localize(scheduled_for_utc)
        scheduled_for_local = scheduled_for_utc.astimezone(USER_TIMEZONE)
        posts_data.append((post.id, preview, scheduled_for_local))
    
    count = len(posts_data)
    
    # Create message with list
    posts_list = "\n\n".join([
        f"📌 *Post \\#{pid}*\n"
        f"   {escape_markdown_v2(preview)}\n"
        f"   ⏰ {escape_markdown_v2(format_datetime(scheduled_for))}\n"
        f"   ⏳ {escape_markdown_v2(format_relative_time(scheduled_for))}"
        for pid, preview, scheduled_for in posts_data[:5]  # Show first 5
    ])
    
    message = (
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 *SCHEDULED POSTS* \\(`{count}`\\)\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{posts_list}\n\n"
        f"🌍 Timezone: `{escape_markdown_v2(TZ)}`\n\n"
        f"💡 Click to view details"
    )
    
    await query.edit_message_text(
        message,
        parse_mode="MarkdownV2",
        reply_markup=get_scheduled_posts_keyboard(posts_data)
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
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "✅ *POST DELETED*\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "🗑️ Post removed successfully\\.",
                parse_mode="MarkdownV2",
                reply_markup=get_back_keyboard()
            )
        else:
            await query.edit_message_text(
                "❌ Failed to delete post\\.",
                parse_mode="MarkdownV2",
                reply_markup=get_back_keyboard()
            )
    else:
        # Show confirmation
        post_id = int(data.split("_")[1])
        
        await query.edit_message_text(
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ *CONFIRM DELETE*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Are you sure you want to delete\n"
            "this post?\n\n"
            "⚠️ This action cannot be undone\\!",
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
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "✏️ *EDIT POST*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📝 *Current content:*\n"
        f"{escape_markdown_v2(post.content)}\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Type your new content below\\.\n\n"
        "💡 Type /cancel to abort\\.",
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
        thread_preview = "\n\n".join([
            f"📌 *Tweet {i}/{len(tweets)}:*\n{escape_markdown_v2(tweet)}"
            for i, tweet in enumerate(tweets, 1)
        ])
        
        preview_message = (
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🧵 *THREAD PREVIEW*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{thread_preview}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📊 *Stats:*\n"
            f"   • Total chars: `{char_count}`\n"
            f"   • Tweets: `{len(tweets)}`\n"
            f"   • Created: {'`AI`' if post.created_by_ai else '`Manually`'}\n\n"
            f"Choose an action:"
        )
    else:
        preview_message = (
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👁️ *POST PREVIEW*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📝 *Content:*\n"
            f"{escape_markdown_v2(post.content)}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📊 *Stats:*\n"
            f"   • Characters: `{char_count}/{MAX_TWEET_LENGTH}` {'✅' if char_count <= MAX_TWEET_LENGTH else '⚠️'}\n"
            f"   • Type: `Single tweet`\n"
            f"   • Created: {'`AI`' if post.created_by_ai else '`Manually`'}\n\n"
            f"Choose an action:"
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
    
    # Create a callback for when the schedule fires
    async def publish_scheduled_post(bot=None):
        """Callback to publish the post when scheduled time arrives."""
        p = PostService.get_post(post_id)
        if p and p.status == PostStatus.SCHEDULED:
            if p.is_thread():
                tweets = split_into_tweets(p.content)
                success, tweet_ids, error = twitter_service.post_thread(tweets)
                if success:
                    PostService.update_post_status(post_id, PostStatus.PUBLISHED, twitter_id=tweet_ids[0] if tweet_ids else None)
                    await notify_scheduled_post_result(bot, post_id, True, tweet_id=tweet_ids[0] if tweet_ids else None, is_thread=True)
                else:
                    PostService.update_post_status(post_id, PostStatus.FAILED, error_message=error)
                    await notify_scheduled_post_result(bot, post_id, False, error=error, is_thread=True)
            else:
                success, tweet_id, error = twitter_service.post_tweet(p.content)
                if success:
                    PostService.update_post_status(post_id, PostStatus.PUBLISHED, twitter_id=tweet_id)
                    await notify_scheduled_post_result(bot, post_id, True, tweet_id=tweet_id)
                else:
                    PostService.update_post_status(post_id, PostStatus.FAILED, error_message=error)
                    await notify_scheduled_post_result(bot, post_id, False, error=error)
    
    job_id = scheduler_service.schedule_post(
        post_id=post_id,
        scheduled_time=scheduled_time_utc,
        callback=publish_scheduled_post,
        bot=context.bot
    )
    
    if job_id:
        PostService.schedule_post(post_id, scheduled_time_utc, job_id)
        
        await query.edit_message_text(
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ *POST SCHEDULED*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📅 Your post will be published\n"
            f"   *{escape_markdown_v2(time_label)}*\n\n"
            f"⏰ {escape_markdown_v2(format_datetime(scheduled_time_local))}\n"
            f"🌍 Timezone: `{escape_markdown_v2(TZ)}`\n\n"
            f"💡 View scheduled posts in menu\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
    else:
        await query.edit_message_text(
            "❌ Failed to schedule post\\. Please try again\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )


async def handle_custom_schedule_prompt(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Prompt user for custom schedule date/time."""
    post_id = int(query.data.split("_")[-1])
    
    context.user_data['scheduling_post_id'] = post_id
    context.user_data['awaiting'] = 'custom_schedule'
    
    await query.edit_message_text(
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📆 *CUSTOM SCHEDULE*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Enter the date and time:\n\n"
        f"📝 *Format:* `YYYY\\-MM\\-DD HH:MM`\n\n"
        f"📌 *Example:*\n"
        f"   `2026\\-02\\-05 14:30`\n\n"
        f"🌍 Timezone: `{escape_markdown_v2(TZ)}`\n\n"
        f"Type /cancel to abort\\.",
        parse_mode="MarkdownV2"
    )


async def process_custom_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    """Process custom schedule date input."""
    context.user_data['awaiting'] = None
    post_id = context.user_data.pop('scheduling_post_id', None)
    
    if not post_id:
        await update.message.reply_text(
            "❌ No post to schedule\\. Please try again\\.",
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
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "❌ *INVALID FORMAT*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Please use format:\n"
            "`YYYY\\-MM\\-DD HH:MM`\n\n"
            "Example: `2026\\-02\\-05 14:30`",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
        return
    
    # Validate it's in the future (compare in user's timezone)
    now_local = datetime.now(USER_TIMEZONE)
    if scheduled_time <= now_local:
        await update.message.reply_text(
            "❌ Scheduled time must be in the future\\!",
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
    
    async def publish_scheduled_post(bot=None):
        p = PostService.get_post(post_id)
        if p and p.status == PostStatus.SCHEDULED:
            if p.is_thread():
                tweets = split_into_tweets(p.content)
                success, tweet_ids, error = twitter_service.post_thread(tweets)
                if success:
                    PostService.update_post_status(post_id, PostStatus.PUBLISHED, twitter_id=tweet_ids[0] if tweet_ids else None)
                    await notify_scheduled_post_result(bot, post_id, True, tweet_id=tweet_ids[0] if tweet_ids else None, is_thread=True)
                else:
                    PostService.update_post_status(post_id, PostStatus.FAILED, error_message=error)
                    await notify_scheduled_post_result(bot, post_id, False, error=error, is_thread=True)
            else:
                success, tweet_id, error = twitter_service.post_tweet(p.content)
                if success:
                    PostService.update_post_status(post_id, PostStatus.PUBLISHED, twitter_id=tweet_id)
                    await notify_scheduled_post_result(bot, post_id, True, tweet_id=tweet_id)
                else:
                    PostService.update_post_status(post_id, PostStatus.FAILED, error_message=error)
                    await notify_scheduled_post_result(bot, post_id, False, error=error)
    
    job_id = scheduler_service.schedule_post(
        post_id=post_id,
        scheduled_time=scheduled_time_utc,
        callback=publish_scheduled_post,
        bot=context.bot
    )
    
    if job_id:
        PostService.schedule_post(post_id, scheduled_time_utc, job_id)
        
        # Show confirmation with time in user's timezone
        await update.message.reply_text(
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ *POST SCHEDULED*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📅 Your post will be published:\n\n"
            f"⏰ {escape_markdown_v2(format_datetime(scheduled_time))}\n"
            f"🌍 Timezone: `{escape_markdown_v2(TZ)}`\n\n"
            f"💡 View scheduled posts in menu\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
    else:
        await update.message.reply_text(
            "❌ Failed to schedule post\\. Please try again\\.",
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
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 *SCHEDULED POST*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📝 *Content:*\n"
        f"{escape_markdown_v2(truncate_text(post.content, 200))}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⏰ *Scheduled for:*\n"
        f"   {escape_markdown_v2(format_datetime(scheduled_for_local))}\n"
        f"   {escape_markdown_v2(format_relative_time(scheduled_for_local))}\n"
        f"🌍 Timezone: `{escape_markdown_v2(TZ)}`\n\n"
        f"Choose an action:",
        parse_mode="MarkdownV2",
        reply_markup=get_scheduled_post_actions_keyboard(post_id)
    )


async def handle_scheduled_page(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle pagination for scheduled posts."""
    page = int(query.data.split("_")[-1])
    
    scheduled = PostService.get_scheduled_posts()
    
    if not scheduled:
        await query.edit_message_text(
            "📅 No scheduled posts found\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
        return
    
    # Convert UTC to user's timezone for display
    posts_data = []
    for post, sched in scheduled:
        preview = truncate_text(post.content, 40)
        scheduled_for_utc = sched.scheduled_for
        if scheduled_for_utc.tzinfo is None:
            scheduled_for_utc = pytz.UTC.localize(scheduled_for_utc)
        scheduled_for_local = scheduled_for_utc.astimezone(USER_TIMEZONE)
        posts_data.append((post.id, preview, scheduled_for_local))
    
    count = len(posts_data)
    per_page = 5
    start = page * per_page
    end = start + per_page
    
    posts_list = "\n\n".join([
        f"📌 *Post \\#{pid}*\n"
        f"   {escape_markdown_v2(preview)}\n"
        f"   ⏰ {escape_markdown_v2(format_datetime(scheduled_for))}"
        for pid, preview, scheduled_for in posts_data[start:end]
    ])
    
    message = (
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 *SCHEDULED POSTS* \\(`{count}`\\)\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{posts_list}\n\n"
        f"🌍 Timezone: `{escape_markdown_v2(TZ)}`\n\n"
        f"💡 Click to view details"
    )
    
    await query.edit_message_text(
        message,
        parse_mode="MarkdownV2",
        reply_markup=get_scheduled_posts_keyboard(posts_data, page=page)
    )


async def handle_reschedule_prompt(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Prompt user to reschedule a post."""
    post_id = int(query.data.split("_")[-1])
    
    context.user_data['rescheduling_post_id'] = post_id
    context.user_data['awaiting'] = 'reschedule'
    
    await query.edit_message_text(
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📆 *RESCHEDULE POST*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Enter the new date and time:\n\n"
        f"📝 *Format:* `YYYY\\-MM\\-DD HH:MM`\n\n"
        f"📌 *Example:*\n"
        f"   `2026\\-02\\-05 14:30`\n\n"
        f"🌍 Timezone: `{escape_markdown_v2(TZ)}`\n\n"
        f"Type /cancel to abort\\.",
        parse_mode="MarkdownV2"
    )


async def process_reschedule(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    """Process reschedule date input."""
    context.user_data['awaiting'] = None
    post_id = context.user_data.pop('rescheduling_post_id', None)
    
    if not post_id:
        await update.message.reply_text(
            "❌ No post to reschedule\\. Please try again\\.",
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
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "❌ *INVALID FORMAT*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Please use format:\n"
            "`YYYY\\-MM\\-DD HH:MM`\n\n"
            "Example: `2026\\-02\\-05 14:30`",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
        return
    
    # Validate it's in the future (compare in user's timezone)
    now_local = datetime.now(USER_TIMEZONE)
    if new_time_local <= now_local:
        await update.message.reply_text(
            "❌ Scheduled time must be in the future\\!",
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
    
    # Reschedule in APScheduler (use UTC time)
    success = scheduler_service.reschedule_post(job_id, new_time_utc)
    
    if success:
        # Update in database (store UTC)
        PostService.reschedule_post(post_id, new_time_utc)
        
        # Show confirmation with time in user's timezone
        await update.message.reply_text(
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ *POST RESCHEDULED*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📅 New scheduled time:\n\n"
            f"⏰ {escape_markdown_v2(format_datetime(new_time_local))}\n"
            f"🌍 Timezone: `{escape_markdown_v2(TZ)}`\n\n"
            f"💡 View scheduled posts in menu\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
    else:
        await update.message.reply_text(
            "❌ Failed to reschedule post\\. Please try again\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
