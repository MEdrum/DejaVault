"""Tests for mutable default args in schemas (issue #16).

Pydantic models must not use mutable defaults like ``metadata: dict = {}``
because the default is shared across instances. Each instance should get
its own fresh dict via ``Field(default_factory=dict)``.
"""

from app.models.schemas import MemoryGetResponse, MemorySearchResult


class TestMemorySearchResult:
    def test_default_metadata_is_empty_dict(self):
        result = MemorySearchResult(file_path="a.md", content="x", score=0.5)
        assert result.metadata == {}

    def test_instances_do_not_share_metadata(self):
        r1 = MemorySearchResult(file_path="a.md", content="x", score=0.5)
        r2 = MemorySearchResult(file_path="b.md", content="y", score=0.5)

        r1.metadata["tag"] = "important"

        assert r1.metadata == {"tag": "important"}
        assert r2.metadata == {}, "metadata dict is shared between instances!"

    def test_explicit_metadata_is_preserved(self):
        result = MemorySearchResult(file_path="a.md", content="x", score=0.5, metadata={"k": "v"})
        assert result.metadata == {"k": "v"}


class TestMemoryGetResponse:
    def test_default_metadata_is_empty_dict(self):
        resp = MemoryGetResponse(file_path="a.md", content="x")
        assert resp.metadata == {}

    def test_instances_do_not_share_metadata(self):
        r1 = MemoryGetResponse(file_path="a.md", content="x")
        r2 = MemoryGetResponse(file_path="b.md", content="y")

        r1.metadata["source"] = "test"

        assert r1.metadata == {"source": "test"}
        assert r2.metadata == {}, "metadata dict is shared between instances!"

    def test_explicit_metadata_is_preserved(self):
        resp = MemoryGetResponse(file_path="a.md", content="x", metadata={"k": "v"})
        assert resp.metadata == {"k": "v"}