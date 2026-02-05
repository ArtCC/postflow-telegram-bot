"""
Database Management
SQLAlchemy engine and session management.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session as SQLAlchemySession
from contextlib import contextmanager

from bot.config import DATABASE_PATH, logger
from bot.database.models import Base

# Create engine
engine = create_engine(
    f"sqlite:///{DATABASE_PATH}",
    echo=False,  # Set to True for SQL debugging
    connect_args={"check_same_thread": False}  # Needed for SQLite
)

# Create session factory
# expire_on_commit=False allows objects to be used after session closes
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)

# Session type alias
Session = SQLAlchemySession


def init_db():
    """Initialize database - create all tables"""
    try:
        Base.metadata.create_all(bind=engine)
        _ensure_post_media_column()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise


def _ensure_post_media_column() -> None:
    """Add media_path column to posts table if missing (SQLite)."""
    with engine.connect() as connection:
        result = connection.execute(text("PRAGMA table_info(posts)"))
        columns = [row[1] for row in result.fetchall()]
        if "media_path" not in columns:
            connection.execute(text("ALTER TABLE posts ADD COLUMN media_path TEXT"))


@contextmanager
def get_session():
    """
    Get a database session with automatic cleanup.
    
    Usage:
        with get_session() as session:
            posts = session.query(Post).all()
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        session.close()


def get_db():
    """
    Get a database session (for dependency injection).
    
    Usage:
        session = get_db()
        try:
            # Use session
            session.commit()
        finally:
            session.close()
    """
    return SessionLocal()
