"""Tests for keyword search scope and flag injection (issues #8, #9).

Verifies that ripgrep keyword search:
- only searches *.md files (not other file types)
- treats queries starting with '-' as literal patterns, not flags

ripgrep is not installed in the test environment, so subprocess.run is
mocked to simulate rg's --json output.
"""

import json
from unittest import mock

import pytest

from app.services.memory_service import MemoryService


def _rg_json_line(path: str, text: str) -> str:
    """Build a single rg --json 'match' line."""
    return json.dumps(
        {
            "type": "match",
            "data": {
                "path": {"text": path},
                "lines": {"text": text},
            },
        }
    )


def _make_rg_result(*lines: str):
    """Create a CompletedProcess-like object with the given JSON lines."""
    return mock.Mock(
        stdout="\n".join(lines) + "\n" if lines else "",
        returncode=0,
    )


class TestKeywordSearchScope:
    def test_searches_md_files_only(self, service: MemoryService, memory_repo):
        """rg must be invoked with -g '*.md' to restrict scope to markdown."""
        rg_output = _make_rg_result(
            _rg_json_line(str(memory_repo / "note.md"), "alpha beta"),
        )
        with mock.patch("subprocess.run", return_value=rg_output) as mock_run:
            results = service.search("alpha", search_type="keyword")

        paths = {r.file_path for r in results}
        assert "note.md" in paths

        # Verify rg was invoked with -g '*.md' to restrict scope
        cmd = mock_run.call_args.args[0]
        assert "-g" in cmd
        assert "*.md" in cmd

    def test_searches_nested_md_files(self, service: MemoryService, memory_repo):
        rg_output = _make_rg_result(
            _rg_json_line(str(memory_repo / "sub" / "nested.md"), "nested content"),
        )
        with mock.patch("subprocess.run", return_value=rg_output):
            results = service.search("nested", search_type="keyword")

        paths = {r.file_path for r in results}
        assert "sub/nested.md" in paths

    def test_no_match_returns_empty(self, service: MemoryService):
        with mock.patch("subprocess.run", return_value=_make_rg_result()):
            results = service.search("nonexistent-term", search_type="keyword")
        assert results == []


class TestKeywordFlagInjection:
    def test_query_passed_as_pattern_argument(self, service: MemoryService):
        """The query must be passed with -e so leading '-' is not a flag."""
        with mock.patch("subprocess.run", return_value=_make_rg_result()) as mock_run:
            service.search("-i", search_type="keyword")

        cmd = mock_run.call_args.args[0]
        # -e must appear before the query
        assert "-e" in cmd
        assert cmd[cmd.index("-e") + 1] == "-i"

    @pytest.mark.parametrize(
        "query",
        ["-i", "--json", "-e", "--hidden", "-n"],
    )
    def test_dash_prefixed_query_does_not_raise(self, service: MemoryService, query):
        with mock.patch("subprocess.run", return_value=_make_rg_result()):
            results = service.search(query, search_type="keyword")
        assert results == []

    def test_dash_prefixed_query_matches_literal_content(self, service: MemoryService, memory_repo):
        rg_output = _make_rg_result(
            _rg_json_line(str(memory_repo / "dash.md"), "contains -i literally"),
        )
        with mock.patch("subprocess.run", return_value=rg_output):
            results = service.search("-i", search_type="keyword")

        paths = {r.file_path for r in results}
        assert "dash.md" in paths