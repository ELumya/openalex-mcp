# Architecture

## System Overview

`mcp-openalex` is a FastMCP server that exposes OpenAlex data as structured, agent-friendly tools.
It supports two MCP transports (`stdio` and `http`), validates and normalizes identifiers,
builds OpenAlex queries, and optionally enriches article retrieval with PDF-to-markdown conversion
or LLM post-processing.

### Architecture at a Glance

```mermaid
flowchart TD
    subgraph Client["MCP Client"]
        Agent["AI Agent / MCP Host"]
    end

    subgraph Runtime["mcp-openalex (FastMCP Runtime)"]
        Entry["src/server.py\nTransport + Tool Registration"]
        MW["Middleware\nErrorHandling + Retry"]

        subgraph APIs["Tool Surface"]
            TW["search_works / fetch_work"]
            TA["search_authors / fetch_author / get_author_works"]
            TI["search_institutions / fetch_institution"]
        end

        subgraph Domain["Domain Helpers (src/utils)"]
            NORM["normalizers.py\nID parsing + canonical IDs"]
            FILT["filters.py\nquery builders + output formatting"]
            RES["resolver.py\nname to ID disambiguation"]
        end

        subgraph Integrations["Optional Content Processing"]
            MD["MarkItDown\nPDF to markdown"]
            Sample["ctx.sample()\nLLM summarization"]
        end
    end

    subgraph OpenAlex["External Services"]
        API[(api.openalex.org)]
        Content[(content.openalex.org)]
    end

    Agent -->|"MCP (stdio or HTTP)"| Entry
    Entry --> MW
    MW --> APIs

    APIs --> NORM
    APIs --> FILT
    FILT --> RES
    RES --> NORM

    APIs -->|"pyalex"| API
    TW -->|"open-access full text"| Content
    Content --> MD
    MD --> Sample
    Sample -.->|"summary response"| Agent
```

### Request Lifecycle

```mermaid
sequenceDiagram
    participant Client as MCP Client
    participant FastMCP as server.py
    participant Utils as utils/*
    participant OpenAlex as OpenAlex APIs
    participant Optional as PDF + LLM path

    Client->>FastMCP: Tool call (e.g. search_works / fetch_work)
    FastMCP->>FastMCP: Validate params + apply middleware
    FastMCP->>Utils: Normalize IDs, build filters, resolve names
    Utils->>OpenAlex: Execute pyalex request
    OpenAlex-->>FastMCP: Metadata payload

    alt fulltext processing requested
        FastMCP->>Optional: Download OA PDF + convert to markdown
        opt prompt provided
            Optional-->>FastMCP: LLM summary via ctx.sample()
        end
    end

    FastMCP-->>Client: Structured JSON result for agent use
```

### Design Characteristics

- **Transport-flexible:** same codebase runs as local `stdio` MCP server or networked `http` server.
- **Agent-centric outputs:** tools return compact, structured dictionaries tailored for LLM consumption.
- **Resilient calls:** middleware and pyalex retries reduce failures on transient OpenAlex/API issues.
- **Progressive enrichment:** expensive operations (PDF extraction, LLM summarization) are only triggered when requested.
- **Separation of concerns:** `server.py` orchestrates tools; `utils/` handles normalization, filtering, and disambiguation.

## Module Dependencies

```mermaid
flowchart LR
    server["src/server.py"]
    filters["utils/filters.py"]
    norm["utils/normalizers.py"]
    resolver["utils/resolver.py"]

    server --> norm
    server --> filters
    filters --> norm
    filters --> resolver
    resolver --> norm
```

## search_works Flow

```mermaid
sequenceDiagram
    actor User as User
    participant Agent as AI Agent
    participant MCP as server.py (FastMCP)
    participant Filters as filters.py
    participant Norm as normalizers.py
    participant Res as resolver.py
    participant OA as api.openalex.org

    User->>Agent: request mentioning an institution by name
    Agent->>MCP: search_works(query, institution, ...)
    MCP->>Filters: build_works_query(...)

    opt institution filter provided
        Filters->>Norm: normalize_id(institution)
        alt ID not recognized (free-text name)
            Norm-->>Filters: None
            Filters->>Res: resolve_institution_id(name, ctx)
            Res->>OA: Institutions().search(name)
            OA-->>Res: candidates
            opt multiple matches
                Res->>MCP: ctx.elicit(pick one)
                MCP-->>User: elicitation prompt (via MCP client)
                User-->>MCP: selected institution
                MCP-->>Res: user selection
            end
            Res-->>Filters: OpenAlex I-ID
        end
        Filters->>Filters: query.filter(authorships.institutions)
    end

    Filters-->>MCP: configured Works query
    MCP->>OA: query.get(page, per_page)
    OA-->>MCP: results + meta
    MCP-->>Agent: {results, count, page, per_page}
```

## fetch_work with Full-Text Flow

```mermaid
sequenceDiagram
    actor User as User
    participant Agent as AI Agent
    participant MCP as server.py (FastMCP)
    participant Norm as normalizers.py
    participant OA as api.openalex.org
    participant PDF as content.openalex.org
    participant MD as MarkItDown

    User->>Agent: request
    Agent->>MCP: fetch_work(work_id, fulltext=True, prompt?)
    MCP->>Norm: normalize_id(work_id)
    Norm-->>MCP: canonical ID (W…, doi:…, pmid:…)
    MCP->>OA: Works()[api_id]
    OA-->>MCP: work metadata

    alt fulltext=True and work is open-access
        MCP->>PDF: work.pdf.get()
        PDF-->>MCP: PDF bytes
        MCP->>MD: convert_stream(pdf_bytes)
        MD-->>MCP: markdown text

        alt prompt provided
            MCP->>MCP: build LLM prompt (metadata + text + task)
            MCP->>Agent: ctx.sample(prompt)
            Agent-->>MCP: LLM summary text
            MCP-->>Agent: {format: llm_summary, summary: ...}
        else no prompt
            MCP-->>Agent: markdown work text
        end
    else not open-access
        MCP-->>Agent: {is_open_access: false}
    end
```
