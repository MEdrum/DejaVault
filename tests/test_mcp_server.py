"""Tests for the MCP server tools (issue: MCP integration).

The MCP layer is a thin adapter over MemoryService. We test the tool
functions by invoking them through the MCPServer's public API.
"""

import asyncio

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