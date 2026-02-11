# PostFlow Telegram Bot ✍️

<p align="left">
  <img src="assets/postflow-telegram-bot.png" alt="PostFlow Logo" width="150">
</p>

A powerful Telegram bot for managing and scheduling social media posts with AI support. Self-hosted, open-source, and easy to deploy with Docker.

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![Telegram](https://img.shields.io/badge/Telegram-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white)](https://telegram.org/)
[![GitHub Container Registry](https://img.shields.io/badge/ghcr.io-package-blue?style=for-the-badge&logo=github)](https://github.com/ArtCC/postflow-telegram-bot/pkgs/container/postflow-telegram-bot)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg?style=for-the-badge)](LICENSE)

## ✨ Features

- ✍️ **Manual Post Creation** - Write your posts directly
- 🤖 **AI-Powered Content** - Generate posts with OpenAI GPT
- 📅 **Smart Scheduling** - Schedule posts for optimal timing
- 🌍 **Timezone Support** - Configure your local timezone for scheduling
- 🔔 **Notifications** - Get notified when scheduled posts are published
- 🧵 **Auto Thread Creation** - Automatically splits long posts into threads (respects 280 char limit)
- 🎯 **Topic Presets** - Save favorite topics for quick AI post generation
- 🧩 **Templates** - Reusable content blocks for quick posts
- 🔒 **Secure & Private** - Self-hosted, only you have access
- 🐳 **Docker Ready** - Easy deployment with docker-compose
- 📊 **Statistics** - Track your posting performance
- 📝 **Drafts** - Save posts and finish later
- 📆 **Weekly Planning** - Plan up to 7 days with multiple slots per day
- 🗓️ **Weekly Calendar View** - Review scheduled posts by week
- 🖼️ **Image Posts** - Publish posts with a single attached image
- 💾 **Persistent Storage** - SQLite database for reliability
- 🎨 **Beautiful UI** - Interactive menus and inline buttons
- 🌐 **Localization Ready** - i18n support with English fallback

## 📋 Prerequisites

- Docker and Docker Compose installed
- A Telegram Bot Token from [@BotFather](https://t.me/botfather)
- X Developer Account with API credentials
- (Optional) OpenAI API key for AI features

## 🚀 Quick Start

### 1. Get Your Telegram User ID

- Open a chat with [@userinfobot](https://t.me/userinfobot)
- It replies with your User ID
- Copy the number into `TELEGRAM_USER_ID`

Example reply:
```
Your user ID: 123456789
```

### 2. Get X API Credentials

1. Go to [developer.twitter.com](https://developer.twitter.com)
2. Create a new app or use existing one
3. Generate API keys and access tokens
4. You'll need:
  - API Key
  - API Secret
  - Access Token
  - Access Token Secret

### 3. Clone the Repository

```bash
git clone https://github.com/artcc/postflow-telegram-bot.git
cd postflow-telegram-bot
```

### 4. Configure Environment Variables

Create a `.env` file from the example:

```bash
cp .env.example .env
```

Edit the `.env` file with your credentials:

```env
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_USER_ID=123456789

# Timezone (required) - Your local timezone for scheduling
# Examples: Europe/Madrid, America/New_York, Asia/Tokyo
TZ=Europe/Madrid

# Twitter/X API Credentials
TWITTER_API_KEY=your_api_key_here
TWITTER_API_SECRET=your_api_secret_here
TWITTER_ACCESS_TOKEN=your_access_token_here
TWITTER_ACCESS_TOKEN_SECRET=your_access_token_secret_here

# OpenAI API (optional - leave empty to disable AI features)
OPENAI_API_KEY=sk-your-openai-api-key-here

# Database Configuration (default: /data/postflow.db)
DATABASE_PATH=/data/postflow.db
```

> **Important:** All variables are **required** except `OPENAI_API_KEY` (optional). The bot won't start without the required credentials.

> **Timezone:** Use standard timezone names from [IANA Time Zone Database](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) (e.g., `Europe/Madrid`, `America/New_York`, `Asia/Tokyo`).

### 5. Deploy with Docker Compose

The `docker-compose.yml` configuration:

```yaml
services:
  postflow-bot:
    image: ghcr.io/artcc/postflow-telegram-bot:latest
    container_name: postflow-bot
    environment:
      # Telegram Bot Configuration
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - TELEGRAM_USER_ID=${TELEGRAM_USER_ID}
      
      # Timezone (required) - e.g., Europe/Madrid, America/New_York
      - TZ=${TZ}
      
      # Twitter/X API Credentials
      - TWITTER_API_KEY=${TWITTER_API_KEY}
      - TWITTER_API_SECRET=${TWITTER_API_SECRET}
      - TWITTER_ACCESS_TOKEN=${TWITTER_ACCESS_TOKEN}
      - TWITTER_ACCESS_TOKEN_SECRET=${TWITTER_ACCESS_TOKEN_SECRET}
      
      # OpenAI API (optional)
      - OPENAI_API_KEY=${OPENAI_API_KEY:-}
      
      # Database Configuration
      - DATABASE_PATH=${DATABASE_PATH:-/data/postflow.db}
    volumes:
      - ./data:/data  # Database persistence
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

Start the bot:

```bash
# Start the bot in detached mode
docker-compose up -d
```

The `docker-compose.yml` automatically:
- Pulls the latest image from GitHub Container Registry
- Loads environment variables from `.env` file
- Creates a persistent volume for the database (`./data`)
- Configures automatic restarts
- Sets up log rotation

> **Note:** The image is pulled from `ghcr.io/artcc/postflow-telegram-bot:latest` - no build required!

### 6. Verify the Bot is Running

```bash
# Check container status
docker ps | grep postflow-bot

# View real-time logs
docker logs -f postflow-bot
```

**Expected output:**
```
2026-02-02 10:30:15 - bot.config - INFO - Bot configured for user ID: 123456789
2026-02-02 10:30:15 - bot.config - INFO - Twitter API: Enabled
2026-02-02 10:30:15 - bot.config - INFO - OpenAI API: Enabled
2026-02-02 10:30:15 - bot.main - INFO - Starting PostFlow Telegram Bot...
2026-02-02 10:30:16 - bot.main - INFO - Bot is running... Press Ctrl+C to stop.
```

**Troubleshooting startup:**
- If you see errors about missing variables, check your `.env` file
- If container exits immediately, check logs: `docker logs postflow-bot`
- Verify all required credentials are set correctly

## 💬 Using the Bot

### Basic Usage

1. Open Telegram and find your bot
2. Send `/start` to verify authorization
3. Use `/menu` to access the main menu
4. Click "✍️ New" to create your first post

### Creating Posts

#### Manual Post
1. Click "✍️ New" → "✏️ Write Manually"
2. Type your content
3. Preview and choose "🚀 Publish Now" or "📅 Schedule"

#### AI-Generated Post
1. Click "✍️ New" → "🤖 AI"
2. If you have topic presets, select one or choose "✏️ Custom Prompt"
3. For custom: Describe what you want: *"Post about Python advantages"*
4. Review generated content
5. Publish or schedule

#### Template Post
1. Click "✍️ New" → "🧩 Templates"
2. Choose a template
3. Review the prefilled content
4. Edit if needed, then publish or schedule

### Managing Topic Presets

Topic presets allow you to quickly generate AI posts on your favorite subjects.

#### Adding Topics
1. Click "🎯 Topics" in main menu or use `/topics`
2. Click "➕ Add Topic"
3. Enter a topic name (3-30 characters)
   - Examples: "Python Programming", "AI & ML", "Tech News"
4. Topic is saved for quick access (max 10 topics)

#### Using Topics
1. Click "✍️ New" → "🤖 AI"
2. Select a topic preset button
3. AI generates a professional post about that topic
4. Review, edit if needed, then publish or schedule

#### Managing Topics
- **List Topics**: View all your saved topics
- **Delete Topic**: Remove individual topics
- **Delete All**: Clear all topics (with confirmation)

> **Note:** Topics require OpenAI to be configured. Each topic generates unique content every time and is limited to a single post (max 280 characters).

### Managing Templates

1. Click "🧩 Templates" in main menu or use `/templates`
2. Add a template (name + content)
3. List templates to view details
4. Edit content or delete when needed
5. Use a template to create a post in one tap

#### Weekly Plan
1. Click "✍️ New" → "📆 Plan Week"
2. Select days (rolling 7-day window)
3. Choose posts per day (max 3)
4. Enter time slots for each day
5. Create each post manually or with AI
6. Review summary and confirm scheduling

#### Image Post
1. Click "✍️ New" → "🖼️ Image"
2. Send an image with an optional caption (max 280 chars)
3. Preview and choose "🚀 Publish Now" or "📅 Schedule"

### Thread Creation

Posts longer than 280 characters are automatically converted to threads:
- Intelligent splitting at sentence boundaries
- Automatic numbering (1/3, 2/3, 3/3)
- Preview before publishing
- All tweets published as connected thread

### Scheduling Posts

1. Create your post (manual or AI)
2. Choose "📅 Schedule"
3. Select quick option or custom date:
   - ⏰ In 1 hour
   - ⏰ In 3 hours
   - 📆 Tomorrow 9am
   - 📆 Custom date (format: `2026-01-25 18:00`)
4. Post will be published automatically at scheduled time
5. You'll receive a notification when the post is published

> **Note:** All times are displayed in your configured timezone (TZ environment variable).

### Post Notifications

When a scheduled post is published (or fails), you'll receive a notification:

**Success notification:**
```
🎉 SCHEDULED POST PUBLISHED
✅ Your scheduled post #123 has been published successfully!
🔗 View on X
```

**Failure notification:**
```
❌ SCHEDULED POST FAILED
⚠️ Your scheduled post #123 could not be published.
📝 Error: [error details]
💡 Check /menu to retry or reschedule.
```

### Managing Scheduled Posts

1. Click "📅 Scheduled" in main menu
2. View all pending posts
3. Click on any post to:
   - 👁️ View details
   - ✏️ Edit schedule time
   - 🗑️ Delete

### Weekly Calendar View

1. Open "📅 Scheduled" in the main menu
2. Tap "🗓️ Calendar" to see the current week
3. Navigate weeks with Previous/Next buttons
4. Review scheduled posts grouped by day and time

### Managing Drafts

1. Click "📝 Drafts" in main menu
2. Select a draft to preview
3. Edit, publish, or schedule from the preview

### Available Commands

- `/start` - Welcome message and authorization check
- `/help` - Show help information
- `/menu` - Open interactive main menu
- `/new` - New post
- `/plan` - Plan week
- `/topics` - Manage topic presets
- `/templates` - Manage templates
- `/drafts` - List drafts
- `/scheduled` - List scheduled posts
- `/stats` - Show statistics
- `/status` - Check bot and API status
- `/settings` - Show settings
- `/chatid` - Show your Telegram User ID
- `/author` - About the author
- `/cancel` - Cancel current operation

### Internationalization

The bot uses your Telegram `language_code` and falls back to English when a locale is not available.

### 📊 Statistics & Monitoring

The bot tracks:
- Total posts created
- Published posts count
- Scheduled posts pending
- Failed posts (with error details)
- Success rate percentage

Access statistics via the "📊 Statistics" button in the main menu or with `/status` command.

## 🔧 Architecture

```
┌─────────────────┐
│  Telegram User  │
└────────┬────────┘
         │
         ▼
┌─────────────────────┐
│  Telegram Bot API   │
└────────┬────────────┘
         │
         ▼
┌─────────────────────────┐
│  PostFlow Bot           │
│  - Handlers             │
│  - Services             │
│  - Database (SQLite)    │
│  - APScheduler          │
└────────┬────────────────┘
         │
         ├──────────────────┐
         │                  │
         ▼                  ▼
┌──────────────┐   ┌──────────────┐
│   X API      │   │  OpenAI API  │
└──────────────┘   └──────────────┘
```

### Project Structure

```
postflow-telegram-bot/
├── bot/
│   ├── __init__.py
│   ├── config.py              # Configuration & environment variables
│   ├── main.py                # Bot entry point
│   ├── database/
│   │   ├── __init__.py
│   │   ├── models.py          # SQLAlchemy models
│   │   └── database.py        # Database management
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── commands.py        # Command handlers
│   │   ├── callbacks.py       # Button callback handlers
│   │   ├── posts.py           # Post management logic
│   │   └── conversations.py   # Multi-step conversations
│   ├── locales/
│   │   ├── en.json            # UI strings
│   │   └── es.json            # UI strings
│   ├── services/
│   │   ├── __init__.py
│   │   ├── twitter_service.py # X API integration
│   │   ├── openai_service.py  # OpenAI API integration
│   │   ├── scheduler_service.py # APScheduler management
│   │   ├── post_service.py    # Post business logic
│   │   ├── topic_service.py   # Topic presets management
│   │   └── template_service.py # Templates management
│   └── utils/
│       ├── __init__.py
│       ├── auth.py            # Authorization helpers
│       ├── formatting.py      # Text formatting utilities
│       ├── i18n.py            # Localization helpers
│       └── keyboards.py       # Telegram keyboard builders
├── data/                      # SQLite database (volume)
├── .env                       # Environment variables (not in git)
├── .env.example               # Example configuration
├── .gitignore
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── LICENSE
└── README.md
```

## 📦 Installing via Portainer

### Method 1: Using Git Repository (Recommended)

1. Go to your Portainer instance
2. Navigate to **Stacks** → **Add Stack**
3. Name it: `postflow-bot`
4. Select **Repository** as build method
5. Enter repository URL: `https://github.com/artcc/postflow-telegram-bot`
6. Compose path: `docker-compose.yml`
7. Add environment variables:
   ```
   TELEGRAM_BOT_TOKEN=your_bot_token
   TELEGRAM_USER_ID=your_user_id
   TZ=Europe/Madrid
   TWITTER_API_KEY=your_api_key
   TWITTER_API_SECRET=your_api_secret
   TWITTER_ACCESS_TOKEN=your_access_token
   TWITTER_ACCESS_TOKEN_SECRET=your_access_token_secret
   OPENAI_API_KEY=your_openai_key
   DATABASE_PATH=/data/postflow.db
   ```
8. Click **Deploy the stack**

### Method 2: Manual Compose File

1. Go to your Portainer instance
2. Navigate to **Stacks** → **Add Stack**
3. Name it: `postflow-bot`
4. Select **Web editor**
5. Paste the `docker-compose.yml` content
6. Add the environment variables as shown above
7. Click **Deploy the stack**

> **Tip:** In Portainer, you can easily edit environment variables after deployment without recreating the stack.

## 🔄 Updating

### With Docker Compose

```bash
# Pull the latest image
docker-compose pull

# Recreate and start the container
docker-compose up -d

# Verify the update
docker logs -f postflow-bot
```

> **Note:** Your data is safe! The `./data` volume persists your database across updates.

### With Portainer

1. Go to **Stacks** → Select `postflow-bot`
2. Click **Pull and redeploy** button
3. Wait for the update to complete
4. Check **Containers** to verify it's running

### Verify Current Version

```bash
# Check image version
docker images | grep postflow-telegram-bot

# Check when the image was pulled
docker inspect ghcr.io/artcc/postflow-telegram-bot:latest | grep Created
```

### Auto-Updates

Every push to the `main` branch automatically:

1. Builds a new Docker image
2. Publishes it to GitHub Container Registry
3. Tags it as `latest`

The bot uses the pre-built image from `ghcr.io/artcc/postflow-telegram-bot:latest`, so you just need to pull the latest version.

> **Note:** The GitHub Container Registry package is public, so anyone can pull the image without authentication.

## 🛡️ Security Notes

- **Never commit your `.env` file** - it contains sensitive tokens
- Your bot token gives full control of your bot - keep it secret
- Only the configured `TELEGRAM_USER_ID` can use the bot
- All unauthorized access attempts are logged
- API keys are stored securely in environment variables
- Database is stored in a persistent Docker volume

## ❓ FAQ

### Can I use this bot for multiple X accounts?

Currently, the bot is designed for single-user, single-account use. Each instance manages one X account. To manage multiple accounts, deploy separate instances with different configurations.

### Does the bot store my API keys securely?

Yes. All API keys are stored in environment variables (`.env` file) which is never committed to git. The keys are only used by your self-hosted instance.

### What happens if the bot crashes while scheduling posts?

Scheduled posts are stored in the SQLite database. When the bot restarts, APScheduler automatically reschedules all pending posts.

### Can I use this bot without OpenAI?

Yes. OpenAI is optional. If you don't configure `OPENAI_API_KEY`, the bot will work perfectly fine for manual post creation and scheduling. You just won't have AI generation features or topic presets.

### How do topic presets work?

Topic presets are saved keywords that trigger AI to generate posts on specific subjects. You can save up to 10 topics (e.g., "Python", "AI News", "Tech Tips"). When creating an AI post, select a topic button and the AI generates unique content about that subject each time. Topics require OpenAI to be configured.

### What X API plan do I need?

You need at least **Basic** access tier from X's Developer Portal to post. The Free tier has very limited posting capabilities.

## 🐛 Troubleshooting

### Bot doesn't respond

- Check if container is running: `docker ps`
- Check logs: `docker logs -f postflow-bot`
- Verify bot token is correct in `.env`
- Ensure bot is not rate-limited by Telegram

### "Unauthorized" message

- Verify your User ID is correct in `.env`
- Use `/chatid` command to see your actual ID
- Restart container after changing `.env`:
  ```bash
  docker-compose restart
  ```

### X API errors

**Error: 401 Unauthorized**
- Check your API credentials in `.env`
- Verify tokens haven't expired
- Regenerate tokens if needed at developer.twitter.com

**Error: 429 Rate Limit**
- X API has rate limits
- Wait for rate limit reset (shown in error message)
- Posts are saved and can be retried

### OpenAI API errors

**Invalid API Key**
- Verify `OPENAI_API_KEY` in `.env`
- Check key hasn't expired
- Ensure you have credits in your OpenAI account

**Rate Limit Exceeded**
- OpenAI has usage limits based on your plan
- Wait a few minutes before retrying
- Upgrade your OpenAI plan if needed

### Database issues

**Database locked**
- Stop the container: `docker-compose down`
- Start again: `docker-compose up -d`

**Lost data after restart**
- Verify volume is mounted correctly in `docker-compose.yml`
- Check that `./data` directory exists

### Permission denied errors

```bash
sudo chown -R 1000:1000 ./data
sudo chmod -R 755 ./data
```

## 🔮 Roadmap

### Phase 1: MVP ✅

- [x] Manual post creation
- [x] AI-powered content generation (OpenAI GPT)
- [x] Twitter/X publishing
- [x] Auto thread creation for long posts
- [x] Post scheduling (quick & custom)
- [x] Scheduled posts management
- [x] Post editing after creation
- [x] Statistics & monitoring
- [x] Docker deployment
- [x] SQLite persistent storage
- [x] Timezone support (TZ configuration)
- [x] Notifications for scheduled posts

### Phase 2: New Features

- [x] Draft system
- [x] Weekly planning wizard (rolling 7-day window)
- [x] Support for images in posts
- [x] Topic presets for AI random post generation
- [x] Additional locales (i18n)
- [x] Publication calendar with weekly view
- [x] Post templates

### Phase 3: Future Features

- [ ] Multi-platform support (Instagram, LinkedIn, Facebook, etc.)

## 🤝 Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) for setup, conventions, and i18n guidelines.

## 🎨 Bot Avatar

You can use the official bot avatar for your own instance:

<p align="left">
  <img src="https://raw.githubusercontent.com/ArtCC/postflow-telegram-bot/main/assets/postflow-telegram-bot.png" alt="PostFlow Bot Avatar" width="200">
</p>

To set this image as your bot's profile picture:
1. Right-click the image above and save it
2. Open [@BotFather](https://t.me/botfather) on Telegram
3. Send `/setuserpic`
4. Select your bot
5. Upload the downloaded image

## 🙏 Acknowledgments

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) - Excellent Telegram Bot API wrapper
- [Tweepy](https://github.com/tweepy/tweepy) - X API library
- [OpenAI](https://openai.com) - AI content generation
- [APScheduler](https://github.com/agronholm/apscheduler) - Advanced Python Scheduler

## 📧 Support

If you encounter any issues or have questions:

1. Check the [Troubleshooting](#-troubleshooting) section
2. Search existing [GitHub Issues](https://github.com/artcc/postflow-telegram-bot/issues)
3. Open a new issue with detailed information

## 📄 License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

---

<p align="left">
  <sub>100% built with GitHub Copilot (GPT-5.2-Codex)</sub><br>
  <sub>Arturo Carretero Calvo — 2026</sub>
</p>