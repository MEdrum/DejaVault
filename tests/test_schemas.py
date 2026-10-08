"""Tests for Pydantic request schema validation."""

import pytest
from pydantic import ValidationError

from app.models.schemas import MemoryCorrectRequest, MemorySearchRequest


class TestMemoryCorrectRequest:
    def test_valid_request(self):
        req = MemoryCorrectRequest(file_path="a.md", old_content="old", new_content="new")
        assert req.old_content == "old"

    def test_empty_old_content_rejected(self):
        with pytest.raises(ValidationError):
            MemoryCorrectRequest(file_path="a.md", old_content="", new_content="new")

    def test_short_old_content_rejected(self):
        with pytest.raises(ValidationError):
            MemoryCorrectRequest(file_path="a.md", old_content="ab", new_content="new")


class TestMemorySearchRequest:
    def test_defaults(self):
        req = MemorySearchRequest(query="hello")
        assert req.limit == 10
        assert req.search_type == "hybrid"

    def test_limit_bounds(self):
        with pytest.raises(ValidationError):
            MemorySearchRequest(query="hello", limit=0)
        with pytest.raises(ValidationError):
            MemorySearchRequest(query="hello", limit=101)