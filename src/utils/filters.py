"""Query filtering and formatting utilities for OpenAlex API.

This module provides functions to:
- Build filtered queries for Works, Authors, and Institutions
- Apply institution and affiliation filters
- Format API responses consistently
"""

from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from pyalex import Works, Authors, Institutions
from .normalizers import normalize_id, id_to_filter_dict
from .institution import resolve_institution_id
from .author import resolve_author_id


async def apply_institution_filter(
    query,
    institution: str,
    filter_scope: str = "works",
    use_lineage: bool = True,
    ctx: Context | None = None
):
    """Apply institution filter to a Works or Authors query.

    Args:
        query: PyAlex query object (Works or Authors)
        institution: Institution name, ROR ID, or OpenAlex ID
        filter_scope: "works" → filters ``authorships.institutions``;
                      "authors" → filters ``last_known_institutions``
        use_lineage: Include child institutions (default True, OpenAlex IDs only)
        ctx: FastMCP context for elicitation when resolving names (optional)

    Returns:
        Filtered query object

    Raises:
        ToolError: If institution not found
    """
    api_id = normalize_id(institution)

    if api_id is None:
        # Free-text name → resolve (with optional elicitation) then recurse
        resolved = await resolve_institution_id(institution, ctx)
        return await apply_institution_filter(query, resolved, filter_scope, use_lineage, ctx)

    filter_dict = id_to_filter_dict(api_id, lineage=use_lineage)

    if filter_scope == "works":
        return query.filter(authorships={"institutions": filter_dict})
    else:
        return query.filter(last_known_institutions=filter_dict)


async def build_works_query(
    query_string: str,
    search_range: str = "title_abstract",
    institution: str | None = None,
    publication_year: int | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    type: str | None = None,
    peer_reviewed_only: bool = False,
    author: str | None = None,
    sort: str | None = None,
    ctx: Context | None = None
):
    """Build a Works query with filters and sorting.

    Args:
        query_string: Search query string
        search_range: Search scope ('title_abstract', 'title', 'abstract', 'general')
        institution: Institution filter (name, ROR, or OpenAlex ID)
        publication_year: Publication year filter
        from_date: Start date filter (YYYY-MM-DD or YYYY)
        to_date: End date filter (YYYY-MM-DD or YYYY)
        type: Work type filter (e.g., 'article', 'review')
        peer_reviewed_only: Filter for peer-reviewed content only
        author: Author filter (name or OpenAlex ID)
        sort: Sort string in "field:direction" format (e.g., "publication_year:desc")
        ctx: FastMCP context for elicitation when resolving names (optional)

    Returns:
        Configured PyAlex Works query

    Raises:
        ToolError: If author or institution not found
    """
    # Build base query based on search range
    if search_range == "title_abstract":
        query = Works().filter(**{"title_and_abstract.search": query_string})
    elif search_range == "title":
        query = Works().search_filter(title=query_string)
    elif search_range == "abstract":
        query = Works().search_filter(abstract=query_string)
    else:
        query = Works().search(query_string)

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
        query = await apply_institution_filter(query, institution, "works", ctx=ctx)

    if author:
        api_id = normalize_id(author)
        if api_id is not None:
            query = query.filter(author=id_to_filter_dict(api_id))
        else:
            # Free-text name → resolve to OpenAlex A-ID
            author_openalex_id = await resolve_author_id(author, ctx)
            query = query.filter(author={"id": author_openalex_id})

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
