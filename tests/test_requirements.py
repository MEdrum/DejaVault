"""Tests for unused dependencies (issue #25).

The requirements.txt must not list packages that are never imported
by the application code.
"""

from pathlib import Path

import pytest

REQUIREMENTS = Path(__file__).parent.parent / "requirements.txt"

# Packages that were previously listed but are never imported in app/
UNUSED_PACKAGES = ["python-multipart", "pyyaml", "gitpython"]


def _requirements_text() -> str:
    return REQUIREMENTS.read_text(encoding="utf-8")


class TestRequirements:
    def test_requirements_file_exists(self):
        assert REQUIREMENTS.exists()

    @pytest.mark.parametrize("pkg", UNUSED_PACKAGES)
    def test_unused_packages_removed(self, pkg):
        text = _requirements_text()
        assert pkg not in text, f"Unused dependency '{pkg}' is still in requirements.txt"

    def test_required_packages_present(self):
        text = _requirements_text()
        for pkg in ("fastapi", "uvicorn", "pydantic", "chromadb", "pytest"):
            assert pkg in text, f"Required package '{pkg}' is missing from requirements.txt"

    def test_no_duplicate_entries(self):
        lines = [
            line.strip()
            for line in _requirements_text().splitlines()
            if line.strip() and not line.startswith("#")
        ]
        assert len(lines) == len(set(lines)), "Duplicate entries in requirements.txt"