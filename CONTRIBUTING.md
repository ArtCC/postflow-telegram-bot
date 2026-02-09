# Contributing

Thanks for taking the time to contribute.

## Quick Start

1. Fork the repo and create a feature branch.
2. Create a local virtual environment.
3. Install dependencies.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

4. Copy the environment file and configure it.

```bash
cp .env.example .env
```

5. Run the bot locally.

```bash
python -m bot.main
```

## Development Notes

- Keep changes focused and small.
- Follow the existing code style and patterns.
- Do not add new dependencies unless needed.

### i18n Guidelines

- All user-facing strings should go through `t()`.
- Add new keys to `bot/locales/en.json`.
- Keep MarkdownV2 escaping consistent in localized strings.
- Prefer short, clear copy and reuse keys when possible.

## Documentation

- Update the README when you add or change user-facing behavior.
- Update the CHANGELOG for notable changes.

## Submitting a PR

- Ensure your changes run locally.
- Describe how you tested your changes.
- Add screenshots or logs when UI behavior changes.
- Keep commit messages clear and scoped.

## Reporting Issues

When opening an issue, include:

- A clear description of the problem.
- Steps to reproduce.
- Logs or error messages.
- Your environment details (OS, Python version, Docker version).