"""
Twitter Service
Integration with Twitter/X API using Tweepy.
"""

import tweepy
from typing import List, Optional, Tuple
from bot.config import (
    logger,
    TWITTER_BACKEND,
    TWITTER_API_KEY,
    TWITTER_API_SECRET,
    TWITTER_ACCESS_TOKEN,
    TWITTER_ACCESS_TOKEN_SECRET,
    TWITTER_ENABLED,
    XQUIK_API_BASE_URL,
    XQUIK_API_KEY,
    XQUIK_ACCOUNT,
)
from bot.services.xquik_client import XquikClient, is_xquik_pending_id
from bot.utils.i18n import DEFAULT_LOCALE, t


class TwitterServiceError(Exception):
    """Custom exception for Twitter service errors"""
    pass


class TwitterService:
    """Service for interacting with Twitter API"""
    
    def __init__(self):
        """Initialize Twitter API client"""
        self.client = None
        self.api = None
        self.enabled = TWITTER_ENABLED
        self.backend = TWITTER_BACKEND
        
        if self.enabled:
            if self.backend == "xquik":
                self.client = XquikClient(
                    XQUIK_API_KEY,
                    XQUIK_ACCOUNT,
                    base_url=XQUIK_API_BASE_URL,
                )
                logger.info("Xquik posting backend initialized")
                return

            try:
                # Log credential status (not the actual values!)
                logger.info(f"Twitter API Key configured: {bool(TWITTER_API_KEY)}")
                logger.info(f"Twitter API Secret configured: {bool(TWITTER_API_SECRET)}")
                logger.info(f"Twitter Access Token configured: {bool(TWITTER_ACCESS_TOKEN)}")
                logger.info(f"Twitter Access Token Secret configured: {bool(TWITTER_ACCESS_TOKEN_SECRET)}")
                
                # Initialize Twitter API v2 client
                self.client = tweepy.Client(
                    consumer_key=TWITTER_API_KEY,
                    consumer_secret=TWITTER_API_SECRET,
                    access_token=TWITTER_ACCESS_TOKEN,
                    access_token_secret=TWITTER_ACCESS_TOKEN_SECRET
                )

                # Initialize Twitter API v1.1 for media upload
                auth = tweepy.OAuth1UserHandler(
                    TWITTER_API_KEY,
                    TWITTER_API_SECRET,
                    TWITTER_ACCESS_TOKEN,
                    TWITTER_ACCESS_TOKEN_SECRET
                )
                self.api = tweepy.API(auth)
                
                # Defer auth test to explicit status checks to avoid rate limits on startup
                logger.info("Twitter API client initialized (auth check deferred)")
                
            except tweepy.TweepyException as e:
                logger.error(f"Failed to initialize Twitter API: {e}")
                logger.error(f"Full error details: {repr(e)}")
                self.enabled = False
                self.client = None
                logger.warning("Twitter API disabled due to initialization error")
            except Exception as e:
                logger.error(f"Unexpected error initializing Twitter API: {e}")
                self.enabled = False
                self.client = None
                logger.warning("Twitter API disabled due to initialization error")
    
    def is_enabled(self) -> bool:
        """Check if Twitter service is enabled and authenticated"""
        return self.enabled and self.client is not None
    
    def post_tweet(self, text: str, locale: Optional[str] = None) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Post a single tweet.
        
        Args:
            text: Tweet content (max 280 chars)
            
        Returns:
            Tuple of (success, tweet_id, error_message)
        """
        locale = locale or DEFAULT_LOCALE
        if not self.is_enabled():
            return False, None, t("errors.twitter_disabled", locale)
        
        try:
            if self.backend == "xquik":
                return self.client.create_tweet(text=text)

            response = self.client.create_tweet(text=text)
            tweet_id = response.data['id']
            logger.info(f"Tweet posted successfully: {tweet_id}")
            return True, str(tweet_id), None
            
        except tweepy.TweepyException as e:
            error_msg = self._parse_twitter_error(e, locale)
            logger.error(f"Failed to post tweet: {error_msg}")
            return False, None, error_msg

    def post_tweet_with_media(self, text: str, media_path: str, locale: Optional[str] = None) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Post a tweet with a single image.

        Args:
            text: Tweet content (max 280 chars)
            media_path: Local path to image file

        Returns:
            Tuple of (success, tweet_id, error_message)
        """
        locale = locale or DEFAULT_LOCALE
        if self.backend == "xquik":
            return False, None, t("errors.xquik_media_unsupported", locale)

        if not self.is_enabled() or self.api is None:
            return False, None, t("errors.twitter_disabled", locale)

        try:
            media = self.api.media_upload(media_path)
            response = self.client.create_tweet(text=text, media_ids=[media.media_id])
            tweet_id = response.data['id']
            logger.info(f"Tweet with media posted successfully: {tweet_id}")
            return True, str(tweet_id), None

        except tweepy.TweepyException as e:
            error_msg = self._parse_twitter_error(e, locale)
            logger.error(f"Failed to post tweet with media: {error_msg}")
            return False, None, error_msg
    
    def post_thread(self, tweets: List[str], locale: Optional[str] = None) -> Tuple[bool, List[str], Optional[str]]:
        """
        Post a thread of tweets.
        
        Args:
            tweets: List of tweet texts
            
        Returns:
            Tuple of (success, list of tweet_ids, error_message)
        """
        locale = locale or DEFAULT_LOCALE
        if not self.is_enabled():
            return False, [], t("errors.twitter_disabled", locale)
        
        if not tweets:
            return False, [], t("errors.twitter_no_tweets", locale)

        if self.backend == "xquik":
            return False, [], t("errors.xquik_threads_unsupported", locale)
        
        tweet_ids = []
        previous_tweet_id = None
        
        try:
            for i, tweet_text in enumerate(tweets):
                # Reply to previous tweet if it's not the first one
                if previous_tweet_id:
                    response = self.client.create_tweet(
                        text=tweet_text,
                        in_reply_to_tweet_id=previous_tweet_id
                    )
                else:
                    response = self.client.create_tweet(text=tweet_text)
                
                tweet_id = str(response.data['id'])
                tweet_ids.append(tweet_id)
                previous_tweet_id = tweet_id
                
                logger.info(f"Posted tweet {i+1}/{len(tweets)}: {tweet_id}")
            
            logger.info(f"Thread posted successfully: {len(tweet_ids)} tweets")
            return True, tweet_ids, None
            
        except tweepy.TweepyException as e:
            error_msg = self._parse_twitter_error(e, locale)
            logger.error(f"Failed to post thread: {error_msg}")
            # Return partial success if some tweets were posted
            return False, tweet_ids, error_msg
    
    def delete_tweet(self, tweet_id: str, locale: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Delete a tweet.
        
        Args:
            tweet_id: ID of the tweet to delete
            
        Returns:
            Tuple of (success, error_message)
        """
        locale = locale or DEFAULT_LOCALE
        if self.backend == "xquik":
            return False, t("errors.xquik_delete_unsupported", locale)

        if not self.is_enabled():
            return False, t("errors.twitter_disabled", locale)
        
        try:
            self.client.delete_tweet(tweet_id)
            logger.info(f"Tweet deleted successfully: {tweet_id}")
            return True, None
            
        except tweepy.TweepyException as e:
            error_msg = self._parse_twitter_error(e, locale)
            logger.error(f"Failed to delete tweet {tweet_id}: {error_msg}")
            return False, error_msg
    
    def get_tweet(self, tweet_id: str) -> Optional[dict]:
        """
        Get tweet details.
        
        Args:
            tweet_id: ID of the tweet
            
        Returns:
            Tweet data or None if failed
        """
        if not self.is_enabled() or self.backend == "xquik" or is_xquik_pending_id(tweet_id):
            return None
        
        try:
            response = self.client.get_tweet(tweet_id)
            return response.data
            
        except tweepy.TweepyException as e:
            logger.error(f"Failed to get tweet {tweet_id}: {e}")
            return None
    
    def _parse_twitter_error(self, error: tweepy.TweepyException, locale: Optional[str] = None) -> str:
        """
        Parse Twitter API error into user-friendly message.
        
        Args:
            error: Tweepy exception
            
        Returns:
            User-friendly error message
        """
        locale = locale or DEFAULT_LOCALE
        error_str = str(error)
        
        # Rate limit
        if "429" in error_str or "rate limit" in error_str.lower():
            return t("errors.twitter_rate_limit", locale)
        
        # Authentication errors
        if "401" in error_str or "403" in error_str:
            return t("errors.twitter_auth_failed", locale)
        
        # Duplicate tweet
        if "duplicate" in error_str.lower():
            return t("errors.twitter_duplicate", locale)
        
        # Tweet too long
        if "too long" in error_str.lower() or "length" in error_str.lower():
            return t("errors.twitter_too_long", locale)
        
        # Connection errors
        if "connection" in error_str.lower() or "timeout" in error_str.lower():
            return t("errors.twitter_connection", locale)
        
        # Service unavailable
        if "503" in error_str:
            return t("errors.twitter_unavailable", locale)
        
        # Generic error
        return t("errors.twitter_generic", locale, error=error_str[:200])
    
    def test_connection(self, locale: Optional[str] = None) -> Tuple[bool, str]:
        """
        Test Twitter API connection.
        
        Returns:
            Tuple of (success, message)
        """
        locale = locale or DEFAULT_LOCALE
        if self.backend == "xquik":
            if self.is_enabled():
                return True, t("errors.twitter_connected", locale, username="Xquik")
            return False, t("errors.twitter_not_configured", locale)

        if not self.enabled:
            return False, t("errors.twitter_not_configured", locale)
        
        try:
            user = self.client.get_me()
            username = user.data.username
            return True, t("errors.twitter_connected", locale, username=username)
            
        except tweepy.TweepyException as e:
            error_msg = self._parse_twitter_error(e, locale)
            return False, error_msg
        except Exception as e:
            return False, t("errors.twitter_connection_detail", locale, error=str(e))
