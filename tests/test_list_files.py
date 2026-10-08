"""Tests for listing the memory repository structure (files/folders/tree).

Covers the MemoryService.list_files method, the REST /api/v1/list
endpoint, and the MCP list_files tool.
"""

import asyncio

import pytest

from app.mcp_server import create_mcp_server
from app.services.memory_service import MemoryService


@pytest.fixture
def repo_with_structure(memory_repo):
    """Create a repo with a nested folder/file structure."""
    (memory_repo / "root.md").write_text("# Root")
    (memory_repo / "notes").mkdir()
    (memory_repo / "notes" / "ideas.md").write_text("# Ideas")
    (memory_repo / "notes" / "project_x").mkdir()
    (memory_repo / "notes" / "project_x" / "solution.md").write_text("# Solution")
    (memory_repo / "notes" / "project_x" / "notes.txt").write_text("not markdown")
    (memory_repo / "archive").mkdir()
    (memory_repo / "archive" / "old.md").write_text("# Old")
    return memory_repo


class TestListFilesService:
    def test_lists_all_md_files(self, service: MemoryService, repo_with_structure):
        result = service.list_files()
        assert "root.md" in result["files"]
        assert "notes/ideas.md" in result["files"]
        assert "notes/project_x/solution.md" in result["files"]
        assert "archive/old.md" in result["files"]

    def test_excludes_non_md_files(self, service: MemoryService, repo_with_structure):
        result = service.list_files()
        assert "notes/project_x/notes.txt" not in result["files"]

    def test_lists_folders(self, service: MemoryService, repo_with_structure):
        result = service.list_files()
        assert "notes" in result["folders"]
        assert "notes/project_x" in result["folders"]
        assert "archive" in result["folders"]

    def test_tree_structure(self, service: MemoryService, repo_with_structure):
        result = service.list_files()
        tree = result["tree"]
        assert "root.md" in tree
        assert "notes" in tree
        assert "ideas.md" in tree["notes"]
        assert "project_x" in tree["notes"]
        assert "solution.md" in tree["notes"]["project_x"]

    def test_prefix_scopes_listing(self, service: MemoryService, repo_with_structure):
        result = service.list_files("notes")
        assert "notes/ideas.md" in result["files"]
        assert "notes/project_x/solution.md" in result["files"]
        assert "root.md" not in result["files"]

    def test_prefix_missing_dir_raises(self, service: MemoryService, repo_with_structure):
        with pytest.raises(FileNotFoundError):
            service.list_files("nonexistent")

    def test_prefix_traversal_blocked(self, service: MemoryService, repo_with_structure):
        from app.services.memory_service import InvalidPathError

        with pytest.raises(InvalidPathError):
            service.list_files("../outside")


class TestListFilesREST:
    def _client(self, service: MemoryService):
        """Create a TestClient with lifespan side effects mocked.

        The lifespan creates its own MemoryService bound to
        settings.MEMORY_REPO_PATH (/data) and starts an MCP uvicorn task.
        We mock initialize() and the uvicorn server so nothing real runs,
        then replace app.state.memory_service with the fixture service
        AFTER __enter__() has run the lifespan.
        """
        from unittest import mock

        from app.main import app

        class _DummyServer:
            """Stand-in for uvicorn.Server that never binds a port."""

            def __init__(self, config):
                self.config = config

            async def serve(self):
                return None

        init_patcher = mock.patch(
            "app.main.MemoryService.initialize",
            new_callable=lambda: (lambda self: asyncio.sleep(0)),
        )
        mcp_patcher = mock.patch("app.main.create_mcp_server")
        uvicorn_patcher = mock.patch("app.main.uvicorn.Server", _DummyServer)
        init_patcher.start()
        mcp_patcher.start()
        uvicorn_patcher.start()

        from fastapi.testclient import TestClient

        client = TestClient(app)
        client.__enter__()
        # Replace the lifespan's /data-bound service with the fixture one.
        app.state.memory_service = service
        client._dejavault_patchers = (init_patcher, mcp_patcher, uvicorn_patcher)
        return client

    def _close(self, client):
        client.__exit__(None, None, None)
        for patcher in client._dejavault_patchers:
            patcher.stop()

    def test_list_endpoint(self, service: MemoryService, repo_with_structure):
        client = self._client(service)
        try:
            r = client.post("/api/v1/list", json={"prefix": ""})
            assert r.status_code == 200
            data = r.json()
            assert "root.md" in data["files"]
            assert "notes" in data["folders"]
            assert "tree" in data
        finally:
            self._close(client)

    def test_list_endpoint_with_prefix(self, service: MemoryService, repo_with_structure):
        client = self._client(service)
        try:
            r = client.post("/api/v1/list", json={"prefix": "notes"})
            assert r.status_code == 200
            data = r.json()
            assert "notes/ideas.md" in data["files"]
            assert "root.md" not in data["files"]
        finally:
            self._close(client)

    def test_list_endpoint_missing_dir_404(self, service: MemoryService, repo_with_structure):
        client = self._client(service)
        try:
            r = client.post("/api/v1/list", json={"prefix": "nonexistent"})
            assert r.status_code == 404
        finally:
            self._close(client)


class TestListFilesMCP:
    @pytest.fixture
    def mcp_server(self, service: MemoryService):
        return create_mcp_server(service)

    def call_tool(self, server, name: str, **kwargs) -> str:
        result = asyncio.run(server.call_tool(name, kwargs))
        return "".join(getattr(block, "text", str(block)) for block in result.content)

    def test_list_files_tool_registered(self, mcp_server):
        tool_names = {t.name for t in asyncio.run(mcp_server.list_tools())}
        assert "list_files" in tool_names

    def test_list_files_tool_output(self, mcp_server, repo_with_structure):
        result = self.call_tool(mcp_server, "list_files")
        assert "FILES:" in result
        assert "- root.md" in result
        assert "- notes/ideas.md" in result
        assert "FOLDERS:" in result
        assert "- notes" in result
        assert "TREE:" in result
        assert "notes/" in result
        assert "ideas.md" in result
        # The "(none)" placeholder must only appear when a section is empty.
        assert "(none)" not in result

    def test_list_files_tool_empty_repo(self, mcp_server, service: MemoryService):
        result = self.call_tool(mcp_server, "list_files")
        assert "FILES:" in result
        assert "(none)" in result

    def test_list_files_tool_with_prefix(self, mcp_server, repo_with_structure):
        result = self.call_tool(mcp_server, "list_files", prefix="notes")
        assert "- notes/ideas.md" in result
        assert "root.md" not in result

    def test_list_files_tool_missing_dir_error(self, mcp_server, repo_with_structure):
        result = self.call_tool(mcp_server, "list_files", prefix="nonexistent")
        assert "Error" in result
        assert "Not a directory" in result