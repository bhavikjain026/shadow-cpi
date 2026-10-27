# Shadow CPI pipeline

Who does what:
- **Tavily** brings in every piece of web data. Logged direct downloads are a counted fallback.
- **Nemotron** (on Nebius Token Factory) only *extracts* facts and cites a numbered line: Nano 30B as a yes/no gatekeeper, Super 120B for quotes and price changes.
- **Plain code** decides everything else: the model returns a line number, code copies that line from the Extract output and checks the number is in it; code matches prices, does all the arithmetic, and seals the result.

```mermaid
flowchart TD
    subgraph SRC["Where data comes from"]
        MOSPI["MoSPI official CPI indices + 2024-series weights"]
        GOV["Government daily retail prices<br/>(Consumer Affairs, 38 foods)"]
        NEWS["Indian news, English + Hindi"]
        IBJA["Published gold / silver rate page<br/>(e.g. IBJA)"]
        OFF["Official sites: state electricity regulators,<br/>oil company, dairy co-op"]
    end

    subgraph TAV["Tavily: the only way web data enters"]
        T_SEARCH["Tavily Search<br/>topic=news, date window = the month,<br/>Indian / Hindi news domains preferred"]
        T_EXTRACT["Tavily Extract<br/>top pages, query-focused chunks"]
        T_MAPCRAWL["Tavily Map + Crawl<br/>'find price circulars or tariff orders<br/>published in &lt;month&gt;'"]
        T_EVENTS["Event layer = Search + Extract<br/>milk, electricity, mobile, rail, medicine,<br/>school fees, GST, fuel (LPG: IOCL list only)"]
        T_GOLD["Gold / silver OBSERVED<br/>Search finds the rate page, Extract reads it"]
        T_CHASE["Evidence chasing<br/>up to 2 follow-up searches per verified event"]
    end

    DIRECT["Logged direct download<br/>(fallback, counted in the report card)"]

    subgraph NEM["Nemotron: extracts only"]
        N_GATE["Small model: gatekeeper<br/>'does this page state an Indian price<br/>or an announced price change?'"]
        N_EXTRACT["Mid model: price quotes + price events<br/>cites a numbered line, never writes a quote"]
    end

    subgraph CODE["Plain code decides"]
        C_VERIFY["Verify: take the exact cited line,<br/>check the number is in it"]
        C_DATES["Dates + leak guard: drop pages outside the month<br/>or stating the official CPI for it"]
        C_MATCH["Event rules: retail only, CPI variety,<br/>national vs regional, one event per kind x state x month"]
        C_MATH["CPI maths: carve-out by item weight,<br/>combine index LEVELS with 2024 weights,<br/>YoY last, full precision"]
        C_RANGE["Range from replay misses (80%)<br/>+ skeptic counter-search"]
        C_SEAL["Seal: canonical JSON + SHA-256 + git tag"]
    end

    MOSPI --> DIRECT
    GOV --> DIRECT
    GOV -. "Tavily tried first" .-> T_EXTRACT
    NEWS --> T_SEARCH --> T_EXTRACT
    NEWS --> T_EVENTS
    IBJA --> T_GOLD
    OFF --> T_MAPCRAWL

    T_EXTRACT --> N_GATE
    T_EVENTS --> N_GATE
    T_GOLD --> N_GATE
    T_MAPCRAWL -. "reported only (found nothing usable)" .-> REPORT["Tavily report card"]
    N_GATE -- "yes" --> N_EXTRACT
    N_EXTRACT --> C_VERIFY
    C_VERIFY -- "verified event" --> T_CHASE --> N_GATE
    C_VERIFY --> C_DATES --> C_MATCH --> C_MATH
    DIRECT --> C_MATH
    C_MATH --> C_RANGE --> C_SEAL
    C_SEAL --> BRIEF["Reporter brief, written by code<br/>from computed numbers + verified quotes"]
    C_SEAL --> APP["App: Home, Evidence, Replay,<br/>Flight Recorder, Archive"]

    REC[("Recorder: cache + flight recorder<br/>logs/flight_recorder.jsonl")]
    TAV -.-> REC
    NEM -.-> REC
    DIRECT -.-> REC
```

## Which Tavily endpoint does which job

| Job | Tavily endpoint | Notes |
| --- | --- | --- |
| Price quotes (March 2026 test; other replay months skip them to save credits) | **Search** (`topic="news"`, `search_depth="basic"`, `max_results=8`, start/end = the month, Indian/Hindi news domains with `include_domains_mode="prefer"`, `mospi.gov.in` excluded) then **Extract** (top 6, `query=…`, `chunks_per_source=5`) | English + Hindi (Devanagari) queries |
| Event layer: announced price changes with effective dates | **Search** + **Extract**; page dates from the last 10 days of the previous month through the month | Applied only if the effective date is inside the month, pro-rated by days. Milk and electricity in English + Hindi; other kinds English only; no LPG events since Amendment 1 (LPG comes from IOCL's list) |
| Gold and silver, observed daily | **Extract** reads IBJA's daily bullion-report PDFs (each lists 4 trading days) | Never left on trend |
| LPG and petrol, observed | **Extract** reads IOCL's domestic LPG price list and PPAC's Delhi petrol prices | Petrol history found only from mid-May 2026 |
| Official circulars and tariff orders (attempted) | **Map** then **Crawl** (`instructions=…`, `select_paths`, `extract_depth="basic"`, `limit` ≤ 15, `allow_external=False`) | 5 official sites and 6 dairy sites tried for October 2026; Map returned nothing on the government and PSU sites, so results are reported in `results/tavily_report_card.md`, not used |
| Evidence chasing | **Search** (≤ 2 follow-ups per verified event) | Report only: 5 of 12 replay events had a confirming result from another site (`results/tavily_report_card.md`) |
| Government daily retail prices (spine) | none: downloaded by hand from behind a CAPTCHA | The site blocks Tavily and its report menu has a CAPTCHA (see honest_limits.md) |
| Economists' poll articles | **Search** | Dated original article only |
| MoSPI official indices | none: logged direct download from MoSPI's public API | A paged JSON API Tavily cannot call |

Every call, from Tavily, Nebius or a direct download, goes through the Recorder. The Recorder caches each response and logs one line with the time, parameters, results, credits, latency and parent call.
