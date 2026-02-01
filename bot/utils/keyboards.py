"""
Keyboard Utilities
Helper functions for creating inline keyboards.
"""

from typing import List, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Create the main menu keyboard with inline buttons."""
    keyboard = [
        [
            InlineKeyboardButton("✍️ New Post", callback_data="new_post"),
            InlineKeyboardButton("📅 Scheduled", callback_data="scheduled"),
        ],
        [
            InlineKeyboardButton("📊 Statistics", callback_data="statistics"),
            InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
        ],
        [
            InlineKeyboardButton("ℹ️ Help", callback_data="help"),
            InlineKeyboardButton("🔄 Status", callback_data="status"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_back_keyboard() -> InlineKeyboardMarkup:
    """Create a keyboard with a back button."""
    keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="menu")]]
    return InlineKeyboardMarkup(keyboard)


def get_new_post_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard for new post options."""
    keyboard = [
        [InlineKeyboardButton("✏️ Write Manually", callback_data="post_manual")],
    ]
    
    # Add AI option only if OpenAI is enabled
    from bot.config import OPENAI_ENABLED
    if OPENAI_ENABLED:
        keyboard.insert(0, [InlineKeyboardButton("🤖 Generate with AI", callback_data="post_ai")])
    
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="menu")])
    return InlineKeyboardMarkup(keyboard)


def get_post_preview_keyboard(post_id: int, is_thread: bool = False) -> InlineKeyboardMarkup:
    """
    Create keyboard for post preview actions.
    
    Args:
        post_id: Post ID
        is_thread: Whether the post is a thread
        
    Returns:
        Inline keyboard markup
    """
    label = "🚀 Publish Thread" if is_thread else "🚀 Publish Now"
    
    keyboard = [
        [
            InlineKeyboardButton(label, callback_data=f"publish_{post_id}"),
            InlineKeyboardButton("📅 Schedule", callback_data=f"schedule_{post_id}"),
        ],
        [
            InlineKeyboardButton("✏️ Edit", callback_data=f"edit_{post_id}"),
            InlineKeyboardButton("❌ Cancel", callback_data=f"delete_{post_id}"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_schedule_keyboard(post_id: int) -> InlineKeyboardMarkup:
    """Create keyboard for scheduling options."""
    keyboard = [
        [
            InlineKeyboardButton("⏰ In 1 hour", callback_data=f"quick_schedule_1h_{post_id}"),
            InlineKeyboardButton("⏰ In 3 hours", callback_data=f"quick_schedule_3h_{post_id}"),
        ],
        [
            InlineKeyboardButton("📆 Tomorrow 9am", callback_data=f"quick_schedule_tomorrow_{post_id}"),
            InlineKeyboardButton("📆 Custom date", callback_data=f"custom_schedule_{post_id}"),
        ],
        [InlineKeyboardButton("🔙 Back", callback_data=f"preview_{post_id}")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_scheduled_posts_keyboard(scheduled_posts: List[tuple], page: int = 0, per_page: int = 5) -> InlineKeyboardMarkup:
    """
    Create keyboard for scheduled posts list with pagination.
    
    Args:
        scheduled_posts: List of (post_id, preview, scheduled_for) tuples
        page: Current page number
        per_page: Items per page
        
    Returns:
        Inline keyboard markup
    """
    keyboard = []
    
    # Calculate pagination
    start = page * per_page
    end = start + per_page
    page_posts = scheduled_posts[start:end]
    
    # Add post buttons
    for post_id, preview, _ in page_posts:
        keyboard.append([
            InlineKeyboardButton(
                f"📝 {preview}",
                callback_data=f"view_scheduled_{post_id}"
            )
        ])
    
    # Add pagination buttons if needed
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ Previous", callback_data=f"scheduled_page_{page-1}"))
    if end < len(scheduled_posts):
        nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f"scheduled_page_{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Add back button
    keyboard.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="menu")])
    
    return InlineKeyboardMarkup(keyboard)


def get_scheduled_post_actions_keyboard(post_id: int) -> InlineKeyboardMarkup:
    """Create keyboard for scheduled post actions."""
    keyboard = [
        [
            InlineKeyboardButton("👁️ View", callback_data=f"preview_{post_id}"),
            InlineKeyboardButton("✏️ Edit Time", callback_data=f"reschedule_{post_id}"),
        ],
        [
            InlineKeyboardButton("🗑️ Delete", callback_data=f"confirm_delete_scheduled_{post_id}"),
        ],
        [InlineKeyboardButton("🔙 Back", callback_data="scheduled")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_confirm_delete_keyboard(post_id: int, is_scheduled: bool = False) -> InlineKeyboardMarkup:
    """Create keyboard for delete confirmation."""
    callback_prefix = "scheduled" if is_scheduled else "post"
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes, delete", callback_data=f"confirm_delete_{callback_prefix}_{post_id}"),
            InlineKeyboardButton("❌ No, cancel", callback_data=f"cancel_delete_{post_id}"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_error_keyboard(show_retry: bool = False, show_settings: bool = False) -> InlineKeyboardMarkup:
    """Create keyboard for error messages."""
    keyboard = []
    
    if show_retry:
        keyboard.append([InlineKeyboardButton("🔄 Retry", callback_data="retry_last_action")])
    
    if show_settings:
        keyboard.append([InlineKeyboardButton("⚙️ Settings", callback_data="settings")])
    
    keyboard.append([InlineKeyboardButton("🔙 Menu", callback_data="menu")])
    
    return InlineKeyboardMarkup(keyboard)
