# TODO

Findings from a code review of DejaVault. Items are grouped into **Issues & Fixes** (bugs, unfinished work, bad practices) and **Future Features** (ideas to make the tool more useful).

## Issues & Fixes

| #   | Area        | Issue                                             | Description                                                                                                                             |
| --- | ----------- | ------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| 2   | Security    | No authentication                                 | Any agent on the network can read/write/delete all memory. Add API keys or token auth.                                                  |
| 3   | Security    | CORS misconfiguration                             | `allow_origins=["*"]` + `allow_credentials=True` is invalid per spec and rejected by browsers. Remove credentials or restrict origins.  |
| 10  | Bug         | Hardcoded keyword score                           | All keyword results get score `0.8`, skewing hybrid ranking. Compute real relevance (match count/position).                             |
| 11  | Bug         | `list_related()` returns the file itself          | Vector search on a file's own content returns it as top result. Exclude the source file.                                                |
| 12  | Bug         | Duplicate health endpoints                        | `/health` (main.py) returns only `{status, service}` while `/api/v1/health` returns full status — inconsistent and undocumented. Unify. |
| 13  | Bug         | `n_results=limit` may exceed collection size      | ChromaDB errors when requesting more results than exist. Use `min(limit, collection.count())`.                                          |
| 14  | Bug         | `_git_commit` reports stale hash                  | When nothing to commit, `rev-parse HEAD` returns the previous commit hash — misleading response. Detect no-op commits.                  |
| 15  | Bug         | `_git_init` skips initial commit if README exists | Empty repo with existing README never gets an initial commit. Check `git rev-parse --verify HEAD`.                                      |
| 18  | Performance | Blocking calls in async routes                    | `record`, `update`, `search`, etc. are sync and block the event loop. Run in executor or make async.                                    |
| 19  | Performance | Full index rebuild on every startup               | `initialize()` re-embeds all files each boot — slow for large repos. Skip if collection is current.                                     |
| 20  | Reliability | Startup fails if ChromaDB is down                 | `_init_chromadb()` raises and the app won't start. Retry or start degraded.                                                             |
| 24  | Config      | `CHROMA_DB_PATH`/`chroma_path` unused             | ChromaDB is always an HTTP client; the path param and env var are dead config. Remove or implement local mode.                          |
| 26  | Config      | Empty `chroma_data/` dir in repo                  | Unused local folder confuses; ChromaDB runs in its own container. Remove or gitignore.                                                  |
| 29  | Hygiene     | No healthchecks in compose                        | Add `healthcheck:` for both containers so orchestration can detect failures.                                                            |
| 30  | Hygiene     | `read_only: false` rootfs                         | Could be `read_only: true` (only `/data` and tmpfs need writes) — better security.                                                      |
| 31  | Docs        | README health example wrong                       | Shows `git_repo`/`chroma_connected` in `/health` response, but `main.py` returns only `status`/`service`.                               |
| 32  | Docs        | `search_type` not documented as enum              | Document valid values and default in README/OpenAPI.                                                                                    |

## Future Features

| #   | Feature                     | Description                                                                           |
| --- | --------------------------- | ------------------------------------------------------------------------------------- |
| 33  | Authentication              | API keys / token auth so only authorized agents access memory.                        |
| 34  | Namespaces                  | Separate memory spaces per agent (e.g., `opencode/`, `orchestrator/`).                |
| 35  | Memory TTL / expiry         | Auto-archive memories older than a configurable age.                                  |
| 36  | Importance scoring          | Rank memories by importance/recency for better retrieval.                             |
| 37  | BM25 keyword ranking        | Replace hardcoded 0.8 score with proper relevance ranking.                            |
| 38  | Document chunking           | Split long files into overlapping chunks before embedding for better semantic recall. |
| 39  | Frontmatter metadata        | Parse YAML frontmatter (tags, dates, links) and expose as search filters.             |
| 40  | Search filters              | Filter by path, tag, date range, or file type.                                        |
| 41  | Pagination                  | Offset/limit pagination for search results.                                           |
| 42  | RAG endpoint                | Return retrieved context + generated answer for agent Q&A.                            |
| 43  | Batch operations            | Record/update/archive multiple files in one request.                                  |
| 44  | Web UI                      | Simple browser UI to browse, search, and edit memories.                               |
| 45  | Git remote sync             | Push/pull to a remote repo for offsite backup and multi-host sync.                    |
| 46  | Version diff / rollback API | Show diffs between commits and revert to a previous version via API.                  |
| 47  | Webhooks / events           | Notify agents when memory changes (e.g., via webhook or SSE).                         |
| 48  | Metrics                     | Prometheus metrics for usage, latency, index size.                                    |
| 49  | Configurable embeddings     | Allow choosing the embedding model / dimension.                                       |
| 50  | File watching               | Watch the repo and auto-index changes instead of full rebuilds.                       |
| 51  | Semantic dedup              | Detect and merge duplicate memories.                                                  |
| 52  | Memory consolidation        | Periodically merge related memories into summaries.                                   |
| 53  | Export / import             | Backup and restore via API (JSON bundle).                                             |
| 54  | Concurrency safety          | File locks / serialized writes to prevent race conditions.                            |
| 55  | Rate limiting               | Protect the API from abuse by misbehaving agents.                                     |
| 56  | CI/CD                       | GitHub Actions for lint, tests, and image build.                                      |
