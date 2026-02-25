"""Author-related utility functions for OpenAlex MCP server."""

from pyalex import Authors
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from .normalizers import normalize_id


async def resolve_author_id(name_or_id: str, ctx: Context | None = None) -> str:
    """Resolve an author name or external ID to an OpenAlex Author ID.

    - Known external IDs (OpenAlex A..., ORCID) are passed through directly.
    - Name queries trigger a fuzzy search. If multiple matches are found and
      ctx is available, the user is prompted to pick one via elicitation.
    - Fallback: returns the first (most relevant) search result.

    Args:
        name_or_id: Author name or external ID (OpenAlex, ORCID)
        ctx: FastMCP context for elicitation (optional)

    Returns:
        OpenAlex Author ID ready for use in API calls

    Raises:
        ToolError: If no author is found matching the name
    """
    api_id = normalize_id(name_or_id)

    # Known external ID → pass directly without a search
    if api_id is not None:
        return api_id

    # Fuzzy name search
    results = Authors().search(name_or_id).select([
        "id", "display_name", "works_count", "topics", "last_known_institutions"
    ]).get(per_page=5)

    if not results:
        raise ToolError("AUTHOR_NOT_FOUND", f"No author found matching: {name_or_id}")

    if len(results) == 1:
        return normalize_id(results[0]["id"]) or results[0]["id"]

    # Multiple results → try elicitation
    if ctx is not None:
        try:
            options = {}
            for a in results:
                topics = ", ".join(
                    t.get("display_name", "") for t in (a.get("topics") or [])[:3]
                )
                insts = a.get("last_known_institutions") or []
                inst_name = insts[0].get("display_name", "") if insts else ""
                parts = [p for p in [
                    inst_name,
                    f"Topics: {topics}" if topics else None,
                    f"{a.get('works_count', 0)} works"
                ] if p]
                options[a["id"]] = {"title": f"{a['display_name']} — {'; '.join(parts)}"}

            from fastmcp.server.elicitation import AcceptedElicitation
            result = await ctx.elicit(
                f"Multiple authors match '{name_or_id}'. Please select one:",
                response_type=options,
            )
            if isinstance(result, AcceptedElicitation):
                return result.data
        except Exception:
            pass  # Fall through to first result

    # Fallback: first (most relevant) result
    return results[0]["id"]
