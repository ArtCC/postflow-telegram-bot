"""
Authorization Utilities
Helper functions for user authorization.
"""

from bot.config import TELEGRAM_USER_ID


def is_authorized(user_id: int) -> bool:
    """
    Check if the user ID is authorized to use the bot.
    
    Args:
        user_id: Telegram user ID
        
    Returns:
        True if authorized, False otherwise
    """
    return user_id == TELEGRAM_USER_ID
