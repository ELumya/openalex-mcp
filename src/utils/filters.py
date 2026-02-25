"""Query filtering and formatting utilities for OpenAlex API.

This module provides functions to:
- Build filtered queries for Works, Authors, and Institutions
- Apply institution and affiliation filters
- Format API responses consistently
"""

from fastmcp.exceptions import ToolError
from pyalex import Works, Authors, Institutions
from .normalizers import detect_id_type
from .institution import get_first_institution_id
from .author import get_first_author_id


def apply_institution_filter(query, institution: str, use_lineage: bool = True):
    """Apply institution filter to a Works query.

    Args:
        query: PyAlex Works query object
        institution: Institution name, ROR ID, or OpenAlex ID
        use_lineage: Whether to include child institutions (default True)

    Returns:
        Filtered query object

    Raises:
        ToolError: If institution not found (code: INSTITUTION_NOT_FOUND)
    """
    id_type, normalized_id = detect_id_type(institution)
    
    if id_type == "openalex_institution":
        # OpenAlex IDs support lineage filter (includes child institutions)
        filter_key = "lineage" if use_lineage else "id"
        return query.filter(authorships={"institutions": {filter_key: normalized_id}})
    
    elif id_type == "ror":
        # OpenAlex natively supports ROR filtering on authorships
        return query.filter(authorships={"institutions": {"ror": normalized_id}})
    
    else:
        # Name search - resolve to ID
        institution_id = get_first_institution_id(institution)
        if not institution_id:
            raise ToolError("INSTITUTION_NOT_FOUND", f"No institution found matching: {institution}")
        
        # Recurse with resolved ID
        return apply_institution_filter(query, institution_id, use_lineage)


def apply_affiliation_filter(query, affiliation: str, use_lineage: bool = True):
    """Apply affiliation filter to an Authors query.

    Args:
        query: PyAlex Authors query object
        affiliation: Institution name, ROR ID, or OpenAlex ID
        use_lineage: Whether to include child institutions (default True)

    Returns:
        Filtered query object

    Raises:
        ToolError: If institution not found (code: INSTITUTION_NOT_FOUND)
    """
    id_type, normalized_id = detect_id_type(affiliation)
    
    if id_type == "openalex_institution":
        # OpenAlex IDs support lineage filter (includes child institutions)
        filter_key = "lineage" if use_lineage else "id"
        return query.filter(last_known_institutions={filter_key: normalized_id})
    
    elif id_type == "ror":
        # OpenAlex natively supports ROR filtering on last_known_institutions
        return query.filter(last_known_institutions={"ror": normalized_id})
    
    else:
        # Name search
        institution_id = get_first_institution_id(affiliation)
        if not institution_id:
            raise ToolError("INSTITUTION_NOT_FOUND", f"No institution found: {affiliation}")
        
        # Recurse with resolved ID
        return apply_affiliation_filter(query, institution_id, use_lineage)


def build_works_query(
    search_query: str,
    search_range: str = "title_abstract",
    institution: str | None = None,
    publication_year: int | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    type: str | None = None,
    peer_reviewed_only: bool = False,
    author: str | None = None,
    sort: str | None = None
):
    """Build a Works query with filters and sorting.

    Args:
        search_query: Search query string
        search_range: Search scope ('title_abstract', 'title', 'abstract', 'general')
        institution: Institution filter (name, ROR, or OpenAlex ID)
        publication_year: Publication year filter
        from_date: Start date filter (YYYY-MM-DD or YYYY)
        to_date: End date filter (YYYY-MM-DD or YYYY)
        type: Work type filter (e.g., 'article', 'review')
        peer_reviewed_only: Filter for peer-reviewed content only
        author: Author filter (name or OpenAlex ID)
        sort: Sort string in "field:direction" format (e.g., "publication_year:desc")

    Returns:
        Configured PyAlex Works query

    Raises:
        ToolError: If author or institution not found
    """
    # Build base query based on search range
    query = {
        "title_abstract": lambda: Works().filter(**{"title_and_abstract.search": search_query}),
        "title": lambda: Works().search_filter(title=search_query),
        "abstract": lambda: Works().search_filter(abstract=search_query),
        "general": lambda: Works().search(search_query)
    }[search_range]()
    
    # Apply filters
    if peer_reviewed_only:
        query = query.filter(is_paratext=False, type="article")
    
    if publication_year:
        query = query.filter(publication_year=publication_year)
    
    if from_date:
        query = query.filter(from_publication_date=from_date)
    
    if to_date:
        query = query.filter(to_publication_date=to_date)
    
    if type:
        query = query.filter(type=type)
    
    if institution:
        query = apply_institution_filter(query, institution)
    
    if author:
        id_type, normalized_id = detect_id_type(author)
        if id_type == "openalex_author":
            author_id = normalized_id
        else:
            author_id = get_first_author_id(author)
            if not author_id:
                raise ToolError("AUTHOR_NOT_FOUND", f"No author found matching: {author}")
        
        query = query.filter(author={"id": author_id})
    
    if sort:
        field, _, direction = sort.partition(":")
        query = query.sort(**{field: direction or "desc"})
    
    return query


def format_work_result(work: dict) -> dict:
    """Format a work result with consistent open_access handling."""
    result = {
        "id": work.get("id"),
        "doi": work.get("doi"),
        "title": work.get("title"),
        "publication_year": work.get("publication_year")
    }

    # Standardized open_access format
    open_access = work.get("open_access", {})
    if open_access.get("is_oa", False):
        result["open_access_url"] = open_access.get("oa_url")
    else:
        result["is_open_access"] = False

    # Include primary topic if available
    if "primary_topic" in work:
        result["primary_topic"] = {
            "id": work["primary_topic"].get("id"),
            "name": work["primary_topic"].get("display_name")
        }

    # Include 3 first authors if available
    authorships = work.get("authorships", [])
    if authorships:
        result["authors"] = [
            {
                "id": authorship.get("author", {}).get("id"),
                "display_name": authorship.get("author", {}).get("display_name")
            }
            for authorship in authorships[:3]
        ]

    return result


def format_institution_result(inst: dict) -> dict:
    """Format an institution result with consistent structure."""
    result = {
        "id": inst.get("ror") or inst.get("id"),
        "display_name": inst.get("display_name"),
        "country_code": inst.get("country_code"),
        "type": inst.get("type"),
        "works_count": inst.get("works_count")
    }

    # Include parent institutions (lineage) if available
    lineage = inst.get("lineage", [])
    if len(lineage) > 1:
        result["parent_institutions"] = lineage[:-1]  # Exclude self from lineage

    return result


def format_author_result(author: dict) -> dict:
    """Format an author result with consistent structure."""
    result = {
        "id": author.get("id"),
        "display_name": author.get("display_name"),
        "orcid": author.get("orcid"),
        "works_count": author.get("works_count")
    }

    # Format institutions consistently
    institutions = author.get("last_known_institutions", [])
    if institutions:
        result["last_known_institutions"] = [
            format_institution_result(inst) for inst in institutions
        ]
    else:
        result["last_known_institutions"] = []

    return result
