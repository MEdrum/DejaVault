"""Tests for memory CRUD operations (issues #4, #5, #6)."""

import pytest

from app.services.memory_service import MemoryService


class TestRecord:
    def test_record_new_file(self, service: MemoryService):
        result = service.record("new.md", "hello world", "init")
        assert result["file_path"] == "new.md"
        assert result["commit_hash"]
        assert (service.repo_path / "new.md").read_text() == "hello world"

    def test_record_existing_file_raises(self, service: MemoryService):
        service.record("new.md", "hello world", "init")
        with pytest.raises(FileExistsError):
            service.record("new.md", "overwritten", "should fail")

    def test_record_existing_file_preserves_content(self, service: MemoryService):
        service.record("new.md", "hello world", "init")
        with pytest.raises(FileExistsError):
            service.record("new.md", "overwritten", "should fail")
        assert (service.repo_path / "new.md").read_text() == "hello world"

    def test_record_nested_path_creates_dirs(self, service: MemoryService):
        service.record("a/b/c.md", "nested", "init")
        assert (service.repo_path / "a/b/c.md").read_text() == "nested"


class TestUpdate:
    def test_update_existing_file(self, service: MemoryService):
        service.record("new.md", "hello", "init")
        service.update("new.md", "updated", "update")
        assert (service.repo_path / "new.md").read_text() == "updated"

    def test_update_missing_file_raises(self, service: MemoryService):
        with pytest.raises(FileNotFoundError):
            service.update("missing.md", "content")


class TestCorrect:
    def test_correct_replaces_unique_occurrence(self, service: MemoryService):
        service.record("test.md", "foo bar baz", "init")
        service.correct("test.md", "foo", "X")
        assert (service.repo_path / "test.md").read_text() == "X bar baz"

    def test_correct_multiple_matches_raises(self, service: MemoryService):
        """Multiple matches must be rejected to avoid replacing the wrong one."""
        service.record("test.md", "foo bar foo baz foo", "init")
        with pytest.raises(ValueError, match="matches 3 times"):
            service.correct("test.md", "foo", "X")
        # File must be unchanged after the refusal
        assert (service.repo_path / "test.md").read_text() == "foo bar foo baz foo"

    def test_correct_empty_old_content_raises(self, service: MemoryService):
        service.record("test.md", "content", "init")
        with pytest.raises(ValueError):
            service.correct("test.md", "", "X")

    def test_correct_missing_old_content_raises(self, service: MemoryService):
        service.record("test.md", "content", "init")
        with pytest.raises(ValueError):
            service.correct("test.md", "nonexistent", "X")

    def test_correct_missing_file_raises(self, service: MemoryService):
        with pytest.raises(FileNotFoundError):
            service.correct("missing.md", "old", "new")


class TestArchive:
    def test_archive_deletes_file(self, service: MemoryService):
        service.record("test.md", "content", "init")
        service.archive("test.md")
        assert not (service.repo_path / "test.md").exists()

    def test_archive_missing_file_raises(self, service: MemoryService):
        with pytest.raises(FileNotFoundError):
            service.archive("missing.md")


class TestGet:
    def test_get_existing_file(self, service: MemoryService):
        service.record("test.md", "content", "init")
        result = service.get("test.md")
        assert result is not None
        assert result["content"] == "content"

    def test_get_missing_file_returns_none(self, service: MemoryService):
        assert service.get("missing.md") is None