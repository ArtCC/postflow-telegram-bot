"""
Twitter Service
Integration with Twitter/X API using Tweepy.
"""

import tweepy
from typing import List, Optional, Tuple
from bot.config import (
    logger,
    TWITTER_API_KEY,
    TWITTER_API_SECRET,
    TWITTER_ACCESS_TOKEN,
    TWITTER_ACCESS_TOKEN_SECRET,
    TWITTER_ENABLED,
)


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
        
        if self.enabled:
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
                
                # Test authentication
                me = self.client.get_me()
                if me.data:
                    logger.info(f"Twitter API initialized successfully. Logged in as @{me.data.username}")
                else:
                    logger.warning("Twitter API initialized but could not verify user")
                
            except tweepy.TweepyException as e:
                logger.error(f"Failed to initialize Twitter API: {e}")
                logger.error(f"Full error details: {repr(e)}")
                self.enabled = False
                raise TwitterServiceError(f"Twitter authentication failed: {str(e)}")
    
    def is_enabled(self) -> bool:
        """Check if Twitter service is enabled and authenticated"""
        return self.enabled and self.client is not None
    
    def post_tweet(self, text: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Post a single tweet.
        
        Args:
            text: Tweet content (max 280 chars)
            
        Returns:
            Tuple of (success, tweet_id, error_message)
        """
        if not self.is_enabled():
            return False, None, "Twitter API is not configured or disabled"
        
        try:
            response = self.client.create_tweet(text=text)
            tweet_id = response.data['id']
            logger.info(f"Tweet posted successfully: {tweet_id}")
            return True, str(tweet_id), None
            
        except tweepy.TweepyException as e:
            error_msg = self._parse_twitter_error(e)
            logger.error(f"Failed to post tweet: {error_msg}")
            return False, None, error_msg
    
    def post_thread(self, tweets: List[str]) -> Tuple[bool, List[str], Optional[str]]:
        """
        Post a thread of tweets.
        
        Args:
            tweets: List of tweet texts
            
        Returns:
            Tuple of (success, list of tweet_ids, error_message)
        """
        if not self.is_enabled():
            return False, [], "Twitter API is not configured or disabled"
        
        if not tweets:
            return False, [], "No tweets provided"
        
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
            error_msg = self._parse_twitter_error(e)
            logger.error(f"Failed to post thread: {error_msg}")
            # Return partial success if some tweets were posted
            return False, tweet_ids, error_msg
    
    def delete_tweet(self, tweet_id: str) -> Tuple[bool, Optional[str]]:
        """
        Delete a tweet.
        
        Args:
            tweet_id: ID of the tweet to delete
            
        Returns:
            Tuple of (success, error_message)
        """
        if not self.is_enabled():
            return False, "Twitter API is not configured or disabled"
        
        try:
            self.client.delete_tweet(tweet_id)
            logger.info(f"Tweet deleted successfully: {tweet_id}")
            return True, None
            
        except tweepy.TweepyException as e:
            error_msg = self._parse_twitter_error(e)
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
        if not self.is_enabled():
            return None
        
        try:
            response = self.client.get_tweet(tweet_id)
            return response.data
            
        except tweepy.TweepyException as e:
            logger.error(f"Failed to get tweet {tweet_id}: {e}")
            return None
    
    def _parse_twitter_error(self, error: tweepy.TweepyException) -> str:
        """
        Parse Twitter API error into user-friendly message.
        
        Args:
            error: Tweepy exception
            
        Returns:
            User-friendly error message
        """
        error_str = str(error)
        
        # Rate limit
        if "429" in error_str or "rate limit" in error_str.lower():
            return "Rate limit exceeded. Please wait before posting again."
        
        # Authentication errors
        if "401" in error_str or "403" in error_str:
            return "Authentication failed. Check your API credentials."
        
        # Duplicate tweet
        if "duplicate" in error_str.lower():
            return "This tweet appears to be a duplicate."
        
        # Tweet too long
        if "too long" in error_str.lower() or "length" in error_str.lower():
            return "Tweet exceeds 280 character limit."
        
        # Connection errors
        if "connection" in error_str.lower() or "timeout" in error_str.lower():
            return "Connection error. Check your internet connection."
        
        # Service unavailable
        if "503" in error_str:
            return "Twitter service temporarily unavailable."
        
        # Generic error
        return f"Twitter error: {error_str[:200]}"
    
    def test_connection(self) -> Tuple[bool, str]:
        """
        Test Twitter API connection.
        
        Returns:
            Tuple of (success, message)
        """
        if not self.enabled:
            return False, "Twitter API credentials not configured"
        
        try:
            user = self.client.get_me()
            username = user.data.username
            return True, f"Connected as @{username}"
            
        except tweepy.TweepyException as e:
            error_msg = self._parse_twitter_error(e)
            return False, error_msg
