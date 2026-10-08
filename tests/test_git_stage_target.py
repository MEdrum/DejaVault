"""Tests for staging only the target file in git commits (issue #22).

_git_commit must stage only the specific file being changed, not
everything in the repo (git add .), so unrelated manual changes are
not swept into memory commits.
"""

from unittest import mock

from app.services.memory_service import MemoryService


class TestGitCommitStagesOnlyTargetFile:
    def test_git_add_uses_specific_file(self, service: MemoryService):
        """git add must target the file, not '.'."""
        rev_parse = mock.Mock(stdout="abc123\n", returncode=0)
        commit = mock.Mock(stdout="[main abc123] msg\n", stderr="", returncode=0)

        def fake_run(cmd, **kwargs):
            if cmd[1] == "commit":
                return commit
            if cmd[1] == "rev-parse":
                return rev_parse
            return mock.Mock(returncode=0)

        with mock.patch("subprocess.run", side_effect=fake_run) as mock_run:
            service._git_commit("msg", "notes/foo.md")

        # First call must be: git add -- notes/foo.md
        add_call = mock_run.call_args_list[0]
        cmd = add_call.args[0]
        assert cmd[0] == "git"
        assert cmd[1] == "add"
        assert cmd[2] == "--"
        assert cmd[3] == "notes/foo.md"
        assert "." not in cmd, "git add . must not be used"

    def test_git_add_never_uses_dot(self, service: MemoryService):
        """No git add call should ever stage '.'."""
        rev_parse = mock.Mock(stdout="abc123\n", returncode=0)
        commit = mock.Mock(stdout="[main abc123] msg\n", stderr="", returncode=0)

        def fake_run(cmd, **kwargs):
            if cmd[1] == "commit":
                return commit
            if cmd[1] == "rev-parse":
                return rev_parse
            return mock.Mock(returncode=0)

        with mock.patch("subprocess.run", side_effect=fake_run) as mock_run:
            service._git_commit("msg", "foo.md")

        for call in mock_run.call_args_list:
            cmd = call.args[0]
            if cmd[1] == "add":
                assert "." not in cmd, f"git add . used: {cmd}"


class TestRecordStagesOnlyTargetFile:
    def test_record_commits_only_the_new_file(self, service: MemoryService, memory_repo):
        """After record(), only the new file should be committed."""
        import subprocess

        # Create an unrelated modified file that must NOT be committed
        (memory_repo / "unrelated.md").write_text("unrelated change")

        service.record("new.md", "hello", "init")

        # The commit should only contain new.md
        result = subprocess.run(
            ["git", "show", "--stat", "--oneline", "HEAD"],
            cwd=memory_repo, capture_output=True, text=True, check=True,
        )
        assert "new.md" in result.stdout
        assert "unrelated.md" not in result.stdout