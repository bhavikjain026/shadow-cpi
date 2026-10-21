# Shadow CPI

**An experimental, sealed nowcast of India's next official CPI inflation number** — made before MoSPI releases it, with a source behind every input, locked in public, and scored when the real number comes out.

> MoSPI sends price collectors to 2,860 markets. Shadow CPI sends Tavily to the web.
> Token Factory reasons. Tavily knows.

- **Tavily** is the single entry point for web data: government daily retail price tables (Extract), announced price changes with effective dates in English and Hindi news (Search), official circulars (Map + Crawl).
- **NVIDIA Nemotron on Nebius Token Factory** only *extracts* facts and exact quotes.
- **Plain code decides**: it verifies every quote word-for-word, combines index levels with official 2024-series weights, and computes inflation.

Status: foundation (day 1). Built for the Nebius x NVIDIA Global AI Hackathon, 2026.

## Quick start (no coding needed)

1. Install Python 3.10 or newer.
2. In this folder, run: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and paste your keys after the `=` signs (Tavily key from tavily.com or the Nebius Builder Program; Nebius Token Factory key).
4. Run the day-1 checks: `python checks.py`
5. Copy the report it prints (everything below "COPY EVERYTHING BELOW") back to Claude.

Or open this folder in Claude Code and say: *"Run python checks.py and show me the report."*

To run the offline tests (no keys, no credits): `python -m pytest -q`

## What's here

| File | What it does |
| --- | --- |
| `checks.py` | Day-1 checks: keys, Nemotron models and JSON mode, Tavily on government price tables and a MoSPI PDF, date-windowed news search (English, Hindi, strict date filter), milk-price event search, quote extraction + word-for-word check, credits used |
| `shadow_cpi/tavily.py` | Tavily client (Search, Extract, Map, Crawl) with credit usage, caching and failed-result handling |
| `shadow_cpi/nemotron.py` | Nemotron client with JSON-schema output (and fallback), price-quote and price-event extractors |
| `shadow_cpi/recorder.py` | Cache + **Flight Recorder** (`logs/flight_recorder.jsonl`): every outside call with time, parameters, results, credits, latency |
| `shadow_cpi/verify.py` | Word-for-word quote check (English + Hindi), unit conversion, date and duplicate checks, matched-price change |
| `shadow_cpi/cpi_math.py` | Level-based aggregation, item carve-out, year-on-year, contributions, coverage, baselines |
| `shadow_cpi/seal.py` | Sealed predictions: canonical JSON + SHA-256 |

## Honest limits
- This is an experimental nowcast, not a reconstruction of MoSPI's 358-item survey; the app shows how much of the basket is measured vs carried on trend.
- Replays of past months search today's web with date filters; Tavily's published date is a best estimate, so the code also checks dates written inside pages and reports what it drops.

## License
MIT
