"""Institution-related utility functions for OpenAlex MCP server."""

from pyalex import Institutions
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from .normalizers import normalize_id


async def resolve_institution_id(name_or_id: str, ctx: Context | None = None) -> str:
    """Resolve an institution name or external ID to an OpenAlex Institution ID.

    - Known external IDs (OpenAlex I..., ROR) are passed through directly.
    - Name queries trigger a fuzzy search. If multiple matches are found and
      ctx is available, the user is prompted to pick one via elicitation.
    - Fallback: returns the first (most relevant) search result.

    Args:
        name_or_id: Institution name or external ID (OpenAlex, ROR)
        ctx: FastMCP context for elicitation (optional)

    Returns:
        OpenAlex Institution ID ready for use in API calls

    Raises:
        ToolError: If no institution is found matching the name
    """
    api_id = normalize_id(name_or_id)

    # Known external ID → pass directly without a search
    if api_id is not None:
        return api_id

    # Fuzzy name search
    results = Institutions().search(name_or_id).select([
        "id", "display_name", "country_code", "type", "works_count"
    ]).get(per_page=5)

    if not results:
        raise ToolError("INSTITUTION_NOT_FOUND", f"No institution found matching: {name_or_id}")

    if len(results) == 1:
        return normalize_id(results[0]["id"]) or results[0]["id"]

    # Multiple results → try elicitation
    if ctx is not None:
        try:
            options = {}
            for inst in results:
                parts = [p for p in [
                    inst.get("country_code"),
                    inst.get("type"),
                    f"{inst.get('works_count', 0)} works"
                ] if p]
                options[inst["id"]] = {"title": f"{inst['display_name']} — {'; '.join(parts)}"}

            from fastmcp.server.elicitation import AcceptedElicitation
            result = await ctx.elicit(
                f"Multiple institutions match '{name_or_id}'. Please select one:",
                response_type=options,
            )
            if isinstance(result, AcceptedElicitation):
                return result.data
        except Exception:
            pass  # Fall through to first result

    # Fallback: first (most relevant) result
    return results[0]["id"]
