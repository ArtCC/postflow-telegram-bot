# PostFlow Telegram Bot ✍️

<p align="left">
  <img src="assets/postflow-telegram-bot.png" alt="PostFlow Logo" width="150">
</p>

A powerful Telegram bot for managing and scheduling social media posts with AI support. Self-hosted, open-source, and easy to deploy with Docker.

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![Telegram](https://img.shields.io/badge/Telegram-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white)](https://telegram.org/)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg?style=for-the-badge)](LICENSE)

## ✨ Features

- ✍️ **Manual Post Creation** - Write your posts directly
- 🤖 **AI-Powered Content** - Generate posts with OpenAI GPT
- 📅 **Smart Scheduling** - Schedule posts for optimal timing
- 🧵 **Auto Thread Creation** - Automatically splits long posts into threads (respects 280 char limit)
- 🐦 **Twitter/X Integration** - Direct publishing to Twitter
- 🔒 **Secure & Private** - Self-hosted, only you have access
- 🐳 **Docker Ready** - Easy deployment with docker-compose
- 📊 **Statistics** - Track your posting performance
- 💾 **Persistent Storage** - SQLite database for reliability
- 🎨 **Beautiful UI** - Interactive menus and inline buttons

## 📋 Prerequisites

- Docker and Docker Compose installed
- A Telegram Bot Token from [@BotFather](https://t.me/botfather)
- Twitter/X Developer Account with API credentials
- (Optional) OpenAI API key for AI features

## 🚀 Quick Start

### 1. Get Your Telegram User ID

1. Start a conversation with [@userinfobot](https://t.me/userinfobot) on Telegram
2. It will reply with your User ID (a number like `123456789`)
3. Save this number for the configuration

### 2. Get Twitter API Credentials

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
# Telegram Bot
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_USER_ID=123456789

# Twitter/X API
TWITTER_API_KEY=your_api_key
TWITTER_API_SECRET=your_api_secret
TWITTER_ACCESS_TOKEN=your_access_token
TWITTER_ACCESS_TOKEN_SECRET=your_access_token_secret

# OpenAI (optional)
OPENAI_API_KEY=sk-your-key-here

# Database
DATABASE_PATH=/data/postflow.db
```

### 5. Deploy with Docker Compose

```bash
docker-compose up -d
```

### 6. Verify the Bot is Running

```bash
docker logs -f postflow-bot
```

You should see: `Bot is running...`

## 💬 Using the Bot

### Basic Usage

1. Open Telegram and find your bot
2. Send `/start` to verify authorization
3. Use `/menu` to access the main menu
4. Click "✍️ New Post" to create your first post

### Creating Posts

#### Manual Post
1. Click "✍️ New Post" → "✏️ Write Manually"
2. Type your content
3. Preview and choose "🚀 Publish Now" or "📅 Schedule"

#### AI-Generated Post
1. Click "✍️ New Post" → "🤖 Generate with AI"
2. Describe what you want: *"Post about Python advantages"*
3. Review generated content
4. Publish or schedule

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

### Managing Scheduled Posts

1. Click "📅 Scheduled" in main menu
2. View all pending posts
3. Click on any post to:
   - 👁️ View details
   - ✏️ Edit schedule time
   - 🗑️ Delete

### Available Commands

- `/start` - Welcome message and authorization check
- `/help` - Show help information
- `/menu` - Open interactive main menu
- `/status` - Check bot and API status
- `/chatid` - Show your Telegram User ID
- `/cancel` - Cancel current operation

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
│ Twitter API  │   │  OpenAI API  │
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
│   ├── services/
│   │   ├── __init__.py
│   │   ├── twitter_service.py # Twitter API integration
│   │   ├── openai_service.py  # OpenAI API integration
│   │   ├── scheduler_service.py # APScheduler management
│   │   └── post_service.py    # Post business logic
│   └── utils/
│       ├── __init__.py
│       ├── auth.py            # Authorization helpers
│       ├── formatting.py      # Text formatting utilities
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

1. Go to your Portainer instance
2. Navigate to **Stacks** → **Add Stack**
3. Name it: `postflow-bot`
4. Paste the contents of `docker-compose.yml`
5. Add your environment variables in the "Environment variables" section
6. Click **Deploy the stack**

## 🔄 Updating

### With Docker Compose

```bash
docker-compose pull
docker-compose up -d
```

### With Portainer

1. Go to your stack
2. Click **Pull and redeploy**

## 🛡️ Security Notes

- **Never commit your `.env` file** - it contains sensitive tokens
- Your bot token gives full control of your bot - keep it secret
- Only the configured `TELEGRAM_USER_ID` can use the bot
- All unauthorized access attempts are logged
- API keys are stored securely in environment variables
- Database is stored in a persistent Docker volume

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

### Twitter API errors

**Error: 401 Unauthorized**
- Check your API credentials in `.env`
- Verify tokens haven't expired
- Regenerate tokens if needed at developer.twitter.com

**Error: 429 Rate Limit**
- Twitter API has rate limits
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

## 📊 Statistics & Monitoring

The bot tracks:
- Total posts created
- Published posts count
- Scheduled posts pending
- Failed posts (with error details)
- Success rate

View with `/status` command.

## 🔮 Roadmap (Future Features)

- [ ] Support for images and videos in posts
- [ ] Multi-platform support (Instagram, LinkedIn, Facebook)
- [ ] Post templates
- [ ] Analytics dashboard
- [ ] Best time to post suggestions
- [ ] Hashtag recommendations
- [ ] Draft system
- [ ] Post editing after creation
- [ ] Recurring posts
- [ ] Web dashboard (optional)

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 Development

### Running Locally (without Docker)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export $(cat .env | xargs)

# Run the bot
python -m bot.main
```

### Code Style

- Follow PEP 8
- Use type hints
- Document functions with docstrings
- Keep functions focused and small

## 🎨 Bot Avatar

You can use the official bot avatar for your own instance:

<p align="left">
  <img src="https://github.com/ArtCC/postflow-telegram-bot/blob/main/assets/postflow-telegram-bot.png" alt="PostFlow Logo" width="200">
</p>

**Download**: [postflow-telegram-bot.png](https://github.com/ArtCC/postflow-telegram-bot/blob/main/assets/postflow-telegram-bot.png)

To set this image as your bot's profile picture:
1. Download the image from the link above
2. Open [@BotFather](https://t.me/botfather) on Telegram
3. Send `/setuserpic`
4. Select your bot
5. Upload the downloaded image

## 🙏 Acknowledgments

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) - Excellent Telegram Bot API wrapper
- [Tweepy](https://github.com/tweepy/tweepy) - Twitter API library
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
  <sub>100% built with GitHub Copilot (Claude Sonnet 4.5)</sub><br>
  <sub>Arturo Carretero Calvo — 2026</sub>
</p>