# Agent Memory Service

A self-hosted, Git-backed memory service for AI agents. It gives your agents (OpenCode, orchestrators, etc.) a persistent, versioned, searchable memory store exposed through a simple REST API.

## Table of Contents

- [What is it?](#what-is-it)
- [Features](#features)
- [Quick Start](#quick-start)
- [Usage](#usage)
  - [API Endpoints](#api-endpoints)
  - [Examples](#examples)
- [Architecture](#architecture)
- [Deployment](#deployment)
  - [Docker Compose](#docker-compose)
  - [Storage](#storage)
  - [Security](#security)
- [Configuration](#configuration)
- [Operations](#operations)
  - [Git Operations](#git-operations)
  - [Indexing](#indexing)
  - [Monitoring](#monitoring)
  - [Backup](#backup)
  - [Recovery Procedures](#recovery-procedures)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
  - [Project Structure](#project-structure)
  - [Testing](#testing)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

---

## What is it?

The Agent Memory Service is a small REST API that gives AI agents a **durable, versioned memory**. Instead of letting agents write directly to files (which is hard to audit and easy to corrupt), all memory writes go through this service, which:

1. Stores memory as **Markdown files** in a Git repository (canonical, human-readable, versioned).
2. Keeps a **vector index** (ChromaDB) for semantic search.
3. Provides **keyword search** via ripgrep.
4. Combines both into a **hybrid search**.
5. Exposes everything through a clean **REST API** on port 8000.

It is designed to run as a Docker container on an internal network, isolated from agents so they can only interact with memory through the API.

## Features

- **Canonical storage**: Markdown files in a Git repository
- **Keyword search**: ripgrep-based full-text search
- **Vector search**: ChromaDB with sentence transformers
- **Hybrid search**: Combines both approaches
- **Git history**: Full version control of memory
- **REST API**: Clean interface for all operations
- **Auto-indexing**: Vector index updated on every write

## Quick Start

### Prerequisites

- Docker with Docker Compose
- An external Docker network named `agent-internal` (used to connect agents to this service)

### 1. Create the external network (once)

```bash
docker network create agent-internal
```

### 2. Configure the environment

```bash
cp .env.example .env
cp docker-compose.example.yml docker-compose.yml
```

Then edit `docker-compose.yml` and set the storage volume paths for your host (the example uses placeholder paths).

### 3. Start the service

```bash
docker compose up -d --build
```

This starts two containers:

| Container             | Purpose                     |
| --------------------- | --------------------------- |
| `agent-memory`        | FastAPI service (port 8000) |
| `agent-memory-chroma` | ChromaDB vector database    |

### 4. Verify it's running

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{
  "status": "healthy",
  "service": "agent-memory",
  "git_repo": "/data/memory",
  "chroma_connected": true
}
```

### 5. Record your first memory

```bash
curl -X POST http://localhost:8000/api/v1/record \
  -H "Content-Type: application/json" \
  -d '{"file_path": "projects/example.md", "content": "# Example\n\nThis is my first memory."}'
```

### 6. Search it

```bash
curl -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "first memory", "limit": 5, "search_type": "hybrid"}'
```

That's it — the service is up and usable. See [Usage](#usage) for all endpoints, and [Configuration](#configuration) for tuning.

## Usage

### API Endpoints

| Endpoint                | Method | Description                    |
| ----------------------- | ------ | ------------------------------ |
| `/health`               | GET    | Health check                   |
| `/api/v1/search`        | POST   | Search (keyword/vector/hybrid) |
| `/api/v1/get`           | POST   | Get memory file                |
| `/api/v1/record`        | POST   | Record new memory              |
| `/api/v1/update`        | POST   | Update memory                  |
| `/api/v1/correct`       | POST   | Correct memory content         |
| `/api/v1/archive`       | POST   | Archive (delete) memory        |
| `/api/v1/related`       | POST   | List related memories          |
| `/api/v1/rebuild-index` | POST   | Rebuild vector index           |

### Examples

#### Health Check

```
GET /health
```

Returns service status and connectivity.

#### Search Memory

```
POST /api/v1/search
{
  "query": "search term",
  "limit": 10,
  "search_type": "hybrid"  // "keyword", "vector", or "hybrid"
}
```

#### Get Memory

```
POST /api/v1/get
{
  "file_path": "path/to/file.md"
}
```

#### Record Memory

```
POST /api/v1/record
{
  "file_path": "path/to/file.md",
  "content": "# Title\n\nContent...",
  "commit_message": "Optional commit message"
}
```

#### Update Memory

```
POST /api/v1/update
{
  "file_path": "path/to/file.md",
  "content": "# Title\n\nNew content...",
  "commit_message": "Optional commit message"
}
```

#### Correct Memory

```
POST /api/v1/correct
{
  "file_path": "path/to/file.md",
  "old_content": "text to replace",
  "new_content": "replacement text",
  "commit_message": "Optional commit message"
}
```

#### Archive Memory

```
POST /api/v1/archive
{
  "file_path": "path/to/file.md",
  "commit_message": "Optional commit message"
}
```

#### List Related

```
POST /api/v1/related
{
  "file_path": "path/to/file.md",
  "limit": 5
}
```

#### Rebuild Index

```
POST /api/v1/rebuild-index
{
  "force": false
}
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Agent Memory Service                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ FastAPI     │  │    Git      │  │   ChromaDB          │  │
│  │ (port 8000) │  │   (repo)    │  │   (vector index)    │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
│         │                │                    │             │
│         └────────────────┼────────────────────┘             │
│                          ▼                                  │
│              ┌─────────────────────┐                        │
│              │  /data/memory/      │                        │
│              │  (BTRFS subvolume)  │                        │
│              └─────────────────────┘                        │
└─────────────────────────────────────────────────────────────┘
                              │
                    agent-internal network
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        ┌──────────┐   ┌──────────┐   ┌──────────┐
        │ OpenCode │   │Orchestr. │   │  Other   │
        └──────────┘   └──────────┘   └──────────┘
```

## Deployment

### Docker Compose

A sanitized example is provided in [`docker-compose.example.yml`](./docker-compose.example.yml). Copy it to `docker-compose.yml` and adjust the storage paths for your host:

```bash
cp docker-compose.example.yml docker-compose.yml
```

The real `docker-compose.yml` is gitignored because it contains host-specific paths and may mount secrets (e.g. SSH keys for git remote sync).

```yaml
services:
  agent-memory:
    build: .
    container_name: agent-memory
    ports:
      - "8000:8000"
    volumes:
      - /path/to/your/storage/agent-memory:/data:rw
    networks:
      - agent-internal
    env_file:
      - .env

  chromadb:
    image: chromadb/chroma:1.0.15
    container_name: agent-memory-chroma
    volumes:
      - /path/to/your/storage/agent-memory/chroma:/chroma/chroma
    networks:
      - agent-internal
    environment:
      - CHROMA_SERVER_HOST=0.0.0.0
      - CHROMA_SERVER_HTTP_PORT=8000
      - ANONYMIZED_TELEMETRY=False

networks:
  agent-internal:
    external: true
```

### Storage

- **Memory repository**: `<storage>/memory/` (BTRFS subvolume)
- **Vector index**: `<storage>/chroma/` (BTRFS subvolume)

### Security

- Runs as non-root user (UID 1000)
- No privileged mode
- No host networking
- No Docker socket access
- Capability dropping (only CHOWN, SETGID, SETUID, DAC_OVERRIDE)
- `no-new-privileges:true`
- Resource limits: 1 CPU, 2GB RAM, 50 PIDs

## Configuration

### Environment Variables

All settings are read from environment variables. Copy [`.env.example`](./.env.example) to `.env` and adjust as needed:

```bash
cp .env.example .env
```

| Variable         | Default             | Description                 |
| ---------------- | ------------------- | --------------------------- |
| MEMORY_REPO_PATH | /data/memory        | Path to markdown repository |
| CHROMA_DB_PATH   | /data/chroma        | Path to ChromaDB data       |
| API_HOST         | 0.0.0.0             | API bind address            |
| API_PORT         | 8000                | API port                    |
| CHROMA_HOST      | agent-memory-chroma | ChromaDB hostname           |
| CHROMA_PORT      | 8000                | ChromaDB port               |
| GIT_AUTHOR_NAME  | Agent Memory        | Git commit author name      |
| GIT_AUTHOR_EMAIL | agent-memory@local  | Git commit author email     |
| LOG_LEVEL        | INFO                | Logging level               |

## Operations

### Git Operations

The service manages Git automatically:

- Initializes repo on first run
- Commits on every record/update/correct/archive
- Uses configured author: "Agent Memory" <agent-memory@local>
- Branch: `main`

#### Manual Git Access

```bash
cd /home/fabian/docker/storage/agent-memory/memory
git log --oneline
git show <commit>
git diff <commit1> <commit2>
```

### Indexing

#### Vector Index (ChromaDB)

- Collection: `memory`
- Embedding: all-MiniLM-L6-v2 (downloaded on first run)
- Distance: cosine similarity
- Auto-updated on write operations

#### Keyword Index (ripgrep)

- Real-time search via `rg --json -i`
- No separate index needed
- Searches all `.md` files in repository

#### Rebuild Index

```bash
# Via API
curl -X POST http://localhost:8000/api/v1/rebuild-index \
  -H "Content-Type: application/json" \
  -d '{"force": true}'

# Or manually
docker exec agent-memory python -c "
from app.services.memory_service import MemoryService
import asyncio
svc = MemoryService('/data/memory', '/data/chroma')
asyncio.run(svc.rebuild_index(force=True))
"
```

### Monitoring

```bash
# Check container health
docker ps --filter name=agent-memory

# View logs
docker logs agent-memory -f

# Check resource usage
docker stats agent-memory agent-memory-chroma
```

### Backup

```bash
# Backup memory repository (Git)
cd /home/fabian/docker/storage/agent-memory/memory
git bundle create /backup/memory-$(date +%Y%m%d).bundle --all

# Backup ChromaDB
tar -czf /backup/chroma-$(date +%Y%m%d).tar.gz -C /home/fabian/docker/storage/agent-memory chroma/

# BTRFS snapshot
sudo btrfs subvolume snapshot /home/fabian/docker/storage/agent-memory /home/fabian/docker/storage/agent-memory_snapshot_$(date +%Y%m%d)
```

### Recovery Procedures

#### Container Restart

```bash
docker restart agent-memory
docker restart agent-memory-chroma
```

#### Host Restart

Containers use `restart: unless-stopped` - they start automatically.

#### Index Corruption

```bash
# Force rebuild via API
curl -X POST http://localhost:8000/api/v1/rebuild-index \
  -H "Content-Type: application/json" \
  -d '{"force": true}'

# Or delete chroma data and restart
rm -rf /home/fabian/docker/storage/agent-memory/chroma/*
docker restart agent-memory-chroma
docker restart agent-memory
```

#### Git Repository Recovery

```bash
cd /home/fabian/docker/storage/agent-memory/memory
# Check status
git status
# Reset if needed
git reset --hard HEAD
# Or restore from remote (if configured)
git pull origin main
```

#### Verify Storage After Reboot

```bash
# Check subvolumes mounted
findmnt -t btrfs | grep agent-memory

# Check disk space
df -h /home/fabian/docker/storage/agent-memory/

# Verify git repo
cd /home/fabian/docker/storage/agent-memory/memory && git status
```

## Troubleshooting

### ChromaDB Connection Failed

```bash
# Check chroma container
docker logs agent-memory-chroma

# Verify network
docker exec agent-memory ping agent-memory-chroma

# Check chroma health
curl http://localhost:8000/api/v2/heartbeat
```

### Search Returns No Results

```bash
# Check if files exist
ls -la /home/fabian/docker/storage/agent-memory/memory/

# Rebuild index
curl -X POST http://localhost:8000/api/v1/rebuild-index -H "Content-Type: application/json" -d '{"force": true}'
```

### Git Errors

```bash
cd /home/fabian/docker/storage/agent-memory/memory
git status
git fsck
```

## Development

### Project Structure

```
agent-memory/
├── app/
│   ├── main.py                 # FastAPI app entry point
│   ├── api/
│   │   └── routes.py           # REST API routes
│   ├── core/
│   │   └── config.py           # Settings (env vars)
│   ├── models/
│   │   └── schemas.py          # Pydantic request/response models
│   └── services/
│       └── memory_service.py   # Core logic (git, search, indexing)
├── .github/
│   ├── pull_request_template.md
│   └── workflows/
│       └── ci.yml              # Lint, test, docker build
├── .dockerignore
├── .env.example                # Example environment config
├── .gitignore
├── CHANGELOG.md
├── CONTRIBUTING.md
├── Dockerfile
├── LICENSE
├── README.md
├── SECURITY.md
├── TODO.md
├── docker-compose.example.yml  # Example compose (host paths redacted)
├── requirements.txt
└── chroma_data/                # Local runtime data (gitignored)
```

### Testing

```bash
# Health check
curl http://localhost:8000/health

# Record a memory
curl -X POST http://localhost:8000/api/v1/record \
  -H "Content-Type: application/json" \
  -d '{"file_path": "test.md", "content": "# Test\n\nContent", "commit_message": "Test"}'

# Search
curl -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "limit": 5, "search_type": "hybrid"}'

# Get memory
curl -X POST http://localhost:8000/api/v1/get \
  -H "Content-Type: application/json" \
  -d '{"file_path": "test.md"}'

# List related
curl -X POST http://localhost:8000/api/v1/related \
  -H "Content-Type: application/json" \
  -d '{"file_path": "test.md", "limit": 3}'
```

## Roadmap

See [TODO.md](./TODO.md) for known issues, unfinished work, and planned features.

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](./CONTRIBUTING.md) for development setup and guidelines, and check [TODO.md](./TODO.md) for open issues and planned features.

To report a security vulnerability, see [SECURITY.md](./SECURITY.md) — do **not** open a public issue.

## License

[MIT](./LICENSE)
