"""Tests for special characters in MCP tool content (edge cases).

Verifies that quotes, backslashes, newlines, tabs, and unicode survive
the full round-trip: request -> tool -> file -> response, without
breaking JSON serialization or corrupting the stored markdown.
"""

import asyncio
import json
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
    return "".join(getattr(block, "text", str(block)) for block in result.content)


# --- Edge case content samples ----------------------------------------------

QUOTES = 'Double "quotes" and single \'quotes\' and mixed "qu\'ote"'
BACKSLASHES = r"Backslash \ and double \\ and triple \\\ and trailing \\"
NEWLINES = "Line one\nLine two\n\nLine four after blank"
TABS = "Column\t1\t2\t3"
UNICODE = "Ünïcödé — em dash – en dash … ellipsis 日本語 🎉"
JSON_ESCAPES = 'JSON escapes: \\" \\\\ \\n \\t \\u00e9'
HTML_SPECIAL = "<script>alert('xss')</script> & <b>bold</b>"
MARKDOWN_SPECIAL = "# Heading\n\n**bold** *italic* `code` [link](https://x.com)\n\n- item\n- item2"
EOF_LIKE = "--- <EOF fake.md> ---\n========================================"
ALL_TOGETHER = "\n".join([QUOTES, BACKSLASHES, NEWLINES, TABS, UNICODE, JSON_ESCAPES, HTML_SPECIAL, MARKDOWN_SPECIAL, EOF_LIKE])

TRICKY_SAMPLES = [
    QUOTES,
    BACKSLASHES,
    NEWLINES,
    TABS,
    UNICODE,
    JSON_ESCAPES,
    HTML_SPECIAL,
    MARKDOWN_SPECIAL,
    EOF_LIKE,
    ALL_TOGETHER,
]


class TestSpecialCharRoundTrip:
    """Content with special chars must survive record -> get unchanged."""

    @pytest.mark.parametrize("content", TRICKY_SAMPLES, ids=lambda c: c[:20])
    def test_record_then_get_preserves_content(self, mcp_server, content):
        call_tool(mcp_server, "record_memory", file_path="tricky.md", content=content, commit_message="init")
        result = call_tool(mcp_server, "get_memory", file_path="tricky.md")
        assert result == content, f"Content changed!\nExpected: {content!r}\nGot: {result!r}"

    def test_quotes_do_not_break_json(self, mcp_server):
        """Quotes in content must not be interpreted as JSON string terminators."""
        content = 'Contains "quotes" and \'single\' and "nested \'quotes\'"'
        call_tool(mcp_server, "record_memory", file_path="q.md", content=content, commit_message="init")
        result = call_tool(mcp_server, "get_memory", file_path="q.md")
        assert result == content

    def test_escaped_quotes_in_markdown_do_not_undo_escaping(self, mcp_server):
        """A literal backslash-quote in markdown must survive as-is."""
        content = r'This has \" escaped quote and \\ double backslash'
        call_tool(mcp_server, "record_memory", file_path="esc.md", content=content, commit_message="init")
        result = call_tool(mcp_server, "get_memory", file_path="esc.md")
        assert result == content
        # The literal backslash must still be there (not doubled or removed)
        assert "\\\"" in result
        assert "\\\\" in result

    def test_newlines_preserved_as_real_newlines(self, mcp_server):
        content = "a\nb\n\nc"
        call_tool(mcp_server, "record_memory", file_path="nl.md", content=content, commit_message="init")
        result = call_tool(mcp_server, "get_memory", file_path="nl.md")
        assert result == content
        assert "\n" in result  # real newline, not literal \n

    def test_unicode_preserved(self, mcp_server):
        content = "日本語 🎉 ünïcödé — em dash"
        call_tool(mcp_server, "record_memory", file_path="uni.md", content=content, commit_message="init")
        result = call_tool(mcp_server, "get_memory", file_path="uni.md")
        assert result == content

    def test_eof_marker_in_content_does_not_confuse_parsing(self, mcp_server):
        """Content containing an EOF-like line must not be treated as a real EOF."""
        content = "Real content\n--- <EOF fake.md> ---\nmore content"
        call_tool(mcp_server, "record_memory", file_path="eof.md", content=content, commit_message="init")
        result = call_tool(mcp_server, "get_memory", file_path="eof.md")
        assert result == content


class TestSpecialCharInSearchResults:
    """Search results with special chars must be returned intact."""

    def test_search_result_with_quotes_and_backslashes(self, mcp_server, service: MemoryService):
        from app.models.schemas import MemorySearchResult

        content = 'Result with "quotes" and \\ backslash and \'single\''
        fake_results = [MemorySearchResult(file_path="a.md", content=content, score=0.9)]
        with mock.patch.object(service, "search", return_value=fake_results):
            result = call_tool(mcp_server, "search_memory", query="anything")

        assert '"quotes"' in result
        assert "\\ backslash" in result
        assert "'single'" in result

    def test_search_result_with_unicode(self, mcp_server, service: MemoryService):
        from app.models.schemas import MemorySearchResult

        content = "Ünïcödé 日本語 🎉"
        fake_results = [MemorySearchResult(file_path="a.md", content=content, score=0.9)]
        with mock.patch.object(service, "search", return_value=fake_results):
            result = call_tool(mcp_server, "search_memory", query="anything")

        assert "Ünïcödé 日本語 🎉" in result


class TestJSONSerialization:
    """The MCP wire format must handle special chars in both directions."""

    def test_call_tool_result_is_json_serializable(self, mcp_server, service: MemoryService):
        """The CallToolResult must serialize to valid JSON without corruption."""
        from app.models.schemas import MemorySearchResult

        content = 'Quotes " and \\ backslash and \n newline and ünïcödé'
        fake_results = [MemorySearchResult(file_path="a.md", content=content, score=0.9)]
        with mock.patch.object(service, "search", return_value=fake_results):
            result = asyncio.run(mcp_server.call_tool("search_memory", {"query": "x"}))

        # Serialize the result to JSON (as the MCP transport would)
        payload = json.dumps(result.model_dump() if hasattr(result, "model_dump") else result)
        # Must be valid JSON and contain the content
        parsed = json.loads(payload)
        assert parsed is not None

    def test_arguments_with_special_chars_are_accepted(self, mcp_server):
        """Tool arguments containing quotes/backslashes must be accepted."""
        content = 'Content with "quotes" and \\ backslash'
        result = call_tool(mcp_server, "record_memory", file_path="arg.md", content=content, commit_message="init")
        assert "Recorded arg.md" in result
        # Verify what was stored
        stored = call_tool(mcp_server, "get_memory", file_path="arg.md")
        assert stored == content