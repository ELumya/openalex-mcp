"""MCP OpenAlex Server

FastMCP server for OpenAlex scholarly data: search articles, authors, institutions, fetch detailed info.
Optimized for AI agent consumption.
"""

import io
import os
from typing import Annotated
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.dependencies import CurrentContext
from fastmcp.server.context import Context
from pydantic import Field
from pyalex import Works, Authors, Institutions
from markitdown import MarkItDown
import pyalex

# Import utilities
from utils.normalizers import validate_work_id, validate_orcid, detect_id_type, normalize_openalex_id, to_openalex_api_format
from utils.filters import (
    build_works_query, format_work_result, format_author_result,
    format_institution_result, apply_affiliation_filter
)
from utils.author import get_first_author_id
from utils.institution import get_first_institution_id

# Configure OpenAlex API key (REQUIRED as of Feb 13, 2026)
api_key = os.getenv("OPENALEX_API_KEY")
if not api_key:
    raise ValueError(
        "OPENALEX_API_KEY environment variable is required. "
        "Get your free API key at: https://openalex.org/settings/api"
    )
pyalex.config.api_key = api_key

# Configure pyalex retry logic
pyalex.config.max_retries = 3
pyalex.config.retry_backoff_factor = 0.1
pyalex.config.retry_http_codes = [429, 500, 503]

# Initialize FastMCP server
mcp = FastMCP(
    name="openalex",
    instructions="""OpenAlex scholarly database MCP server.""",
    version="0.1.0"
)


# ARTICLE SEARCH TOOL
@mcp.tool(annotations={"readOnlyHint": True})
async def search_articles(
    query_string: Annotated[str, Field(min_length=2, max_length=1000, description="Search query (Elasticsearch syntax)")],
    institution: Annotated[str | None, Field(description="Institution name, ROR, or OpenAlex Institution ID")] = None,
    publication_year: Annotated[int | None, Field(ge=1000, le=2100, description="Publication year (1000-2100)")] = None,
    from_date: Annotated[str | None, Field(description="Start date (YYYY-MM-DD or YYYY)")] = None,
    to_date: Annotated[str | None, Field(description="End date (YYYY-MM-DD or YYYY)")] = None,
    type: Annotated[str | None, Field(description="Work type: 'article', 'review', 'proceedings-article', etc.")] = None,
    limit: Annotated[int, Field(ge=1, le=200, description="Max results (1-200)")] = 20,
    page: Annotated[int, Field(ge=1, description="Page number for pagination")] = 1,
    peer_reviewed_only: Annotated[bool, Field(description="Filter peer-reviewed only")] = False,
    search_range: Annotated[str, Field(description="Search scope: 'general', 'title', 'abstract', 'title_abstract'")] = "title_abstract",
    sort: Annotated[str | None, Field(description="Sort: 'field:direction' (e.g. 'publication_year:desc')")] = None,
    ctx: Context = CurrentContext()
) -> dict:
    """Search OpenAlex articles with filters and ranking. Returns minimal data for quick scanning."""
    query = build_works_query(
        query_string=query_string,
        search_range=search_range,
        institution=institution,
        publication_year=publication_year,
        from_date=from_date,
        to_date=to_date,
        type=type,
        peer_reviewed_only=peer_reviewed_only,
        sort=sort
    )
    
    results = query.select([
        "id", "doi", "title", "publication_year", "open_access", "authorships", "primary_topic"
    ]).get(page=page, per_page=limit)
    
    return {
        "results": [format_work_result(work) for work in results],
        "count": results.meta.get("count", 0),
        "page": results.meta.get("page", 1),
        "per_page": results.meta.get("per_page", limit)
    }


# FETCH ARTICLE TOOL
@mcp.tool(annotations={"readOnlyHint": True})
async def fetch_article(
    work_id: Annotated[str, Field(min_length=1, description="OpenAlex Work ID or DOI")],
    include_abstract: Annotated[bool, Field(description="Include abstract in response")] = True,
    fulltext: Annotated[bool, Field(description="Include full-text content")] = False,
    prompt: Annotated[str | None, Field(description="Optional LLM prompt for analysis (if provided, returns LLM summary; otherwise returns markdown)")] = None,
    ctx: Context = CurrentContext()
) -> dict:
    """Fetch detailed article metadata. If fulltext=True, returns markdown (or LLM summary if prompt provided)."""
    api_id = to_openalex_api_format(work_id)
    work = Works()[api_id]
    
    result = {
        "id": work["id"],
        "doi": work.get("doi"),
        "title": work["title"],
        "publication_year": work.get("publication_year"),
        "type": work.get("type"),
        "is_paratext": work.get("is_paratext"),
        "authorships": work.get("authorships", []),
        "primary_location": work.get("primary_location"),
        "open_access": work.get("open_access")
    }
    
    if include_abstract:
        result["abstract"] = work.get("abstract")
    
    if fulltext:
        if not work.get("open_access", {}).get("is_oa"):
            result["fulltext"] = {"is_open_access": False}
        else:
            result["fulltext"] = await _process_fulltext(work, prompt, ctx)
    
    return result


async def _process_fulltext(work, prompt: str | None, ctx: Context) -> dict | str:
    """Process full-text content. Returns markdown if no prompt, otherwise LLM summary."""
    try:
        # Fetch and convert PDF to markdown
        await ctx.report_progress(30, 100, "Fetching PDF")
        pdf_bytes = work.pdf.get()
        
        await ctx.report_progress(60, 100, "Converting to markdown")
        md = MarkItDown()
        article_text = md.convert_stream(io.BytesIO(pdf_bytes)).text_content
        
        if not prompt:
            await ctx.report_progress(100, 100, "Conversion complete")
            return article_text
        
        # LLM summary
        await ctx.report_progress(70, 100, "Preparing LLM analysis")
        
        content_preview = article_text[:10000]
        if len(article_text) > 10000:
            content_preview += "\n\n[... article truncated for token efficiency ...]"
        
        llm_message = f"""You are analyzing this research article:

# Metadata
- Title: {work['title']}
- Year: {work.get('publication_year')}

# Abstract
{work.get('abstract', 'No abstract available')}

# Full Article
{content_preview}

TASK: {prompt}

Provide a clear, structured response."""
        
        await ctx.report_progress(80, 100, "Requesting LLM analysis")
        sampling_result = await ctx.sample(llm_message, max_tokens=2000)
        await ctx.report_progress(100, 100, "Complete")
        
        return {
            "available": True,
            "format": "llm_summary",
            "prompt": prompt,
            "summary": sampling_result.text
        }
        
    except AttributeError:
        return {"available": False, "reason": "PDF not available"}
    except Exception as e:
        return {"available": False, "reason": f"Processing failed: {str(e)}"}


# AUTHOR SEARCH TOOL
@mcp.tool(annotations={"readOnlyHint": True})
async def search_authors(
    query_string: Annotated[str, Field(min_length=2, max_length=500, description="Author name (Elasticsearch syntax)")],
    affiliation: Annotated[str | None, Field(description="Institution name, ROR, or OpenAlex Institution ID")] = None,
    limit: Annotated[int, Field(ge=1, le=10000, description="Max results (1-10000)")] = 25,
    page: Annotated[int, Field(ge=1, description="Page number for pagination")] = 1,
    min_works_count: Annotated[int | None, Field(ge=0, description="Minimum works count")] = None,
    sort: Annotated[str | None, Field(description="Sort: 'field:direction'")] = None,
    ctx: Context = CurrentContext()
) -> dict:
    """Search author profiles by name, ORCID, or affiliation. Returns metrics (works_count, affiliations)."""
    # Build base query
    query = Authors().search(query_string)

    # Apply filters
    if affiliation:
        query = apply_affiliation_filter(query, affiliation)
    
    if min_works_count is not None:
        query = query.filter(works_count=f">{min_works_count}")
    
    if sort:
        field, _, direction = sort.partition(":")
        query = query.sort(**{field: direction or "desc"})
    
    # Execute query
    results = query.select([
        "id", "display_name", "orcid", "works_count", "last_known_institutions"
    ]).get(page=page, per_page=limit)
    
    return {
        "results": [format_author_result(author) for author in results],
        "count": results.meta.get("count", 0),
        "page": results.meta.get("page", 1),
        "per_page": results.meta.get("per_page", limit)
    }


@mcp.tool(annotations={"readOnlyHint": True})
async def get_author_articles(
    author: Annotated[str, Field(min_length=1, description="Author name or OpenAlex ID")],
    limit: Annotated[int, Field(ge=1, le=200, description="Max results (1-200)")] = 25,
    page: Annotated[int, Field(ge=1, description="Page number for pagination")] = 1,
    sort: Annotated[str | None, Field(description="Sort: 'field:direction'")] = None,
    ctx: Context = CurrentContext()
) -> dict:
    """Get all publications by a specific author."""
    # Resolve author ID
    id_type, normalized = detect_id_type(author)
    if id_type == "openalex_author":
        author_id = normalized
    else:
        author_id = get_first_author_id(author)
        if not author_id:
            raise ToolError("AUTHOR_NOT_FOUND", f"No author found matching: {author}")
    
    # Fetch articles
    works_query = Works().filter(author={"id": author_id})
    if sort:
        field, _, direction = sort.partition(":")
        works_query = works_query.sort(**{field: direction or "desc"})
    
    results = works_query.select([
        "id", "doi", "title", "publication_year", "open_access"
    ]).get(page=page, per_page=limit)
    
    return {
        "results": [format_work_result(work) for work in results],
        "count": results.meta.get("count", 0),
        "page": results.meta.get("page", 1),
        "per_page": results.meta.get("per_page", limit)
    }


# INSTITUTION SEARCH TOOL
@mcp.tool(annotations={"readOnlyHint": True})
async def search_institutions(
    query_string: Annotated[str, Field(min_length=2, max_length=500, description="Institution name (Elasticsearch syntax)")],
    country_code: Annotated[str | None, Field(description="Country code (e.g., 'US', 'FR')")] = None,
    institution_type: Annotated[str | None, Field(description="Type: education, healthcare, company, etc.")] = None,
    limit: Annotated[int, Field(ge=1, le=10000, description="Max results (1-10000)")] = 25,
    page: Annotated[int, Field(ge=1, description="Page number for pagination")] = 1,
    sort: Annotated[str | None, Field(description="Sort: 'field:direction'")] = None,
    ctx: Context = CurrentContext()
) -> dict:
    """Search institutions by name with filters."""
    query = Institutions().search(query_string)
    
    if country_code:
        query = query.filter(country_code=country_code.upper())
    
    if institution_type:
        query = query.filter(type=institution_type)
    
    if sort:
        field, _, direction = sort.partition(":")
        query = query.sort(**{field: direction or "desc"})
    
    results = query.select([
        "id", "ror", "display_name", "country_code", "type", "works_count", "lineage"
    ]).get(page=page, per_page=limit)
    
    return {
        "results": [format_institution_result(inst) for inst in results],
        "count": results.meta.get("count", 0),
        "page": results.meta.get("page", 1),
        "per_page": results.meta.get("per_page", limit)
    }


# FETCH AUTHOR TOOL
@mcp.tool(annotations={"readOnlyHint": True})
async def fetch_author(
    author_id: Annotated[str, Field(min_length=1, description="OpenAlex Author ID or ORCID")],
    ctx: Context = CurrentContext()
) -> dict:
    """Fetch detailed author profile by ID or ORCID."""
    api_id = to_openalex_api_format(author_id)
    author = Authors()[api_id]
    return format_author_result(author)


# FETCH INSTITUTION TOOL
@mcp.tool(annotations={"readOnlyHint": True})
async def fetch_institution(
    institution_id: Annotated[str, Field(min_length=1, description="OpenAlex Institution ID or ROR")],
    ctx: Context = CurrentContext()
) -> dict:
    """Fetch detailed institution profile by ID or ROR."""
    api_id = to_openalex_api_format(institution_id)
    institution = Institutions()[api_id]
    return format_institution_result(institution)


# MAIN
if __name__ == "__main__":
    # Support both stdio and HTTP transport
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()

    if transport == "http":
        host = os.getenv("MCP_HOST", "127.0.0.1")
        port = int(os.getenv("MCP_PORT", "8000"))
        mcp.run(transport="http", host=host, port=port)
    else:
        # STDIO transport
        mcp.run()
