"""Utility functions for OpenAlex MCP server.

This package provides helper functions for:
- ID validation and normalization (normalizers)
- Query building and result formatting (filters)
- Author and institution lookup (author, institution)
"""

from utils.normalizers import (
    validate_work_id,
    validate_orcid,
    detect_id_type,
    normalize_openalex_id,
    to_openalex_api_format
)

from utils.filters import (
    build_works_query,
    format_work_result,
    format_author_result,
    format_institution_result,
    apply_affiliation_filter
)

from utils.author import get_author_ids_by_name, get_first_author_id
from utils.institution import get_institution_ids_by_name, get_first_institution_id

__all__ = [
    # Normalizers
    "validate_work_id",
    "validate_orcid",
    "detect_id_type",
    "normalize_openalex_id",
    "to_openalex_api_format",
    # Filters
    "build_works_query",
    "format_work_result",
    "format_author_result",
    "format_institution_result",
    "apply_affiliation_filter",
    # Author utilities
    "get_author_ids_by_name",
    "get_first_author_id",
    # Institution utilities
    "get_institution_ids_by_name",
    "get_first_institution_id",
]
