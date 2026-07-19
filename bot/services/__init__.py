"""
Bot Services
External API integrations and core business logic.
"""

__all__ = [
    'TwitterService',
    'OpenAIService',
    'SchedulerService',
    'PostService',
]


def __getattr__(name):
    """Lazily import services so standalone helpers stay lightweight."""
    if name == 'TwitterService':
        from bot.services.twitter_service import TwitterService
        return TwitterService
    if name == 'OpenAIService':
        from bot.services.openai_service import OpenAIService
        return OpenAIService
    if name == 'SchedulerService':
        from bot.services.scheduler_service import SchedulerService
        return SchedulerService
    if name == 'PostService':
        from bot.services.post_service import PostService
        return PostService
    raise AttributeError(f"module 'bot.services' has no attribute '{name}'")
