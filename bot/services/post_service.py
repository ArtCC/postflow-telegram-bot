"""
Post Service
Business logic for managing posts.
"""

from datetime import datetime
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session

from bot.database import Post, Thread, ScheduledPost, PostStatus
from bot.database.database import get_session
from bot.utils.formatting import split_into_tweets
from bot.config import logger, MAX_TWEET_LENGTH


class PostService:
    """Service for managing posts"""
    
    @staticmethod
    def create_post(
        content: str,
        created_by_ai: bool = False,
        ai_prompt: Optional[str] = None
    ) -> Optional[Post]:
        """
        Create a new post.
        
        Args:
            content: Post content
            created_by_ai: Whether the post was created by AI
            ai_prompt: AI prompt if applicable
            
        Returns:
            Created Post object or None if failed
        """
        try:
            with get_session() as session:
                post = Post(
                    content=content,
                    created_by_ai=created_by_ai,
                    ai_prompt=ai_prompt,
                    status=PostStatus.DRAFT,
                )
                session.add(post)
                session.commit()
                session.refresh(post)
                
                # Create thread entries if content is long
                tweets = split_into_tweets(content)
                if len(tweets) > 1:
                    for index, tweet_content in enumerate(tweets, 1):
                        thread = Thread(
                            post_id=post.id,
                            tweet_index=index,
                            content=tweet_content,
                        )
                        session.add(thread)
                    session.commit()
                    session.refresh(post)
                    logger.info(f"Created post {post.id} with {len(tweets)} tweets")
                else:
                    logger.info(f"Created post {post.id}")
                
                # Load relationships before session closes
                _ = post.threads
                _ = post.scheduled_post
                
                # Detach from session so it can be used outside
                session.expunge(post)
                
                return post
                
        except Exception as e:
            logger.error(f"Failed to create post: {e}")
            return None
    
    @staticmethod
    def get_post(post_id: int) -> Optional[Post]:
        """
        Get a post by ID.
        
        Args:
            post_id: Post ID
            
        Returns:
            Post object or None if not found
        """
        try:
            with get_session() as session:
                post = session.query(Post).filter(Post.id == post_id).first()
                if post:
                    # Eagerly load relationships before session closes
                    _ = post.threads
                    _ = post.scheduled_post
                    # Detach from session
                    session.expunge(post)
                return post
        except Exception as e:
            logger.error(f"Failed to get post {post_id}: {e}")
            return None
    
    @staticmethod
    def update_post_status(
        post_id: int,
        status: PostStatus,
        twitter_id: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """
        Update post status.
        
        Args:
            post_id: Post ID
            status: New status
            twitter_id: Twitter ID if published
            error_message: Error message if failed
            
        Returns:
            True if updated successfully
        """
        try:
            with get_session() as session:
                post = session.query(Post).filter(Post.id == post_id).first()
                if not post:
                    return False
                
                post.status = status
                if twitter_id:
                    post.twitter_id = twitter_id
                if error_message:
                    post.error_message = error_message
                if status == PostStatus.PUBLISHED:
                    post.published_at = datetime.utcnow()
                
                session.commit()
                logger.info(f"Updated post {post_id} status to {status}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to update post {post_id}: {e}")
            return False
    
    @staticmethod
    def update_post_content(post_id: int, content: str) -> bool:
        """
        Update post content.
        
        Args:
            post_id: Post ID
            content: New content
            
        Returns:
            True if updated successfully
        """
        try:
            with get_session() as session:
                post = session.query(Post).filter(Post.id == post_id).first()
                if not post:
                    return False
                
                post.content = content
                
                # Delete existing threads and recreate if needed
                session.query(Thread).filter(Thread.post_id == post_id).delete()
                
                # Create new thread entries if content is long
                tweets = split_into_tweets(content)
                if len(tweets) > 1:
                    for index, tweet_content in enumerate(tweets, 1):
                        thread = Thread(
                            post_id=post.id,
                            tweet_index=index,
                            content=tweet_content,
                        )
                        session.add(thread)
                
                session.commit()
                logger.info(f"Updated post {post_id} content")
                return True
                
        except Exception as e:
            logger.error(f"Failed to update post {post_id} content: {e}")
            return False
    
    @staticmethod
    def delete_post(post_id: int) -> bool:
        """
        Delete a post.
        
        Args:
            post_id: Post ID
            
        Returns:
            True if deleted successfully
        """
        try:
            with get_session() as session:
                post = session.query(Post).filter(Post.id == post_id).first()
                if not post:
                    return False
                
                session.delete(post)
                session.commit()
                logger.info(f"Deleted post {post_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to delete post {post_id}: {e}")
            return False
    
    @staticmethod
    def get_all_posts(limit: int = 50) -> List[Post]:
        """
        Get all posts.
        
        Args:
            limit: Maximum number of posts to return
            
        Returns:
            List of Post objects
        """
        try:
            with get_session() as session:
                posts = session.query(Post).order_by(Post.created_at.desc()).limit(limit).all()
                # Load relationships and detach
                for post in posts:
                    _ = post.threads
                    _ = post.scheduled_post
                    session.expunge(post)
                return posts
        except Exception as e:
            logger.error(f"Failed to get posts: {e}")
            return []

    @staticmethod
    def get_draft_posts(limit: int = 50) -> List[Post]:
        """
        Get draft posts.

        Args:
            limit: Maximum number of drafts to return

        Returns:
            List of Post objects
        """
        try:
            with get_session() as session:
                posts = (
                    session.query(Post)
                    .filter(Post.status == PostStatus.DRAFT)
                    .order_by(Post.created_at.desc())
                    .limit(limit)
                    .all()
                )
                for post in posts:
                    _ = post.threads
                    _ = post.scheduled_post
                    session.expunge(post)
                return posts
        except Exception as e:
            logger.error(f"Failed to get draft posts: {e}")
            return []
    
    @staticmethod
    def get_scheduled_posts() -> List[Tuple[Post, ScheduledPost]]:
        """
        Get all scheduled posts.
        
        Returns:
            List of (Post, ScheduledPost) tuples
        """
        try:
            with get_session() as session:
                results = (
                    session.query(Post, ScheduledPost)
                    .join(ScheduledPost)
                    .filter(ScheduledPost.status == "pending")
                    .filter(Post.status == PostStatus.SCHEDULED)
                    .order_by(ScheduledPost.scheduled_for)
                    .all()
                )
                # Detach objects from session
                for post, scheduled in results:
                    _ = post.threads
                    session.expunge(post)
                    session.expunge(scheduled)
                return results
        except Exception as e:
            logger.error(f"Failed to get scheduled posts: {e}")
            return []
    
    @staticmethod
    def schedule_post(
        post_id: int,
        scheduled_for: datetime,
        job_id: str
    ) -> Optional[ScheduledPost]:
        """
        Schedule a post.
        
        Args:
            post_id: Post ID
            scheduled_for: When to publish
            job_id: APScheduler job ID
            
        Returns:
            ScheduledPost object or None if failed
        """
        try:
            with get_session() as session:
                # Update post status
                post = session.query(Post).filter(Post.id == post_id).first()
                if not post:
                    return None
                
                post.status = PostStatus.SCHEDULED
                
                # Create scheduled post entry
                scheduled_post = ScheduledPost(
                    post_id=post_id,
                    scheduled_for=scheduled_for,
                    job_id=job_id,
                    status="pending",
                )
                session.add(scheduled_post)
                session.commit()
                session.refresh(scheduled_post)
                
                logger.info(f"Scheduled post {post_id} for {scheduled_for}")
                
                # Detach from session
                session.expunge(scheduled_post)
                return scheduled_post
                
        except Exception as e:
            logger.error(f"Failed to schedule post {post_id}: {e}")
            return None
    
    @staticmethod
    def cancel_scheduled_post(post_id: int) -> bool:
        """
        Cancel a scheduled post.
        
        Args:
            post_id: Post ID
            
        Returns:
            True if cancelled successfully
        """
        try:
            with get_session() as session:
                scheduled_post = session.query(ScheduledPost).filter(
                    ScheduledPost.post_id == post_id
                ).first()
                
                if not scheduled_post:
                    return False
                
                scheduled_post.status = "cancelled"
                
                post = session.query(Post).filter(Post.id == post_id).first()
                if post:
                    post.status = PostStatus.CANCELLED
                
                session.commit()
                logger.info(f"Cancelled scheduled post {post_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to cancel scheduled post {post_id}: {e}")
            return False
    
    @staticmethod
    def get_post_statistics() -> dict:
        """
        Get statistics about posts.
        
        Returns:
            Dictionary with statistics
        """
        try:
            with get_session() as session:
                total = session.query(Post).count()
                published = session.query(Post).filter(Post.status == PostStatus.PUBLISHED).count()
                scheduled = session.query(Post).filter(Post.status == PostStatus.SCHEDULED).count()
                failed = session.query(Post).filter(Post.status == PostStatus.FAILED).count()
                
                return {
                    "total": total,
                    "published": published,
                    "scheduled": scheduled,
                    "failed": failed,
                    "draft": total - published - scheduled - failed,
                }
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {"total": 0, "published": 0, "scheduled": 0, "failed": 0, "draft": 0}

    @staticmethod
    def reschedule_post(post_id: int, new_scheduled_for: datetime) -> bool:
        """
        Update the scheduled time for a post.
        
        Args:
            post_id: Post ID
            new_scheduled_for: New scheduled datetime
            
        Returns:
            True if rescheduled successfully
        """
        try:
            with get_session() as session:
                scheduled_post = session.query(ScheduledPost).filter(
                    ScheduledPost.post_id == post_id
                ).first()
                
                if not scheduled_post:
                    return False
                
                scheduled_post.scheduled_for = new_scheduled_for
                session.commit()
                logger.info(f"Rescheduled post {post_id} to {new_scheduled_for}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to reschedule post {post_id}: {e}")
            return False

    @staticmethod
    def update_scheduled_job_id(post_id: int, job_id: str) -> bool:
        """
        Update the job ID for a scheduled post.

        Args:
            post_id: Post ID
            job_id: New job ID

        Returns:
            True if updated successfully
        """
        try:
            with get_session() as session:
                scheduled_post = session.query(ScheduledPost).filter(
                    ScheduledPost.post_id == post_id
                ).first()

                if not scheduled_post:
                    return False

                scheduled_post.job_id = job_id
                session.commit()
                logger.info(f"Updated scheduled job ID for post {post_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to update scheduled job ID for post {post_id}: {e}")
            return False
