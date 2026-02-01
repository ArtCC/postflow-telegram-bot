"""
Bot Configuration
Environment variables and global settings.
"""

import os
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Reduce httpx logging verbosity (suppress polling requests)
logging.getLogger("httpx").setLevel(logging.WARNING)

# Configuration from environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_USER_ID = os.getenv("TELEGRAM_USER_ID")

# Twitter/X API credentials
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

# OpenAI API (optional)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Database
DATABASE_PATH = os.getenv("DATABASE_PATH", "/data/postflow.db")

# Twitter settings
MAX_TWEET_LENGTH = 280
MAX_THREAD_TWEETS = 25  # Twitter's thread limit

# Validate required configuration
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")

if not TELEGRAM_USER_ID:
    raise ValueError("TELEGRAM_USER_ID environment variable is required")

# Convert user ID to integer
try:
    TELEGRAM_USER_ID = int(TELEGRAM_USER_ID)
except ValueError:
    raise ValueError("TELEGRAM_USER_ID must be a valid integer")

# Check Twitter credentials
TWITTER_ENABLED = all([
    TWITTER_API_KEY,
    TWITTER_API_SECRET,
    TWITTER_ACCESS_TOKEN,
    TWITTER_ACCESS_TOKEN_SECRET
])

if not TWITTER_ENABLED:
    logger.warning("Twitter API credentials not configured. Publishing features will be disabled.")

# Check OpenAI
OPENAI_ENABLED = bool(OPENAI_API_KEY)

if not OPENAI_ENABLED:
    logger.info("OpenAI API key not configured. AI features will be disabled.")

# Ensure data directory exists
Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)

logger.info(f"Bot configured for user ID: {TELEGRAM_USER_ID}")
logger.info(f"Twitter API: {'Enabled' if TWITTER_ENABLED else 'Disabled'}")
logger.info(f"OpenAI API: {'Enabled' if OPENAI_ENABLED else 'Disabled'}")
logger.info(f"Database: {DATABASE_PATH}")
