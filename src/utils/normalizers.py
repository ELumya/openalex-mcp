"""ID normalization utilities for OpenAlex entities."""

import re

# ── Compiled patterns ─────────────────────────────────────────────────────────

_ORCID_RE = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")
_ROR_RE   = re.compile(r"^0[a-z0-9]{8}$")
_DOI_RE   = re.compile(r"^10\..+")
_W_RE     = re.compile(r"^W\d{10}$")
_A_RE     = re.compile(r"^A\d{10}$")
_I_RE     = re.compile(r"^I\d{10}$")

# ── URL prefix tables ─────────────────────────────────────────────────────────

# Plain URL prefixes whose type is determined by the bare value that follows
_PLAIN_URL_PREFIXES = (
    "https://openalex.org/",
    "http://openalex.org/",
)

# Typed URL prefixes: stripping them tells us the ID type immediately
_TYPED_URL_PREFIXES: tuple[tuple[str, str], ...] = (
    ("https://doi.org/",                    "doi"),
    ("http://doi.org/",                     "doi"),
    ("https://orcid.org/",                  "orcid"),
    ("http://orcid.org/",                   "orcid"),
    ("https://ror.org/",                    "ror"),
    ("http://ror.org/",                     "ror"),
    ("https://pubmed.ncbi.nlm.nih.gov/",    "pmid"),
    ("http://pubmed.ncbi.nlm.nih.gov/",     "pmid"),
    ("https://www.wikidata.org/wiki/",      "wikidata"),
    ("http://www.wikidata.org/wiki/",       "wikidata"),
)

# URN prefixes the OpenAlex API recognises natively
# Works:        doi, mag, pmid, pmcid
# Authors:      orcid, scopus, twitter, wikipedia
# Institutions: ror, mag, wikidata
_KNOWN_URN_PREFIXES = {
    "doi", "mag", "pmid", "pmcid",          # works
    "orcid", "scopus", "twitter", "wikipedia",  # authors
    "ror", "wikidata",                       # institutions
}


# ── Internal helper ───────────────────────────────────────────────────────────

def _format(prefix: str, value: str) -> str | None:
    """Return ``"prefix:value"`` after basic validation, or ``None`` if invalid."""
    match prefix:
        case "orcid":
            return f"orcid:{value}" if _ORCID_RE.match(value) else None
        case "doi":
            return f"doi:{value}" if _DOI_RE.match(value) else None
        case _:  # ror, pmid, pmcid, mag — accept any non-empty value
            return f"{prefix}:{value}" if value else None


# ── Public API ────────────────────────────────────────────────────────────────

def normalize_id(id_str: str) -> str | None:
    """Normalize any OpenAlex entity identifier to a canonical API-ready string.

    Strips URL and URN prefixes, validates patterns, and returns a string
    that can be passed directly to pyalex single-entity lookups
    (``Works()[api_id]``) or decomposed into a filter dict via
    :func:`id_to_filter_dict`.

    Supported identifiers
    ---------------------
    Works        — ``W\\d{10}``, ``doi:``, ``pmid:``, ``pmcid:``, ``mag:``
    Authors      — ``A\\d{10}``, ``orcid:``, ``scopus:``, ``twitter:``, ``wikipedia:``
    Institutions — ``I\\d{10}``, ``ror:``, ``mag:``, ``wikidata:``

    All of these are accepted with or without URL prefix
    (``https://doi.org/…``, ``https://orcid.org/…``, …) and with or without
    URN prefix (``doi:…``, ``orcid:…``, ``ror:…``, …).

    Returns
    -------
    ``"W…"`` / ``"A…"`` / ``"I…"``
        Native OpenAlex IDs — no prefix.
    ``"doi:10.xxx/…"`` / ``"orcid:0000-…"`` / ``"ror:0xxxxxxxx"``
    ``"pmid:…"`` / ``"pmcid:…"`` / ``"mag:…"``
        Prefixed external IDs accepted directly by the OpenAlex API.
    ``None``
        Input looks like a free-text name or is unrecognisable.
        Callers should fall back to a name search.
    """
    s = id_str.strip()

    # 1. Typed URL prefixes — the URL itself encodes the ID type
    for url_prefix, urn_prefix in _TYPED_URL_PREFIXES:
        if s.startswith(url_prefix):
            return _format(urn_prefix, s[len(url_prefix):])

    # 2. Plain URL prefixes (openalex.org) — strip and fall through
    for url_prefix in _PLAIN_URL_PREFIXES:
        if s.startswith(url_prefix):
            s = s[len(url_prefix):]
            break

    # 3. Explicit URN prefix (doi:, orcid:, ror:, pmid:, pmcid:, mag:)
    if ":" in s:
        prefix, _, value = s.partition(":")
        if prefix.lower() in _KNOWN_URN_PREFIXES:
            return _format(prefix.lower(), value)
        # Colon not from a known prefix — could be inside a DOI, fall through

    # 4. Pattern-match bare value
    if _W_RE.match(s):     return s              # OpenAlex work
    if _A_RE.match(s):     return s              # OpenAlex author
    if _I_RE.match(s):     return s              # OpenAlex institution
    if _ORCID_RE.match(s): return f"orcid:{s}"  # bare ORCID
    if _ROR_RE.match(s):   return f"ror:{s}"    # bare ROR
    if _DOI_RE.match(s):   return f"doi:{s}"    # bare DOI (no prefix stripped)

    return None  # looks like a free-text name


def id_to_filter_dict(api_id: str, *, lineage: bool = False) -> dict:
    """Convert an API-format ID string to a pyalex filter dict.

    Parameters
    ----------
    api_id:
        A value returned by :func:`normalize_id` (never ``None``).
    lineage:
        When ``True`` and *api_id* is a native OpenAlex Institution ID,
        use the ``lineage`` filter key so child institutions are included.

    Examples
    --------
    ``"A5023888391"``               → ``{"id": "A5023888391"}``
    ``"I27837315"`` (lineage=False) → ``{"id": "I27837315"}``
    ``"I27837315"`` (lineage=True)  → ``{"lineage": "I27837315"}``
    ``"orcid:0000-0002-1298-3089"`` → ``{"orcid": "0000-0002-1298-3089"}``
    ``"ror:00cvxb145"``             → ``{"ror": "00cvxb145"}``
    ``"doi:10.7717/peerj.4375"``   → ``{"doi": "10.7717/peerj.4375"}``
    """
    if ":" in api_id:
        prefix, value = api_id.split(":", 1)
        return {prefix: value}
    # Native OpenAlex ID
    if lineage and _I_RE.match(api_id):
        return {"lineage": api_id}
    return {"id": api_id}
