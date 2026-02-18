"""ID normalization and validation utilities for OpenAlex entities."""

import re
from fastmcp.exceptions import ToolError


def normalize_url(url: str, *prefixes: str) -> str:
    """Strip common URL prefixes from an identifier."""
    for prefix in prefixes:
        if url.startswith(prefix):
            return url.replace(prefix, "")
    return url


def normalize_openalex_id(id_str: str) -> str:
    """Normalize OpenAlex Work/Author/Institution ID by stripping URL prefix."""
    return normalize_url(
        id_str,
        "https://openalex.org/",
        "http://openalex.org/"
    )


def normalize_doi(doi: str) -> str:
    """Normalize DOI by stripping URL prefix."""
    return normalize_url(
        doi,
        "https://doi.org/",
        "http://doi.org/"
    )


def normalize_ror(ror: str) -> str:
    """Normalize ROR ID by stripping URL prefix."""
    return normalize_url(
        ror,
        "https://ror.org/",
        "http://ror.org/"
    )


def normalize_orcid(orcid: str) -> str:
    """Normalize ORCID by stripping URL prefix."""
    return normalize_url(
        orcid,
        "https://orcid.org/",
        "http://orcid.org/"
    )


def validate_work_id(work_id: str) -> str:
    """Validate and normalize Work ID (OpenAlex or DOI)."""
    normalized = normalize_openalex_id(normalize_doi(work_id))
    if not re.match(r'^(W\d{10}|10\..+)', normalized):
        raise ToolError(
            f"INVALID_WORK_ID",
            f"Invalid work_id: {work_id}. Expected OpenAlex ID (W1234567890) or DOI (10.xxxx/...)"
        )
    return normalized


def validate_orcid(orcid: str) -> str:
    """Validate and normalize ORCID."""
    normalized = normalize_orcid(orcid)
    if not re.match(r'^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$', normalized):
        raise ToolError(
            "INVALID_ORCID",
            f"Invalid ORCID: {orcid}. Expected format: XXXX-XXXX-XXXX-XXXX"
        )
    return normalized


def detect_id_type(id_str: str) -> tuple[str, str]:
    """Detect ID type and return (type, normalized_id).
    
    Types: openalex_work, openalex_author, openalex_institution, ror, doi, orcid, unknown.
    """
    # Check ORCID first (before stripping other prefixes)
    orcid_normalized = normalize_orcid(id_str)
    if re.match(r'^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$', orcid_normalized):
        return "orcid", orcid_normalized

    # Normalize all common prefixes
    normalized = normalize_openalex_id(normalize_ror(normalize_doi(id_str)))

    if re.match(r'^I\d{10}$', normalized):
        return "openalex_institution", normalized
    elif re.match(r'^A\d{10}$', normalized):
        return "openalex_author", normalized
    elif re.match(r'^W\d{10}$', normalized):
        return "openalex_work", normalized
    elif re.match(r'^0[a-z0-9]{8}$', normalized):
        return "ror", normalized
    elif re.match(r'^10\..+', normalized):
        return "doi", normalized
    else:
        return "unknown", normalized


def to_openalex_api_format(id_str: str) -> str:
    """Convert any supported ID to the format expected by the PyAlex single-entity fetch.
    
    - OpenAlex IDs (W/A/I...) → returned as-is
    - DOI → "doi:10.xxxx/yyyy"
    - ROR → "ror:03n15ch10"
    - ORCID → "orcid:0000-0002-1298-3089"
    - Unknown → returned as-is (let PyAlex handle the error)
    """
    id_type, normalized = detect_id_type(id_str)
    if id_type.startswith("openalex_"):
        return normalized
    if id_type == "doi":
        return f"doi:{normalized}"
    if id_type == "ror":
        return f"ror:{normalized}"
    if id_type == "orcid":
        return f"orcid:{normalized}"
    return normalized
