"""
Formatting Utilities
Helper functions for text formatting and manipulation.
"""

import re
from datetime import datetime
from typing import List
from bot.config import MAX_TWEET_LENGTH


def escape_markdown_v2(text: str) -> str:
    """
    Escape special characters for Telegram MarkdownV2 format.
    
    Args:
        text: Text to escape
        
    Returns:
        Escaped text safe for MarkdownV2
    """
    if not text:
        return ""
    
    # All characters that need escaping in MarkdownV2
    # Order matters: escape backslash first to avoid double-escaping
    escape_chars = ['\\', '_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    result = str(text)
    for char in escape_chars:
        result = result.replace(char, f'\\{char}')
    
    return result


def format_datetime(dt: datetime, include_time: bool = True) -> str:
    """
    Format datetime to human-readable string.
    
    Args:
        dt: Datetime object
        include_time: Whether to include time
        
    Returns:
        Formatted datetime string
    """
    if include_time:
        return dt.strftime("%b %d, %Y at %H:%M")
    return dt.strftime("%b %d, %Y")


def split_into_tweets(content: str, max_length: int = MAX_TWEET_LENGTH) -> List[str]:
    """
    Split long content into multiple tweets respecting character limit.
    Tries to split at sentence boundaries or spaces.
    
    Args:
        content: Full content to split
        max_length: Maximum characters per tweet (default: 280)
        
    Returns:
        List of tweet strings
    """
    if len(content) <= max_length:
        return [content]
    
    tweets = []
    remaining = content
    
    # Reserve space for thread numbering (e.g., "1/5 ")
    # We'll add numbering later, so reserve ~6 chars
    effective_max = max_length - 6
    
    while remaining:
        if len(remaining) <= effective_max:
            tweets.append(remaining)
            break
        
        # Try to find a good breaking point
        chunk = remaining[:effective_max]
        
        # Try to break at sentence end (. ! ?)
        sentence_end = max(
            chunk.rfind('. '),
            chunk.rfind('! '),
            chunk.rfind('? ')
        )
        
        if sentence_end > effective_max * 0.6:  # At least 60% of max length
            split_point = sentence_end + 2  # Include punctuation and space
        else:
            # Try to break at paragraph
            paragraph_break = chunk.rfind('\n\n')
            if paragraph_break > effective_max * 0.5:
                split_point = paragraph_break + 2
            else:
                # Try to break at line break
                line_break = chunk.rfind('\n')
                if line_break > effective_max * 0.5:
                    split_point = line_break + 1
                else:
                    # Last resort: break at space
                    space = chunk.rfind(' ')
                    if space > effective_max * 0.7:
                        split_point = space + 1
                    else:
                        # Force break at max length
                        split_point = effective_max
        
        tweets.append(remaining[:split_point].strip())
        remaining = remaining[split_point:].strip()
    
    # Add thread numbering
    total = len(tweets)
    if total > 1:
        numbered_tweets = []
        for i, tweet in enumerate(tweets, 1):
            numbered_tweets.append(f"{i}/{total} {tweet}")
        return numbered_tweets
    
    return tweets


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text to maximum length with suffix.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def format_relative_time(dt: datetime) -> str:
    """
    Format datetime as relative time (e.g., "in 2 hours", "tomorrow").
    
    Args:
        dt: Future datetime
        
    Returns:
        Relative time string
    """
    now = datetime.utcnow()
    delta = dt - now
    
    if delta.total_seconds() < 0:
        return "in the past"
    
    seconds = delta.total_seconds()
    
    if seconds < 3600:  # Less than 1 hour
        minutes = int(seconds / 60)
        return f"in {minutes} min" if minutes > 1 else "in 1 min"
    
    elif seconds < 86400:  # Less than 1 day
        hours = int(seconds / 3600)
        return f"in {hours} hours" if hours > 1 else "in 1 hour"
    
    elif seconds < 172800:  # Less than 2 days
        return "tomorrow"
    
    elif seconds < 604800:  # Less than 1 week
        days = int(seconds / 86400)
        return f"in {days} days"
    
    else:
        return format_datetime(dt, include_time=False)


def count_chars(text: str) -> int:
    """
    Count characters in text (useful for tweet length validation).
    
    Args:
        text: Text to count
        
    Returns:
        Character count
    """
    return len(text)


def validate_tweet_length(text: str) -> tuple[bool, int]:
    """
    Validate if text fits in a single tweet.
    
    Args:
        text: Text to validate
        
    Returns:
        Tuple of (is_valid, character_count)
    """
    char_count = count_chars(text)
    return (char_count <= MAX_TWEET_LENGTH, char_count)
