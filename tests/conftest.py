"""Shared pytest fixtures for the DejaVault test suite."""

import subprocess
from pathlib import Path

import pytest

from app.services.memory_service import MemoryService


@pytest.fixture
def memory_repo(tmp_path: Path) -> Path:
    """Create a temporary git-initialized memory repository."""
    repo = tmp_path / "memory"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@local"], cwd=repo, check=True)
    return repo


@pytest.fixture
def service(memory_repo: Path) -> MemoryService:
    """Create a MemoryService bound to the temp repo (no ChromaDB)."""
    svc = MemoryService(str(memory_repo), "/tmp/chroma")
    # ChromaDB is not available in tests; leave client/collection as None.
    return svc