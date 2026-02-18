"""Author-related utility functions for OpenAlex MCP server."""

from pyalex import Authors


def get_author_ids_by_name(name: str, limit: int = 5) -> list[str]:
    """Search authors by name and return OpenAlex IDs.

    Uses fuzzy search to find authors matching the given name.
    Returns a list of OpenAlex author IDs (or ORCID IDs when available).

    Args:
        name: Author name or partial name to search for
        limit: Maximum number of results to return (default: 5)

    Returns:
        List of author IDs (ORCID preferred, OpenAlex ID as fallback)
        Returns empty list if no matches found or on error
    """
    try:
        # Search authors using pyalex
        results = Authors().search(name).select([
            "id", "orcid"
        ]).get(per_page=limit)

        # Extract IDs, preferring ORCID over OpenAlex ID
        ids = []
        for author in results:
            author_id = author.get("orcid") or author.get("id")
            if author_id:
                ids.append(author_id)

        return ids

    except Exception:
        # Return empty list on any error
        return []


def get_first_author_id(name: str) -> str | None:
    """Get the first (most relevant) author ID for a given name.

    Convenience function that returns only the top result from author search.

    Args:
        name: Author name or partial name to search for

    Returns:
        Author ID (ORCID or OpenAlex) or None if not found
    """
    ids = get_author_ids_by_name(name, limit=1)
    return ids[0] if ids else None
