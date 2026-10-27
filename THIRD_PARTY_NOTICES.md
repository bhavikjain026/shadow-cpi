# Third-party notices

Shadow CPI's own code is under the MIT licence ([`LICENSE`](LICENSE)); the timelock34 labels are under CC BY 4.0
([`benchmarks/timelock34/DATASHEET.md`](benchmarks/timelock34/DATASHEET.md)). This file lists what we use from others.

## Libraries

The pipeline (`shadow_cpi/`, `v2/`, `timelock/`) uses only the Python standard library (Python Software Foundation
License). Packages installed from `requirements.txt`, `requirements-app.txt` and `mcp/requirements.txt`:

| Package | Used for | Licence |
|---|---|---|
| Streamlit | the app (`app.py`, `app_pages/`) | Apache License 2.0 |
| pandas | tables in the app | BSD 3-Clause |
| Altair | charts in the app | BSD 3-Clause |
| pytest | tests (not shipped in the app) | MIT |
| mcp (Model Context Protocol Python SDK) | the MCP server in `mcp/` only | MIT |

Their own dependencies (for example NumPy, BSD 3-Clause) come with their own licence files. Licences as stated by
each project; pandas and pytest were checked against the installed package metadata, the others against the
projects' published licence.

Loaded by the viewer's browser, not installed or vendored (no build step):

| Asset | Used for | Licence | Served from |
|---|---|---|---|
| anime.js 4.5.0 (Julian Garnier) | the Leak demo headline count, the app's only JavaScript animation (`app_pages/leak_demo.py`) | MIT | cdnjs, exact version with its SRI hash |
| Inter (Rasmus Andersson) | interface text (`.streamlit/config.toml`) | SIL Open Font License 1.1 | Google Fonts |
| JetBrains Mono (JetBrains) | numbers and code (`.streamlit/config.toml`, `app_pages/style.css`) | SIL Open Font License 1.1 | Google Fonts |

## Services

- **Tavily API** (Search, Extract, Map, Crawl): web search and page reading, under Tavily's terms of service.
- **Nebius Token Factory**, serving **NVIDIA Nemotron** models (Nemotron Nano, Nemotron Super), under Nebius's terms
  and the NVIDIA model licences.

## Data sources

| Source | What we use | How it is fetched |
|---|---|---|
| Ministry of Statistics and Programme Implementation (MoSPI) | official CPI indices, item weights (2024 series) and press releases | MoSPI API, a logged direct download; press releases through Tavily Extract |
| Department of Consumer Affairs (DoCA) | daily retail food prices | downloaded by hand (the report menu has a CAPTCHA) and logged |
| India Bullion and Jewellers Association (IBJA) | daily gold and silver rates | bullion-report PDFs read with Tavily Extract |
| Indian Oil Corporation (IOCL) | LPG and fuel price lists | Tavily Extract |
| Petroleum Planning and Analysis Cell (PPAC) | fuel price data | Tavily Extract |
| The Wayback Machine (Internet Archive) | capture dates, to check whether a page existed by a cutoff (CDX API) | logged direct lookups |
| News sites | short quoted excerpts about announced price changes and results | Tavily Search and Extract |

Government data is used as published, for research; each source keeps its own terms.

## Quotes

Quotes from news and other web pages are short excerpts, each attributed to its page with a link (and, where
logged, the Tavily request ID). They identify the evidence; they are not republished articles. The timelock34
benchmark keeps at most 25 words per page, and the post-hoc AI-assisted review's quotes at most 14 words. Page texts
saved at fetch time stay local and are not committed (`v2/evidence/pages/` is git-ignored); the ledger keeps each
page's SHA-256. URLs, titles and quotes belong to their publishers.
