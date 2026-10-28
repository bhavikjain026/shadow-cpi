# Shadow CPI demo: 2:45, about 375 words at 130-140 wpm
Screen recordings only; no slides.

| Time | On screen | Voice-over | On-screen text |
|---|---|---|---|
| 0:00-0:15 | Leak demo, the F3 petrol tab (saved results) | "Can a search engine keep the past in the past? We asked about a petrol price hike as of the end of May. Without dates, a top result came from September and gave later prices away. With the time lock, Tavily's date filters, every result was from before the cutoff." | The "LEAK +115d" badge on the left, "OK" on the right |
| 0:15-0:35 | The leak demo summary bar, then the Field Report leak table | "If you test an AI agent on past data, this is your problem. So we pre-registered a test: twenty past price changes. With no dates, nine of twenty searches met our confirmed-leak rule; ten after we retried eleven archive lookups that had failed. With Tavily's dates plus the published-date filter: zero detected of twenty, and on twenty-two new cases, pre-registered, zero detected again. The measured cost of that strict setting, on the initial pass: the filter dropped twelve of forty pieces of valid evidence." | "9/20 → 0/20 detected, pre-registered (95%: 26-66% → 0-16%)" · "Update: 10/20 after retrying 11 failed archive lookups" · "Measured cost of strict mode: 12/40 valid evidence dropped (initial pass)" · small: "confirmed-leak rule: see README" |
| 0:35-0:55 | Field Report: the R196 TCS example | "But date filters select which pages, not which version. This preview was published before TCS's results, then updated with the actual numbers. The filter did what Tavily documents; Extract reads the page as it is today, and max age hours controls freshness, not as-of. Our extract-as-of reads the archived copy instead: one demo, not a measurement." | "Date filters select which pages, not which version · extract_as_of (demo, n=1)" |
| 0:55-1:20 | Field Report: the four-arm table | "Should the model write its own search filters? Nemotron wrote valid Tavily fields every time, but fixed templates found three times as many real price changes, six versus two of twenty-nine. That is about how Nemotron planned the queries, not about Tavily. And auto-parameters, with no dates, reached for the present: observed once, on 22 October, six hundred twenty of six hundred fifty-nine results came from October; not reproduced on 27 October. So the model may choose words and sources; code owns the dates." | "Valid fields 189/189 · Templates 6 vs 2 of 29 (query planning, not Tavily) · auto_parameters, 22 Oct: 620/659 from Oct (observed once on 22 Oct 2026, not reproduced on 27 Oct 2026)" |
| 1:20-1:50 | Terminal: tools/demo_live.py running live (endpoint host and model IDs visible, never keys), then the October forecast metrics row | "Here it is end to end, live: Tavily finds a dated price, Nemotron Nano on Nebius Token Factory screens the page, Nemotron Super cites the exact line, and plain code checks the number. Replaying January to September with rules frozen in advance, we missed by 0.194 points, better than trend at 0.212, and about level with economists' polls." | "Live: Tavily → Nemotron Nano → Super (Nebius Token Factory)" · "0.194 vs trend 0.212 · poll months: 0.150 vs 0.148" |
| 1:50-2:05 | October forecast: the seal banner and "How to check the seal yourself" | "October's estimate is sealed on the twenty-ninth: we publish its SHA-256 and a Git tag before the twelfth of November release, so anyone can check when it was committed; the time lock is what guards the evidence." | "Sealed 29 Oct · scheduled release 12 Nov, 4 pm IST" |
| 2:05-2:15 | README: the `timelocked_search` example, then the `extract_as_of` example, then the "Open in Colab" badge (hover it) | "Take the time lock, the as-of reader, or run our leak check with your own Tavily key." | "timelocked_search · extract_as_of · Open in Colab" |
| 2:15-2:30 | README: mcp/ and the benchmark, then docs/tavily_bug_reports.md | "Both come as an MCP tool for any agent, with TimeLock-34: thirty-four labelled replay cases to test a search setup for leaks. Our notes for Tavily's team are a field-notes repro kit: each tagged documented behaviour, doc gap or unexplained, with request IDs." | "MCP tool · TimeLock-34 (34 cases, 32 questions)" |
| 2:30-2:45 | Leak demo again, then the app URL | "Search can filter the past. Pages keep changing. Shadow CPI measures the gap, and seals its forecast before the answer exists." | "shadow-cpi.streamlit.app · github.com/bhavikjain026/shadow-cpi" |

## Recording notes
- Browser zoom 125-150%; pre-load tabs in shot order; record each shot
separately and cut on the voice-over; 0.5 s of silence between shots.
- Only shot 5 is live: run on Bhavik's Mac with the keys in .env, never
on screen; up to 10 Tavily credits. Run it as
`python tools/demo_live.py --live --fresh`, so every call is sent live; the
terminal must show "(live)", never "(from cache)". It must be recorded BEFORE 9 Nov
(the original Nemotron IDs are retired then). Hide terminal history and
any .env window.
- Shots 5 and 6 are recorded after the 29 Oct seal, so the banner shows
the real hash.
- If the total runs past 2:50, shorten shot 5 first, then shot 4.
- Upload to YouTube (public or unlisted), add English captions, check the
model names in the captions by hand, and test the link signed out.
