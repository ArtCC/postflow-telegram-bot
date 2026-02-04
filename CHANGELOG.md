# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.2] - 2026-02-04

### Added
- **Timezone support**: Configure `TZ` environment variable for local time scheduling
- **Post notifications**: Receive Telegram notifications when scheduled posts are published or fail
- **Reschedule posts**: Edit scheduled time for pending posts
- **Cancel delete confirmation**: Proper handling of delete cancellation

### Fixed
- SQLAlchemy `DetachedInstanceError` with session management
- MarkdownV2 escaping for special characters (`=`, `-`, etc.)
- Status button callback handler
- All missing callback handlers for post management

### Changed
- All scheduling times now display in user's configured timezone
- Improved error messages with proper MarkdownV2 formatting

## [0.0.1] - 2026-02-02

### Added
- Initial release
- Manual post creation
- AI-powered content generation with OpenAI GPT
- Twitter/X publishing
- Auto thread creation for posts over 280 characters
- Post scheduling (quick options: 1h, 3h, tomorrow + custom date)
- Scheduled posts management (view, edit, delete)
- Statistics and monitoring
- Docker deployment with GitHub Container Registry
- SQLite persistent storage
- Interactive Telegram menus with inline buttons
- User authorization (single-user mode)

---

[0.0.2]: https://github.com/artcc/postflow-telegram-bot/compare/v0.0.1...v0.0.2
[0.0.1]: https://github.com/artcc/postflow-telegram-bot/releases/tag/v0.0.1