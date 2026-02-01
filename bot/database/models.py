"""
Database Models
SQLAlchemy ORM models for posts, threads, and scheduled posts.
"""

from datetime import datetime
from enum import Enum
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class PostStatus(str, Enum):
    """Post status enumeration"""
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Post(Base):
    """Post model - represents a social media post"""
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content = Column(Text, nullable=False)
    created_by_ai = Column(Boolean, default=False)
    ai_prompt = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    published_at = Column(DateTime, nullable=True)
    status = Column(SQLEnum(PostStatus), default=PostStatus.DRAFT)
    twitter_id = Column(String(50), nullable=True)  # Tweet ID after publishing
    error_message = Column(Text, nullable=True)  # Store error details if failed

    # Relationships
    threads = relationship("Thread", back_populates="post", cascade="all, delete-orphan")
    scheduled_post = relationship("ScheduledPost", back_populates="post", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Post(id={self.id}, status={self.status}, content='{self.content[:50]}...')>"

    def is_thread(self):
        """Check if this post is a thread (has multiple tweets)"""
        return len(self.threads) > 1

    def get_preview(self, max_length=100):
        """Get a preview of the post content"""
        if len(self.content) > max_length:
            return self.content[:max_length] + "..."
        return self.content


class Thread(Base):
    """Thread model - represents individual tweets in a thread"""
    __tablename__ = "threads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    tweet_index = Column(Integer, nullable=False)  # 1, 2, 3, etc.
    content = Column(String(280), nullable=False)  # Twitter's character limit
    twitter_id = Column(String(50), nullable=True)  # Tweet ID after publishing
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    post = relationship("Post", back_populates="threads")

    def __repr__(self):
        return f"<Thread(id={self.id}, post_id={self.post_id}, index={self.tweet_index})>"


class ScheduledPost(Base):
    """Scheduled post model - represents posts scheduled for future publishing"""
    __tablename__ = "scheduled_posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, unique=True)
    scheduled_for = Column(DateTime, nullable=False)
    job_id = Column(String(100), nullable=True)  # APScheduler job ID
    status = Column(String(20), default="pending")  # pending, completed, cancelled, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    executed_at = Column(DateTime, nullable=True)

    # Relationships
    post = relationship("Post", back_populates="scheduled_post")

    def __repr__(self):
        return f"<ScheduledPost(id={self.id}, post_id={self.post_id}, scheduled_for={self.scheduled_for})>"

    def is_pending(self):
        """Check if the scheduled post is still pending"""
        return self.status == "pending" and self.scheduled_for > datetime.utcnow()
