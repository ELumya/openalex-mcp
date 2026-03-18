"""Utility functions for OpenAlex MCP server.

This package provides helper functions for:
- ID validation and normalization (normalizers)
- Query building and result formatting (filters)
- Author and institution lookup (author, institution)
- Generic entity resolution (resolver)
"""

from .normalizers import (
    normalize_id,
    id_to_filter_dict,
)

from .filters import (
    apply_sort,
    build_works_query,
    format_work_result,
    format_author_result,
    format_institution_result,
    apply_institution_filter,
)

from .resolver import resolve_entity_id, resolve_author_id, resolve_institution_id

__all__ = [
    # Normalizers
    "normalize_id",
    "id_to_filter_dict",
    # Filters
    "apply_sort",
    "build_works_query",
    "format_work_result",
    "format_author_result",
    "format_institution_result",
    "apply_institution_filter",
    # Resolver
    "resolve_entity_id",
    # Author utilities
    "resolve_author_id",
    # Institution utilities
    "resolve_institution_id",
]
