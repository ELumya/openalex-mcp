"""Utility functions for OpenAlex MCP server.

This package provides helper functions for:
- ID validation and normalization (normalizers)
- Query building and result formatting (filters)
- Author and institution lookup (author, institution)
"""

from utils.normalizers import (
    normalize_id,
    id_to_filter_dict,
)

from utils.filters import (
    build_works_query,
    format_work_result,
    format_author_result,
    format_institution_result,
    apply_institution_filter
)

from utils.author import resolve_author_id
from utils.institution import resolve_institution_id

__all__ = [
    # Normalizers
    "normalize_id",
    "id_to_filter_dict",
    # Filters
    "build_works_query",
    "format_work_result",
    "format_author_result",
    "format_institution_result",
    "apply_institution_filter",
    # Author utilities
    "resolve_author_id",
    # Institution utilities
    "resolve_institution_id",
]
