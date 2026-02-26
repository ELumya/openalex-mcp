"""Query filtering and formatting utilities for OpenAlex API.

This module provides functions to:
- Build filtered queries for Works, Authors, and Institutions
- Apply institution and affiliation filters
- Format API responses consistently at two detail levels:
    low, compact, suitable for search result lists
    medium, richer, used by fetch_* tools (full object already downloaded)
"""

from typing import Literal

from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from pyalex import Works, Authors, Institutions
from .normalizers import normalize_id, id_to_filter_dict
from .institution import resolve_institution_id
from .author import resolve_author_id


# ── Shared helpers ────────────────────────────────────────────────────────────

def _format_topic(topic: dict) -> dict:
    """Serialize a topic object to {id, name, subfield}."""
    return {
        "id": topic.get("id"),
        "name": topic.get("display_name"),
        "subfield": (topic.get("subfield") or {}).get("display_name"),
    }


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


def format_work_result(work: dict, detail: Literal["low", "medium"] = "low") -> dict:
    """Format a work result.

    Args:
        work: Raw work dict from pyalex.
        detail: ``"low"`` (compact, for search lists) or ``"medium"`` (richer,
                for single-entity fetches).  Abstract and fulltext are always
                handled separately by the caller.
    """
    result = {
        "id": work.get("id"),
        "doi": work.get("doi"),
        "title": work.get("title"),
        "publication_year": work.get("publication_year"),
    }

    # Standardized open_access format
    open_access = work.get("open_access", {})
    if open_access.get("is_oa", False):
        result["open_access_url"] = open_access.get("oa_url")
    else:
        result["is_open_access"] = False

    if detail == "low":
        # Primary topic
        if "primary_topic" in work and work["primary_topic"]:
            result["primary_topic"] = {
                "id": work["primary_topic"].get("id"),
                "name": work["primary_topic"].get("display_name"),
            }

        # First 3 authors, id + name only
        authorships = work.get("authorships") or []
        if authorships:
            result["authors"] = [
                {
                    "id": a.get("author", {}).get("id"),
                    "display_name": a.get("author", {}).get("display_name"),
                }
                for a in authorships[:3]
            ]

    else:  # medium
        result["type"] = work.get("type")

        # Citation metrics
        result["cited_by_count"] = work.get("cited_by_count")
        fwci = work.get("fwci")
        if fwci is not None:
            result["fwci"] = round(fwci, 3)
        cnp = work.get("citation_normalized_percentile") or {}
        if cnp:
            result["citation_percentile"] = {
                "is_in_top_1_percent": cnp.get("is_in_top_1_percent"),
                "is_in_top_10_percent": cnp.get("is_in_top_10_percent"),
            }

        # Bibliographic details
        result["biblio"] = work.get("biblio")

        # Source / venue from primary_location
        primary_location = work.get("primary_location") or {}
        source = primary_location.get("source") or {}
        if source:
            result["source"] = {
                "display_name": source.get("display_name"),
                "type": source.get("type"),
                "is_oa": source.get("is_oa"),
            }
        license_ = primary_location.get("license")
        if license_:
            result["license"] = license_

        # Topics list (replaces single primary_topic in medium)
        topics = work.get("topics") or []
        if topics:
            result["topics"] = [_format_topic(t) for t in topics[:3]]

        # Full author list with their institutions
        authorships = work.get("authorships") or []
        if authorships:
            result["authors"] = [
                {
                    "id": a.get("author", {}).get("id"),
                    "display_name": a.get("author", {}).get("display_name"),
                    "author_position": a.get("author_position"),
                    "is_corresponding": a.get("is_corresponding"),
                    "institutions": [
                        {
                            "display_name": inst.get("display_name"),
                            "id": inst.get("ror") or inst.get("id"),
                        }
                        for inst in (a.get("institutions") or [])
                    ],
                }
                for a in authorships
            ]

    return result


def format_institution_result(inst: dict, detail: Literal["low", "medium"] = "low") -> dict:
    """Format an institution result.

    Args:
        inst: Raw institution dict from pyalex.
        detail: ``"low"`` (compact) or ``"medium"`` (richer, for fetch_institution).
    """
    result = {
        "id": inst.get("ror") or inst.get("id"),
        "display_name": inst.get("display_name"),
        "country_code": inst.get("country_code"),
        "type": inst.get("type"),
        "works_count": inst.get("works_count"),
    }

    # Include parent institutions (lineage) if available
    lineage = inst.get("lineage", [])
    if len(lineage) > 1:
        result["parent_institutions"] = lineage[:-1]  # Exclude self from lineage

    if detail == "medium":
        result["cited_by_count"] = inst.get("cited_by_count")

        summary = inst.get("summary_stats", {})
        if summary:
            result["summary_stats"] = {
                "h_index": summary.get("h_index"),
                "i10_index": summary.get("i10_index"),
            }

        topics = inst.get("topics", [])
        if topics:
            result["topics"] = [_format_topic(t) for t in topics[:5]]

        geo = inst.get("geo", {})
        if geo:
            result["geo"] = {
                "city": geo.get("city"),
                "region": geo.get("region"),
                "country": geo.get("country"),
                "latitude": geo.get("latitude"),
                "longitude": geo.get("longitude"),
            }

        homepage = inst.get("homepage_url")
        if homepage:
            result["homepage_url"] = homepage

    return result


def format_author_result(author: dict, detail: Literal["low", "medium"] = "low") -> dict:
    """Format an author result.

    Args:
        author: Raw author dict from pyalex.
        detail: ``"low"`` (compact) or ``"medium"`` (richer, for fetch_author).
    """
    result = {
        "id": author.get("id"),
        "display_name": author.get("display_name"),
        "orcid": author.get("orcid"),
        "works_count": author.get("works_count"),
    }

    # Last known institutions, always included at low detail
    institutions = author.get("last_known_institutions", [])
    result["last_known_institutions"] = [
        format_institution_result(inst) for inst in institutions
    ]

    if detail == "medium":
        result["cited_by_count"] = author.get("cited_by_count")

        summary = author.get("summary_stats", {})
        if summary:
            result["summary_stats"] = {
                "h_index": summary.get("h_index"),
                "i10_index": summary.get("i10_index"),
                "2yr_mean_citedness": summary.get("2yr_mean_citedness"),
            }

        topics = author.get("topics", [])
        if topics:
            result["topics"] = [_format_topic(t) for t in topics[:3]]

        # Affiliation history sorted by most recent year first
        affiliations = author.get("affiliations", [])
        if affiliations:
            result["affiliations"] = sorted(
                [
                    {
                        "institution": {
                            "display_name": (aff.get("institution", {})).get("display_name"),
                            "id": (aff.get("institution", {})).get("ror")
                                  or (aff.get("institution", {})).get("id"),
                        },
                        "years": sorted(aff.get("years", []), reverse=True),
                    }
                    for aff in affiliations
                ],
                key=lambda x: x["years"][0] if x["years"] else 0,
                reverse=True,
            )

    return result
