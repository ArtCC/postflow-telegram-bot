"""
Topic Service
Business logic for managing topic presets for AI post generation.
"""

from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from bot.config import logger
from bot.database.database import SessionLocal
from bot.database.models import Topic


# Maximum topics per user
MAX_TOPICS_PER_USER = 10

# Topic name constraints
MIN_TOPIC_NAME_LENGTH = 3
MAX_TOPIC_NAME_LENGTH = 30


class TopicService:
    """Service for managing topic presets"""

    @staticmethod
    def create_topic(user_id: int, name: str) -> Tuple[bool, Optional[Topic], Optional[str]]:
        """
        Create a new topic preset for a user.
        
        Args:
            user_id: Telegram user ID
            name: Topic name
            
        Returns:
            Tuple of (success, topic, error_message)
        """
        db: Session = SessionLocal()
        try:
            # Validate topic name length
            name = name.strip()
            if len(name) < MIN_TOPIC_NAME_LENGTH:
                return False, None, f"Topic name must be at least {MIN_TOPIC_NAME_LENGTH} characters"
            
            if len(name) > MAX_TOPIC_NAME_LENGTH:
                return False, None, f"Topic name must be at most {MAX_TOPIC_NAME_LENGTH} characters"
            
            # Check if user has reached max topics
            topic_count = db.query(func.count(Topic.id)).filter(
                Topic.user_id == user_id
            ).scalar()
            
            if topic_count >= MAX_TOPICS_PER_USER:
                return False, None, f"Maximum of {MAX_TOPICS_PER_USER} topics reached. Delete one to add more."
            
            # Check for duplicates (case-insensitive)
            existing = db.query(Topic).filter(
                Topic.user_id == user_id,
                func.lower(Topic.name) == func.lower(name)
            ).first()
            
            if existing:
                return False, None, f"Topic '{name}' already exists"
            
            # Create topic
            topic = Topic(user_id=user_id, name=name)
            db.add(topic)
            db.commit()
            db.refresh(topic)
            
            logger.info(f"Created topic '{name}' for user {user_id}")
            return True, topic, None
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating topic: {e}")
            return False, None, f"Error creating topic: {str(e)}"
        finally:
            db.close()

    @staticmethod
    def get_user_topics(user_id: int) -> List[Topic]:
        """
        Get all topics for a user.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            List of topics
        """
        db: Session = SessionLocal()
        try:
            topics = db.query(Topic).filter(
                Topic.user_id == user_id
            ).order_by(Topic.name).all()
            
            return topics
        except Exception as e:
            logger.error(f"Error fetching topics: {e}")
            return []
        finally:
            db.close()

    @staticmethod
    def get_topic(topic_id: int) -> Optional[Topic]:
        """
        Get a specific topic by ID.
        
        Args:
            topic_id: Topic ID
            
        Returns:
            Topic or None if not found
        """
        db: Session = SessionLocal()
        try:
            topic = db.query(Topic).filter(Topic.id == topic_id).first()
            return topic
        except Exception as e:
            logger.error(f"Error fetching topic: {e}")
            return None
        finally:
            db.close()

    @staticmethod
    def get_topic_for_user(topic_id: int, user_id: int) -> Optional[Topic]:
        """
        Get a specific topic by ID for a given user.

        Args:
            topic_id: Topic ID
            user_id: Telegram user ID

        Returns:
            Topic or None if not found
        """
        db: Session = SessionLocal()
        try:
            topic = db.query(Topic).filter(
                Topic.id == topic_id,
                Topic.user_id == user_id
            ).first()
            return topic
        except Exception as e:
            logger.error(f"Error fetching topic: {e}")
            return None
        finally:
            db.close()

    @staticmethod
    def delete_topic(topic_id: int, user_id: int) -> Tuple[bool, Optional[str]]:
        """
        Delete a topic.
        
        Args:
            topic_id: Topic ID
            user_id: Telegram user ID (for authorization)
            
        Returns:
            Tuple of (success, error_message)
        """
        db: Session = SessionLocal()
        try:
            topic = db.query(Topic).filter(
                Topic.id == topic_id,
                Topic.user_id == user_id
            ).first()
            
            if not topic:
                return False, "Topic not found or unauthorized"
            
            topic_name = topic.name
            db.delete(topic)
            db.commit()
            
            logger.info(f"Deleted topic '{topic_name}' (ID: {topic_id}) for user {user_id}")
            return True, None
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting topic: {e}")
            return False, f"Error deleting topic: {str(e)}"
        finally:
            db.close()

    @staticmethod
    def delete_all_topics(user_id: int) -> Tuple[bool, int, Optional[str]]:
        """
        Delete all topics for a user.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Tuple of (success, deleted_count, error_message)
        """
        db: Session = SessionLocal()
        try:
            deleted_count = db.query(Topic).filter(
                Topic.user_id == user_id
            ).delete()
            
            db.commit()
            
            logger.info(f"Deleted {deleted_count} topics for user {user_id}")
            return True, deleted_count, None
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting all topics: {e}")
            return False, 0, f"Error deleting topics: {str(e)}"
        finally:
            db.close()

    @staticmethod
    def get_topic_count(user_id: int) -> int:
        """
        Get the count of topics for a user.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Number of topics
        """
        db: Session = SessionLocal()
        try:
            count = db.query(func.count(Topic.id)).filter(
                Topic.user_id == user_id
            ).scalar()
            
            return count or 0
        except Exception as e:
            logger.error(f"Error counting topics: {e}")
            return 0
        finally:
            db.close()

    @staticmethod
    def has_reached_max_topics(user_id: int) -> bool:
        """
        Check if user has reached maximum topics.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            True if max reached, False otherwise
        """
        return TopicService.get_topic_count(user_id) >= MAX_TOPICS_PER_USER
