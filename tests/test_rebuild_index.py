"""Tests for vector index rebuild and stale entry pruning (issue #7).

ChromaDB is not available in CI, so we use a lightweight fake collection
that mimics the subset of the ChromaDB collection API used by the service.
"""

import pytest

from app.services.memory_service import MemoryService


class FakeCollection:
    """Minimal in-memory stand-in for a ChromaDB collection."""

    def __init__(self):
        self._docs: dict[str, str] = {}

    def upsert(self, documents, metadatas, ids):
        for doc_id, doc in zip(ids, documents):
            self._docs[doc_id] = doc

    def get(self, include=None):
        return {"ids": list(self._docs.keys())}

    def delete(self, ids):
        for doc_id in ids:
            self._docs.pop(doc_id, None)

    def count(self):
        return len(self._docs)


@pytest.fixture
def fake_collection() -> FakeCollection:
    return FakeCollection()


@pytest.fixture
def service_with_collection(memory_repo, fake_collection) -> MemoryService:
    """MemoryService with a fake collection attached (no ChromaDB needed)."""
    svc = MemoryService(str(memory_repo), "/tmp/chroma")
    svc.collection = fake_collection
    return svc


class TestRebuildIndex:
    async def test_indexes_all_md_files(self, service_with_collection, memory_repo):
        (memory_repo / "a.md").write_text("alpha")
        (memory_repo / "b.md").write_text("beta")
        (memory_repo / "sub").mkdir()
        (memory_repo / "sub" / "c.md").write_text("gamma")
        # Non-md files are ignored
        (memory_repo / "notes.txt").write_text("not indexed")

        result = await service_with_collection.rebuild_index()

        assert result["status"] == "success"
        assert result["files_indexed"] == 3
        assert set(service_with_collection.collection._docs.keys()) == {"a.md", "b.md", "sub/c.md"}

    async def test_skips_hidden_and_git_files(self, service_with_collection, memory_repo):
        (memory_repo / ".hidden.md").write_text("hidden")
        (memory_repo / "visible.md").write_text("visible")

        result = await service_with_collection.rebuild_index()

        assert result["files_indexed"] == 1
        assert set(service_with_collection.collection._docs.keys()) == {"visible.md"}

    async def test_prunes_stale_entries(self, service_with_collection, memory_repo):
        # Pre-populate the collection with an entry that no longer exists on disk
        service_with_collection.collection.upsert(
            documents=["old content"],
            metadatas=[{"file_path": "deleted.md"}],
            ids=["deleted.md"],
        )
        (memory_repo / "current.md").write_text("current")

        result = await service_with_collection.rebuild_index()

        assert result["files_indexed"] == 1
        assert set(service_with_collection.collection._docs.keys()) == {"current.md"}
        assert "deleted.md" not in service_with_collection.collection._docs

    async def test_prunes_multiple_stale_entries(self, service_with_collection, memory_repo):
        for stale in ("gone1.md", "gone2.md", "gone3.md"):
            service_with_collection.collection.upsert(
                documents=["x"], metadatas=[{"file_path": stale}], ids=[stale]
            )
        (memory_repo / "keep.md").write_text("keep")

        await service_with_collection.rebuild_index()

        assert set(service_with_collection.collection._docs.keys()) == {"keep.md"}

    async def test_force_rebuild_recreates_collection(self, service_with_collection, memory_repo):
        """force=True should delete and recreate the collection."""
        service_with_collection.collection.upsert(
            documents=["stale"], metadatas=[{"file_path": "stale.md"}], ids=["stale.md"]
        )
        (memory_repo / "fresh.md").write_text("fresh")

        # Simulate the force path: delete_collection + create_collection
        # are called on the client; our fake just resets the collection.
        # staticmethod avoids the bound-method self-injection problem.
        class FakeClient:
            @staticmethod
            def delete_collection(name):
                service_with_collection.collection._docs.clear()

            @staticmethod
            def create_collection(name, metadata):
                return service_with_collection.collection

        service_with_collection.chroma_client = FakeClient()

        result = await service_with_collection.rebuild_index(force=True)

        assert result["files_indexed"] == 1
        assert set(service_with_collection.collection._docs.keys()) == {"fresh.md"}

    async def test_empty_repo_indexes_zero(self, service_with_collection):
        result = await service_with_collection.rebuild_index()
        assert result["files_indexed"] == 0
        assert service_with_collection.collection._docs == {}