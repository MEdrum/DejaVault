import logging
import os
import subprocess
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import settings
from app.models.schemas import MemorySearchResult

logger = logging.getLogger(__name__)

# Timeout (seconds) for git subprocess calls. Prevents hangs when git
# waits on locks, credential prompts, or slow filesystems.
GIT_TIMEOUT = 30


class GitCommitError(Exception):
    """Raised when a git commit operation fails."""


class InvalidPathError(ValueError):
    """Raised when a file path escapes the memory repository."""


class MemoryService:
    def __init__(self, repo_path: str, chroma_path: str):
        self.repo_path = Path(repo_path)
        self.chroma_path = Path(chroma_path)
        self.chroma_client = None
        self.collection = None
        
    async def initialize(self):
        """Initialize the memory service."""
        # Ensure repo exists
        self.repo_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize git repo if needed
        if not (self.repo_path / ".git").exists():
            self._git_init()
            
        # Initialize ChromaDB
        await self._init_chromadb()
        
        # Build initial index
        await self.rebuild_index()
        
    def _git_init(self):
        """Initialize git repository."""
        subprocess.run(["git", "init"], cwd=self.repo_path, check=True, capture_output=True, timeout=GIT_TIMEOUT)
        subprocess.run(
            ["git", "config", "user.name", settings.GIT_AUTHOR_NAME],
            cwd=self.repo_path, check=True, timeout=GIT_TIMEOUT,
        )
        subprocess.run(
            ["git", "config", "user.email", settings.GIT_AUTHOR_EMAIL],
            cwd=self.repo_path, check=True, timeout=GIT_TIMEOUT,
        )
        
        # Create initial commit if empty
        readme = self.repo_path / "README.md"
        if not readme.exists():
            readme.write_text("# DejaVault Repository\n\nCanonical memory storage.")
            subprocess.run(["git", "add", "."], cwd=self.repo_path, check=True, timeout=GIT_TIMEOUT)
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"],
                cwd=self.repo_path, check=True, timeout=GIT_TIMEOUT,
            )
            
    async def _init_chromadb(self):
        """Initialize ChromaDB HTTP client."""
        self.chroma_client = chromadb.HttpClient(
            host=settings.CHROMA_HOST,
            port=settings.CHROMA_PORT,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        self.collection = self.chroma_client.get_or_create_collection(
            name="memory",
            metadata={"hnsw:space": "cosine"}
        )
        
    async def rebuild_index(self, force: bool = False) -> dict:
        """Rebuild the vector index from markdown files.

        Upserts all current ``*.md`` files and prunes stale entries
        (files that no longer exist in the repository).
        """
        if not self.collection:
            await self._init_chromadb()
            
        if force:
            # Delete and recreate collection
            self.chroma_client.delete_collection(name="memory")
            self.collection = self.chroma_client.create_collection(
                name="memory",
                metadata={"hnsw:space": "cosine"}
            )
            
        files_indexed = 0
        indexed_ids: set[str] = set()
        for md_file in self.repo_path.rglob("*.md"):
            if md_file.name.startswith(".") or ".git" in md_file.parts:
                continue
            try:
                content = md_file.read_text(encoding="utf-8")
                if content.strip():
                    relative_path = md_file.relative_to(self.repo_path)
                    doc_id = str(relative_path)
                    self.collection.upsert(
                        documents=[content],
                        metadatas=[{"file_path": doc_id}],
                        ids=[doc_id]
                    )
                    indexed_ids.add(doc_id)
                    files_indexed += 1
            except Exception as e:  # noqa: BLE001 - log and continue indexing
                logger.warning(f"Failed to index {md_file}: {e}")

        # Prune stale entries (files removed from the repo)
        try:
            existing_ids = self.collection.get(include=[])["ids"]
            stale_ids = [i for i in existing_ids if i not in indexed_ids]
            if stale_ids:
                self.collection.delete(ids=stale_ids)
                logger.info(f"Pruned {len(stale_ids)} stale entries from vector index")
        except Exception as e:  # noqa: BLE001 - pruning is best-effort
            logger.warning(f"Failed to prune stale vector entries: {e}")

        logger.info(f"Indexed {files_indexed} files")
        return {"status": "success", "files_indexed": files_indexed}
        
    def _git_commit(self, message: str, file_path: str) -> str:
        """Commit changes to a single file and return commit hash.

        Only the given file is staged, so unrelated manual changes in
        the repository are not swept into the commit.
        """
        subprocess.run(
            ["git", "add", "--", file_path],
            cwd=self.repo_path, check=True, timeout=GIT_TIMEOUT,
        )
        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=False,
            timeout=GIT_TIMEOUT,
        )
        if result.returncode != 0 and "nothing to commit" not in result.stdout:
            raise GitCommitError(f"Git commit failed: {result.stderr}")
        # Get commit hash
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=True,
            timeout=GIT_TIMEOUT,
        )
        return result.stdout.strip()
        
    def search(self, query: str, limit: int = 10, search_type: str = "hybrid") -> list[MemorySearchResult]:
        """Search memory using keyword, vector, or hybrid search.

        Raises:
            ValueError: if ``search_type`` is not one of
                "keyword", "vector", or "hybrid".
        """
        if search_type not in ("keyword", "vector", "hybrid"):
            raise ValueError(f"Invalid search_type: {search_type!r} (expected keyword, vector, or hybrid)")
        results = []
        
        if search_type in ("vector", "hybrid") and self.collection:
            try:
                chroma_results = self.collection.query(
                    query_texts=[query],
                    n_results=limit
                )
                for i, doc_id in enumerate(chroma_results["ids"][0]):
                    results.append(MemorySearchResult(
                        file_path=chroma_results["metadatas"][0][i]["file_path"],
                        content=chroma_results["documents"][0][i],
                        score=1.0 - chroma_results["distances"][0][i] if chroma_results["distances"] else 1.0,
                        metadata=chroma_results["metadatas"][0][i]
                    ))
            except Exception as e:  # noqa: BLE001 - log and fall back to keyword
                logger.warning(f"Vector search failed: {e}")
                
        if search_type in ("keyword", "hybrid"):
            # Use ripgrep for keyword search.
            # -g '*.md' restricts to markdown files (issue #8).
            # -e treats the query as a pattern, so leading '-' is not
            #   parsed as a flag (issue #9).
            try:
                rg_result = subprocess.run(
                    ["rg", "--json", "-i", "-g", "*.md", "-e", query, str(self.repo_path)],
                    capture_output=True, text=True, timeout=10, check=False
                )
                for line in rg_result.stdout.strip().split("\n"):
                    if line:
                        import json
                        data = json.loads(line)
                        if data["type"] == "match":
                            file_path = data["data"]["path"]["text"]
                            rel_path = os.path.relpath(file_path, self.repo_path)
                            content = data["data"]["lines"]["text"]
                            results.append(MemorySearchResult(
                                file_path=rel_path,
                                content=content,
                                score=0.8,
                                metadata={"file_path": rel_path}
                            ))
            except Exception as e:  # noqa: BLE001 - log and return partial results
                logger.warning(f"Keyword search failed: {e}")
                
        # Deduplicate and sort by score
        seen = set()
        unique_results = []
        for r in results:
            key = (r.file_path, r.content[:100])
            if key not in seen:
                seen.add(key)
                unique_results.append(r)
                
        unique_results.sort(key=lambda x: x.score, reverse=True)
        return unique_results[:limit]
        
    def _resolve_path(self, file_path: str) -> Path:
        """Resolve a file path and ensure it stays inside the repo.

        Raises:
            InvalidPathError: if the path escapes the repository root.
        """
        full_path = (self.repo_path / file_path).resolve()
        repo_root = self.repo_path.resolve()
        if full_path != repo_root and repo_root not in full_path.parents:
            raise InvalidPathError(f"Path escapes the memory repository: {file_path}")
        return full_path

    def get(self, file_path: str) -> dict | None:
        """Get a memory file by path."""
        full_path = self._resolve_path(file_path)
        if not full_path.exists() or not full_path.is_file():
            return None
        content = full_path.read_text(encoding="utf-8")
        return {"file_path": file_path, "content": content, "metadata": {"file_path": file_path}}
        
    def record(self, file_path: str, content: str, commit_message: str | None = None) -> dict:
        """Record new memory.

        Raises:
            FileExistsError: if the file already exists (use ``update`` instead).
        """
        full_path = self._resolve_path(file_path)
        if full_path.exists():
            raise FileExistsError(f"Memory file already exists: {file_path} (use update to modify)")
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        
        msg = commit_message or f"Record memory: {file_path}"
        commit_hash = self._git_commit(msg, file_path)
        
        # Update vector index
        if self.collection:
            self.collection.upsert(
                documents=[content],
                metadatas=[{"file_path": file_path}],
                ids=[file_path]
            )
            
        return {"file_path": file_path, "commit_hash": commit_hash, "message": msg}
        
    def update(self, file_path: str, content: str, commit_message: str | None = None) -> dict:
        """Update existing memory."""
        full_path = self._resolve_path(file_path)
        if not full_path.exists():
            raise FileNotFoundError(f"Memory file not found: {file_path}")
        full_path.write_text(content, encoding="utf-8")
        
        msg = commit_message or f"Update memory: {file_path}"
        commit_hash = self._git_commit(msg, file_path)
        
        # Update vector index
        if self.collection:
            self.collection.upsert(
                documents=[content],
                metadatas=[{"file_path": file_path}],
                ids=[file_path]
            )
            
        return {"file_path": file_path, "commit_hash": commit_hash, "message": msg}
        
    def correct(self, file_path: str, old_content: str, new_content: str, commit_message: str | None = None) -> dict:
        """Correct memory content.

        Raises:
            ValueError: if ``old_content`` is empty, not found, or matches
                more than once (to avoid replacing the wrong occurrence).
        """
        if not old_content:
            raise ValueError("old_content must not be empty")
        full_path = self._resolve_path(file_path)
        if not full_path.exists():
            raise FileNotFoundError(f"Memory file not found: {file_path}")
        current = full_path.read_text(encoding="utf-8")
        occurrences = current.count(old_content)
        if occurrences == 0:
            raise ValueError("Old content not found in file")
        if occurrences > 1:
            raise ValueError(
                f"Old content matches {occurrences} times in file; "
                "refusing to replace to avoid changing the wrong occurrence. "
                "Include more surrounding context in old_content to make it unique."
            )
        new_full = current.replace(old_content, new_content, 1)
        full_path.write_text(new_full, encoding="utf-8")
        
        msg = commit_message or f"Correct memory: {file_path}"
        commit_hash = self._git_commit(msg, file_path)
        
        # Update vector index
        if self.collection:
            self.collection.upsert(
                documents=[new_full],
                metadatas=[{"file_path": file_path}],
                ids=[file_path]
            )
            
        return {"file_path": file_path, "commit_hash": commit_hash, "message": msg}
        
    def archive(self, file_path: str, commit_message: str | None = None) -> dict:
        """Archive (delete) a memory file."""
        full_path = self._resolve_path(file_path)
        if not full_path.exists():
            raise FileNotFoundError(f"Memory file not found: {file_path}")
        full_path.unlink()
        
        msg = commit_message or f"Archive memory: {file_path}"
        commit_hash = self._git_commit(msg, file_path)
        
        # Remove from vector index
        if self.collection:
            try:
                self.collection.delete(ids=[file_path])
            except Exception as e:  # noqa: BLE001 - index cleanup is best-effort
                logger.warning(f"Failed to remove {file_path} from vector index: {e}")
            
        return {"file_path": file_path, "commit_hash": commit_hash, "message": msg}
        
    def list_related(self, file_path: str, limit: int = 5) -> list[MemorySearchResult]:
        """List related memories."""
        content = self.get(file_path)
        if not content:
            return []
        return self.search(content["content"][:500], limit=limit, search_type="vector")
        
    def health_check(self) -> dict:
        """Health check."""
        chroma_connected = False
        if self.chroma_client:
            try:
                self.chroma_client.heartbeat()
                chroma_connected = True
            except Exception as e:  # noqa: BLE001 - report connectivity status
                logger.warning(f"ChromaDB heartbeat failed: {e}")
        return {
            "status": "healthy",
            "service": "dejavault",
            "git_repo": str(self.repo_path),
            "chroma_connected": chroma_connected
        }