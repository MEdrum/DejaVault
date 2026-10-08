"""Tests for path validation in MemoryService (issue #1)."""

import pytest

from app.services.memory_service import InvalidPathError, MemoryService


class TestPathValidation:
    def test_valid_relative_path(self, service: MemoryService):
        assert service._resolve_path("test.md") == (service.repo_path / "test.md").resolve()

    def test_valid_nested_path(self, service: MemoryService):
        assert service._resolve_path("sub/dir/file.md") == (service.repo_path / "sub/dir/file.md").resolve()

    def test_valid_absolute_path_inside_repo(self, service: MemoryService):
        inside = service.repo_path / "notes.md"
        inside.write_text("hello")
        assert service._resolve_path(str(inside)) == inside.resolve()

    @pytest.mark.parametrize(
        "bad_path",
        [
            "../evil.md",
            "../../etc/passwd",
            "sub/../../evil.md",
            "/etc/passwd",
            "..",
            "a/../../../etc/passwd",
        ],
    )
    def test_path_traversal_blocked(self, service: MemoryService, bad_path: str):
        with pytest.raises(InvalidPathError):
            service._resolve_path(bad_path)

    def test_get_rejects_traversal(self, service: MemoryService):
        with pytest.raises(InvalidPathError):
            service.get("../evil.md")

    def test_record_rejects_traversal(self, service: MemoryService):
        with pytest.raises(InvalidPathError):
            service.record("../../evil.md", "content")

    def test_update_rejects_traversal(self, service: MemoryService):
        with pytest.raises(InvalidPathError):
            service.update("../../evil.md", "content")

    def test_correct_rejects_traversal(self, service: MemoryService):
        with pytest.raises(InvalidPathError):
            service.correct("../../evil.md", "old", "new")

    def test_archive_rejects_traversal(self, service: MemoryService):
        with pytest.raises(InvalidPathError):
            service.archive("../../evil.md")