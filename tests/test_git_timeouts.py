"""Tests for git subprocess timeouts (issue #21).

All git subprocess calls must include a timeout so they can't hang
indefinitely on locks, credential prompts, or slow filesystems.
"""

from unittest import mock

import pytest

from app.services.memory_service import GIT_TIMEOUT, MemoryService


class TestGitInitTimeouts:
    def test_all_git_init_calls_have_timeout(self, service: MemoryService):
        """Every subprocess.run in _git_init must pass timeout=GIT_TIMEOUT."""
        with mock.patch("subprocess.run") as mock_run:
            service._git_init()

        assert mock_run.call_count >= 3, "expected git init/config calls"
        for call in mock_run.call_args_list:
            kwargs = call.kwargs
            assert "timeout" in kwargs, f"missing timeout in call: {call}"
            assert kwargs["timeout"] == GIT_TIMEOUT

    def test_git_init_commit_calls_have_timeout(self, service: MemoryService):
        """When README is created, git add/commit must also have timeouts."""
        with mock.patch("subprocess.run") as mock_run:
            service._git_init()

        # The last two calls should be git add and git commit
        commands = [call.args[0] for call in mock_run.call_args_list]
        assert any(cmd[0] == "git" and cmd[1] == "add" for cmd in commands)
        assert any(cmd[0] == "git" and cmd[1] == "commit" for cmd in commands)
        for call in mock_run.call_args_list:
            assert "timeout" in call.kwargs


class TestGitCommitTimeouts:
    def test_git_commit_calls_have_timeout(self, service: MemoryService):
        """git add, git commit, and git rev-parse must all have timeouts."""
        # Mock rev-parse to return a hash
        rev_parse = mock.Mock(stdout="abc123\n", returncode=0)
        commit = mock.Mock(stdout="[main abc123] msg\n", stderr="", returncode=0)

        def fake_run(cmd, **kwargs):
            if cmd[1] == "commit":
                return commit
            if cmd[1] == "rev-parse":
                return rev_parse
            return mock.Mock(returncode=0)

        with mock.patch("subprocess.run", side_effect=fake_run) as mock_run:
            result = service._git_commit("test message")

        assert result == "abc123"
        assert mock_run.call_count == 3
        for call in mock_run.call_args_list:
            assert "timeout" in call.kwargs, f"missing timeout in call: {call}"
            assert call.kwargs["timeout"] == GIT_TIMEOUT

    def test_git_commit_timeout_propagates(self, service: MemoryService):
        """A TimeoutExpired from git should propagate to the caller."""
        with mock.patch(
            "subprocess.run",
            side_effect=TimeoutExpired("git", 30),
        ):
            with pytest.raises(TimeoutExpired):
                service._git_commit("test message")


class TimeoutExpired(Exception):
    """Stand-in for subprocess.TimeoutExpired to avoid importing subprocess."""


class TestGitInitTimeoutPropagation:
    def test_git_init_timeout_propagates(self, service: MemoryService):
        with mock.patch(
            "subprocess.run",
            side_effect=TimeoutExpired("git", 30),
        ):
            with pytest.raises(TimeoutExpired):
                service._git_init()