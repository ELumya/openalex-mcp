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
uv run fastmcp run src/server.py
```

**HTTP transport:**

```bash
MCP_TRANSPORT=http MCP_HOST=127.0.0.1 MCP_PORT=8000 uv run fastmcp run src/server.py
```

## MCP Tools

| Tool | Description |
| ------ | ------------- |
| `search_articles` | Search articles with filters (institution, year, date range, type, peer-reviewed) |
| `fetch_article` | Fetch full article metadata by OpenAlex ID or DOI — optionally extract PDF or request an LLM summary |
| `search_authors` | Search author profiles by name or ORCID |
| `fetch_author` | Fetch full author profile by OpenAlex ID or ORCID |
| `get_author_articles` | List all publications by a specific author |
| `search_institutions` | Search institutions by name, country, or type |
| `fetch_institution` | Fetch full institution profile by OpenAlex ID or ROR |

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for system overview, module dependency graph, and tool flow diagrams.

## TODOs

- [ ] Add tests
- [ ] Add CI/CD
- [ ] Use cache for high rate requests
- [x] Scan code base for dead code
- [x] Add mermaid documentation
- [ ] Unify concepts names (ie. Articles/Works)
- [x] Two levels of formating details in `filter`: low (current one), medium (for `fetch_*` tools)

### Tools Evolutions

- [x] Test OpenAlex support of Elasticsearch: YES!
- [x] Update work search tools descriptions, add: "Elasticsearch syntax"
- [x] Update tools descriptions, do not explain how it works but what you need to pass.
- [x] Update Author search tool, remove IDs handling (use `fetch_author` for this)

in [format_work_result](C:\Users\Lumya\Documents\Travail\CEA - alternace\Projet\mcp-openalex\src\utils\filters.py:163) add:  

- [x] first 3 Authors
- [x] Primary topic classification

in [_process_fulltext](C:\Users\Lumya\Documents\Travail\CEA - alternace\Projet\mcp-openalex\src\server.py:174) in `fetch_article`

- [x] Remove pure PDF handling, auto-detect format based on prompt presence (if prompt provided → LLM summary, else → markdown)
- [ ] Use proper sampling parameters (deferred)

### Search

- [ ] Search by topics
- [ ] Search foundational works

### Citation

- [ ] graph_work_citations

### Authors

- [x] get_author_articles: parameter `author` replaced by `author_id`; accepts only OpenAlex ID or ORCID.
- [ ] graph_collaborations

### Institutions

- [ ] graph_colaborations

### Global analysis tools

- [ ] OpenAlex Topic comparaison
- [ ] Geographical Region comparaison
- [ ] Institutions comparaison
- [ ] Trend deep analysis

## License

[MIT](LICENSE)
