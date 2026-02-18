"""Institution-related utility functions for OpenAlex MCP server."""

from pyalex import Institutions


def get_institution_ids_by_name(name: str, limit: int = 5) -> list[str]:
    """Search institutions by name and return OpenAlex IDs.

    Uses fuzzy search to find institutions matching the given name.
    Returns a list of OpenAlex institution IDs (or ROR IDs when available).

    Args:
        name: Institution name or partial name to search for
        limit: Maximum number of results to return (default: 5)

    Returns:
        List of institution IDs (ROR preferred, OpenAlex ID as fallback)
        Returns empty list if no matches found or on error
    """
    try:
        # Search institutions using pyalex
        results = Institutions().search(name).select([
            "id", "ror"
        ]).get(per_page=limit)

        # Extract IDs, preferring ROR over OpenAlex ID
        ids = []
        for inst in results:
            institution_id = inst.get("ror") or inst.get("id")
            if institution_id:
                ids.append(institution_id)

        return ids

    except Exception:
        # Return empty list on any error
        return []


def get_first_institution_id(name: str) -> str | None:
    """Get the first (most relevant) institution ID for a given name.

    Convenience function that returns only the top result from institution search.

    Args:
        name: Institution name or partial name to search for

    Returns:
        Institution ID (ROR or OpenAlex) or None if not found
    """
    ids = get_institution_ids_by_name(name, limit=1)
    return ids[0] if ids else None
