"""Tests for search_type validation (issue #17).

Invalid search types must be rejected instead of silently returning
empty results. The schema uses Literal to reject at the API boundary,
and the service raises ValueError as a defensive check.
"""

import pytest
from pydantic import ValidationError

from app.models.schemas import MemorySearchRequest
from app.services.memory_service import MemoryService


class TestSearchRequestSchema:
    def test_default_search_type_is_hybrid(self):
        req = MemorySearchRequest(query="hello")
        assert req.search_type == "hybrid"

    @pytest.mark.parametrize("valid", ["keyword", "vector", "hybrid"])
    def test_valid_search_types_accepted(self, valid):
        req = MemorySearchRequest(query="hello", search_type=valid)
        assert req.search_type == valid

    @pytest.mark.parametrize("invalid", ["", "semantic", "KEYWORD", "hybrid ", "vector2", "123"])
    def test_invalid_search_types_rejected(self, invalid):
        with pytest.raises(ValidationError):
            MemorySearchRequest(query="hello", search_type=invalid)


class TestSearchServiceValidation:
    @pytest.mark.parametrize("invalid", ["", "semantic", "KEYWORD", "hybrid ", "vector2", "123"])
    def test_invalid_search_type_raises_value_error(self, service: MemoryService, invalid):
        with pytest.raises(ValueError, match="Invalid search_type"):
            service.search("hello", search_type=invalid)

    @pytest.mark.parametrize("valid", ["keyword", "vector", "hybrid"])
    def test_valid_search_types_do_not_raise(self, service: MemoryService, valid):
        # No collection attached -> vector/hybrid return empty, keyword runs rg.
        # We only assert that no ValueError is raised for valid types.
        service.search("hello", search_type=valid)