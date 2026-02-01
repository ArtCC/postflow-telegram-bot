"""
Post Handlers
Handlers for creating, publishing, and managing posts.
"""

from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes

from bot.config import logger, MAX_TWEET_LENGTH
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
    
    # Format scheduled posts for display
    posts_data = []
    for post, sched in scheduled:
        preview = truncate_text(post.content, 40)
        posts_data.append((post.id, preview, sched.scheduled_for))
    
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
