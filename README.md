# mcp-openalex

MCP server for the [OpenAlex](https://openalex.org) scholarly database. Gives AI agents tools to search and retrieve academic articles, authors, and institutions.

## Requirements

- Python >= 3.12
- [uv](https://docs.astral.sh/uv/)
- OpenAlex API key ([get one for free](https://docs.openalex.org/))

## Installation

```bash
git clone https://github.com/ELumya/openalex-mcp.git
cd openalex-mcp
uv sync
```

## Configuration

Copy the example env file and set your API key:

```bash
cp .env.example .env
# edit .env and set OPENALEX_API_KEY=your-key-here
```

## Running

**STDIO (default — for local MCP clients):**

```bash
uv run python src/server.py
```

**HTTP transport:**

```bash
MCP_TRANSPORT=http MCP_HOST=127.0.0.1 MCP_PORT=8000 uv run python src/server.py
```

For LiteLLM proxy integration, see [`litellm-config.example.yaml`](litellm-config.example.yaml).

## MCP Tools

| Tool | Description |
|------|-------------|
| `search_articles` | Search articles with filters (institution, year, date range, type, peer-reviewed) |
| `fetch_article` | Fetch full article metadata by OpenAlex ID or DOI — optionally extract PDF or request an LLM summary |
| `search_authors` | Search author profiles by name or ORCID |
| `fetch_author` | Fetch full author profile by OpenAlex ID or ORCID |
| `get_author_articles` | List all publications by a specific author |
| `search_institutions` | Search institutions by name, country, or type |
| `fetch_institution` | Fetch full institution profile by OpenAlex ID or ROR |

All fetch tools accept multiple ID formats (OpenAlex IDs, DOIs, ORCIDs, ROR IDs) and automatically detect the format.

## License

[MIT](LICENSE)
