# Contributing to Agent Memory Service

Thanks for your interest in contributing! Here's how to get started.

## Development Setup

```bash
# Clone the repo
git clone <your-fork-url>
cd agent-memory

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy the example env file
cp .env.example .env
```

## Running Locally

The service needs a running ChromaDB instance. The easiest way is Docker Compose:

```bash
cp docker-compose.example.yml docker-compose.yml
# Edit docker-compose.yml to point at your local storage paths
docker compose up -d --build
```

## Code Style

- Follow [PEP 8](https://peps.python.org/pep-0008/) conventions.
- Keep functions small and focused.
- Add type hints to all public functions.
- Use descriptive names — the codebase favors clarity over brevity.

## Testing

There is currently no automated test suite (see [TODO.md](./TODO.md)). If you add tests, place them in a `tests/` directory and use `pytest`.

## Submitting Changes

1. Fork the repository and create a feature branch.
2. Make your changes with clear, focused commits.
3. Update the README if your change affects usage.
4. Open a pull request using the [pull request template](./.github/pull_request_template.md).

## Reporting Issues

- Use the GitHub issue tracker.
- Include the version, environment (Docker/host), and steps to reproduce.
- For security issues, see [SECURITY.md](./SECURITY.md) — do **not** open a public issue.
