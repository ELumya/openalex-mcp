"""Entity resolvers for OpenAlex MCP server.

Provides:
- ``resolve_entity_id`` — generic async helper (pass-through, fuzzy search,
  elicitation, consistent normalisation on every return path).
- ``resolve_author_id`` — convenience wrapper for Authors.
- ``resolve_institution_id`` — convenience wrapper for Institutions.
"""

from collections.abc import Callable

from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from pyalex import Authors, Institutions

from .normalizers import normalize_id

# Import elicitation support gracefully — older FastMCP builds may not have it.
try:
    from fastmcp.server.elicitation import AcceptedElicitation
    _ELICITATION_AVAILABLE = True
except ImportError:
    _ELICITATION_AVAILABLE = False


async def resolve_entity_id(
    entity_class,
    name_or_id: str,
    select_fields: list[str],
    display_fn: Callable[[dict], str],
    error_code: str,
    prompt_label: str,
    ctx: Context | None = None,
) -> str:
    """Resolve an entity name or external ID to an OpenAlex ID.

    Args:
        entity_class: PyAlex entity class (e.g. ``Authors``, ``Institutions``).
        name_or_id: Free-text name or external ID string.
        select_fields: Fields to request in the search query.
        display_fn: ``(entity_dict) -> str`` that produces a human-readable
            label for elicitation options.
        error_code: ``ToolError`` code emitted when no results are found.
        prompt_label: Singular entity type name used in error/elicitation
            messages (e.g. ``"author"``, ``"institution"``).
        ctx: FastMCP context for elicitation (optional).

    Returns:
        Normalised OpenAlex entity ID.

    Raises:
        ToolError: If no entity is found matching ``name_or_id``.
    """
    api_id = normalize_id(name_or_id)

    # Already a known external ID — pass through without a network search.
    if api_id is not None:
        return api_id

    # Fuzzy name search.
    results = (
        entity_class().search(name_or_id).select(select_fields).get(per_page=5)
    )

    if not results:
        raise ToolError(error_code, f"No {prompt_label} found matching: {name_or_id}")

    if len(results) == 1:
        return normalize_id(results[0]["id"]) or results[0]["id"]

    # Multiple results → try interactive disambiguation.
    if ctx is not None and _ELICITATION_AVAILABLE:
        try:
            options = {
                entity["id"]: {"title": display_fn(entity)} for entity in results
            }
            elicitation_result = await ctx.elicit(
                f"Multiple {prompt_label}s match '{name_or_id}'. Please select one:",
                response_type=options,
            )
            if isinstance(elicitation_result, AcceptedElicitation):
                chosen = elicitation_result.data
                return normalize_id(chosen) or chosen
        except (NotImplementedError, AttributeError):
            pass  # Elicitation not supported by this transport; fall through.

    # Fallback: first (most relevant) result.
    return normalize_id(results[0]["id"]) or results[0]["id"]


# ── Author ────────────────────────────────────────────────────────────────────

def _author_display(author: dict) -> str:
    """Build a human-readable label for an author elicitation option."""
    topics = ", ".join(
        t.get("display_name", "") for t in (author.get("topics") or [])[:3]
    )
    insts = author.get("last_known_institutions") or []
    inst_name = insts[0].get("display_name", "") if insts else ""
    parts = [p for p in [
        inst_name,
        f"Topics: {topics}" if topics else None,
        f"{author.get('works_count', 0)} works",
    ] if p]
    return f"{author['display_name']} — {'; '.join(parts)}"


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
    return await resolve_entity_id(
        entity_class=Authors,
        name_or_id=name_or_id,
        select_fields=["id", "display_name", "works_count", "topics", "last_known_institutions"],
        display_fn=_author_display,
        error_code="AUTHOR_NOT_FOUND",
        prompt_label="author",
        ctx=ctx,
    )


# ── Institution ───────────────────────────────────────────────────────────────

def _institution_display(inst: dict) -> str:
    """Build a human-readable label for an institution elicitation option."""
    parts = [p for p in [
        inst.get("country_code"),
        inst.get("type"),
        f"{inst.get('works_count', 0)} works",
    ] if p]
    return f"{inst['display_name']} — {'; '.join(parts)}"


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
    return await resolve_entity_id(
        entity_class=Institutions,
        name_or_id=name_or_id,
        select_fields=["id", "display_name", "country_code", "type", "works_count"],
        display_fn=_institution_display,
        error_code="INSTITUTION_NOT_FOUND",
        prompt_label="institution",
        ctx=ctx,
    )
