"""Tests for the MCP server tools (issue: MCP integration).

The MCP layer is a thin adapter over MemoryService. We test the tool
functions by invoking them through the MCPServer's public API.
"""

import asyncio
from unittest import mock

import pytest

from app.mcp_server import create_mcp_server
from app.services.memory_service import MemoryService


@pytest.fixture
def mcp_server(service: MemoryService):
    """Create an MCPServer bound to the test service."""
    return create_mcp_server(service)


def call_tool(server, name: str, **kwargs) -> str:
    """Invoke an MCP tool by name and return its text result."""
    result = asyncio.run(server.call_tool(name, kwargs))
    # CallToolResult.content is a list of content blocks (TextContent).
    return "".join(getattr(block, "text", str(block)) for block in result.content)


class TestMCPToolsRegistered:
    def test_server_created(self, mcp_server):
        assert mcp_server is not None

    def test_tools_are_registered(self, mcp_server):
        """All expected tools should be registered on the server."""
        tool_names = {t.name for t in asyncio.run(mcp_server.list_tools())}
        expected = {
            "search_memory",
            "get_memory",
            "record_memory",
            "update_memory",
            "correct_memory",
            "archive_memory",
            "list_related",
            "rebuild_index",
        }
        assert expected.issubset(tool_names), f"Missing tools: {expected - tool_names}"


class TestMCPToolBehavior:
    def test_record_then_get(self, mcp_server, service: MemoryService):
        """record_memory then get_memory should round-trip."""
        result = call_tool(mcp_server, "record_memory", file_path="test.md", content="# Hello\n\nWorld", commit_message="init")
        assert "Recorded test.md" in result

        content = call_tool(mcp_server, "get_memory", file_path="test.md")
        assert "# Hello" in content

    def test_search_memory_no_results(self, mcp_server):
        result = call_tool(mcp_server, "search_memory", query="nonexistent")
        assert "No results" in result

    def test_get_missing_file(self, mcp_server):
        result = call_tool(mcp_server, "get_memory", file_path="missing.md")
        assert "not found" in result

    def test_record_existing_returns_error(self, mcp_server, service: MemoryService):
        call_tool(mcp_server, "record_memory", file_path="test.md", content="first", commit_message="init")
        result = call_tool(mcp_server, "record_memory", file_path="test.md", content="second", commit_message="init")
        assert "Error" in result

    def test_archive_memory(self, mcp_server, service: MemoryService):
        call_tool(mcp_server, "record_memory", file_path="test.md", content="content", commit_message="init")
        result = call_tool(mcp_server, "archive_memory", file_path="test.md")
        assert "Archived test.md" in result

    def test_correct_memory(self, mcp_server, service: MemoryService):
        call_tool(mcp_server, "record_memory", file_path="test.md", content="foo bar baz", commit_message="init")
        result = call_tool(mcp_server, "correct_memory", file_path="test.md", old_content="foo", new_content="X")
        assert "Corrected test.md" in result
        content = call_tool(mcp_server, "get_memory", file_path="test.md")
        assert content == "X bar baz"

    def test_correct_memory_multiple_matches_returns_error(self, mcp_server, service: MemoryService):
        call_tool(mcp_server, "record_memory", file_path="test.md", content="foo bar foo", commit_message="init")
        result = call_tool(mcp_server, "correct_memory", file_path="test.md", old_content="foo", new_content="X")
        assert "Error" in result
        assert "matches 2 times" in result
        # File must be unchanged
        content = call_tool(mcp_server, "get_memory", file_path="test.md")
        assert content == "foo bar foo"


class TestMCPResponseFormat:
    """Verify multi-result responses use explicit EOF markers.

    Blank lines are ambiguous because markdown content itself contains
    blank lines. Each result block must end with '--- <EOF path> ---'
    followed by a line of 40 '=' characters.
    """

    SEPARATOR = "=" * 40

    def test_search_uses_eof_markers(self, mcp_server, service: MemoryService):
        from app.models.schemas import MemorySearchResult

        fake_results = [
            MemorySearchResult(file_path="a.md", content="# A\n\npara one\n\npara two", score=0.9),
            MemorySearchResult(file_path="b.md", content="# B\n\nother content", score=0.8),
        ]
        with mock.patch.object(service, "search", return_value=fake_results):
            result = call_tool(mcp_server, "search_memory", query="anything")

        # Each block must have an EOF marker and the 40-char separator
        assert "--- <EOF a.md> ---" in result
        assert "--- <EOF b.md> ---" in result
        assert self.SEPARATOR in result

        # Splitting on the separator yields one block per result
        blocks = [b for b in result.split(self.SEPARATOR) if b.strip()]
        assert len(blocks) == 2
        assert blocks[0].strip().startswith("[0.900] a.md")
        assert blocks[0].strip().endswith("--- <EOF a.md> ---")
        assert blocks[1].strip().startswith("[0.800] b.md")
        assert blocks[1].strip().endswith("--- <EOF b.md> ---")

    def test_search_content_with_blank_lines_stays_in_one_block(self, mcp_server, service: MemoryService):
        """Blank lines inside content must NOT split the block."""
        from app.models.schemas import MemorySearchResult

        content = "# A\n\npara one\n\npara two\n\npara three"
        fake_results = [MemorySearchResult(file_path="a.md", content=content, score=0.9)]
        with mock.patch.object(service, "search", return_value=fake_results):
            result = call_tool(mcp_server, "search_memory", query="anything")

        # The whole content must be inside the single block
        assert "para one" in result
        assert "para three" in result
        assert result.count("--- <EOF a.md> ---") == 1

    def test_search_no_results_returns_exact_string(self, mcp_server, service: MemoryService):
        with mock.patch.object(service, "search", return_value=[]):
            result = call_tool(mcp_server, "search_memory", query="nothing")
        assert result == "No results found."

    def test_list_related_uses_eof_markers(self, mcp_server, service: MemoryService):
        from app.models.schemas import MemorySearchResult

        fake_results = [
            MemorySearchResult(file_path="x.md", content="content x", score=0.7),
            MemorySearchResult(file_path="y.md", content="content y", score=0.6),
        ]
        with mock.patch.object(service, "list_related", return_value=fake_results):
            result = call_tool(mcp_server, "list_related", file_path="base.md")

        assert "--- <EOF x.md> ---" in result
        assert "--- <EOF y.md> ---" in result
        blocks = [b for b in result.split(self.SEPARATOR) if b.strip()]
        assert len(blocks) == 2
        assert blocks[0].strip().startswith("[0.700] x.md")
        assert blocks[1].strip().startswith("[0.600] y.md")

    def test_list_related_no_results_returns_exact_string(self, mcp_server, service: MemoryService):
        with mock.patch.object(service, "list_related", return_value=[]):
            result = call_tool(mcp_server, "list_related", file_path="base.md")
        assert result == "No related memories found."