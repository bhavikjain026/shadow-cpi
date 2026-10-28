Each product answers the organisers' five questions. Only facts already logged in `FEEDBACK_NOTES.md` (dated
entries below) or `results/feedback_evidence/`, plus Nebius's own retirement notice (`config/doc_citations.json`).

**Nebius Token Factory**

- *What we used it for:* the one OpenAI-compatible endpoint (`{{nebius_host}}`) for every model call, through
  `shadow_cpi/nemotron.py`.
- *What worked well:* JSON-schema output worked on the opening call (`checks.py`, "[PASS] Nemotron JSON output"), so
  every answer is parsed, not guessed; the `/models` list served several Nemotron models behind the one endpoint, so
  roles are picked by name in `config/models.json`.
- *What needs work:* one read timeout and one connection reset each stopped a long run (our helper now retries
  timeouts, not resets); the `/models` list mixes naming styles (case, `3.5` vs `3_5`) and puts a vision model next
  to the text models; the Nemotron IDs we use are removed from Serverless on {{switch_day}} (Dedicated Endpoints
  unaffected), so a project that must run through judging has to switch models mid-way, which we pre-registered on
  {{migration_registered}}.
- *Onboarding, zero to hello world:* key in `.env`, any OpenAI-compatible client pointed at the endpoint, `/models`,
  then one chat completion with a JSON schema: that is `checks.py`, and it passed on the opening run. The step that
  took care was choosing model IDs from the `/models` list.
- *Would we build with it again?* Yes: strict schema output and two model sizes behind one endpoint let code, not
  the model, decide every number. We would ask for retries on resets and a longer runway before retirements.

**NVIDIA Nemotron Nano** (`{{nano_id}}`)

- *What we used it for:* the yes/no gatekeeper ("does this page state an Indian price or price change?") and
  display-only English glosses.
- *What worked well:* it answered the opening JSON-schema check in the requested shape.
- *What needs work:* it said "no" to a page that plainly listed rupee prices (a Delhi vegetable-price page); we added
  a code backstop so a page with a visible rupee price is never skipped.
- *Onboarding:* the same `checks.py` call; nothing model-specific to set up.
- *Would we build with it again?* Yes, as a cheap gatekeeper, with the code backstop in place.

**NVIDIA Nemotron Super** (`{{super_id}}`)

- *What we used it for:* reading each page as numbered lines and citing the line for every price and price change;
  writing the search fields in arms B, C and H.
- *What worked well:* citing line numbers instead of copying text made Hindi pages work; the Hindi quotes that failed
  the code check were mostly prices written in words, which code cannot verify as numerals.
- *What needs work:* it sometimes labelled the item from the page's context rather than the cited line, took the low
  end of a price range, or took the old price in "from X to Y" sentences; code now requires the item name in the
  cited line, takes the midpoint of a range and reads "from X to Y" as a change.
- *Onboarding:* the `checks.py` price-extraction check (a numbered line cited, the number checked by code) passed on
  the opening run.
- *Would we build with it again?* Yes: line-number citing is what lets code check every number on the page.

**Tavily** (separate from Nebius and NVIDIA; the field notes are in `docs/tavily_bug_reports.md`)

- *What we used it for:* every web page that enters the system: Search with dates, Extract, Map and Crawl
  (endpoints used: {{tavily_endpoints}}).
- *What worked well:* dated news searches stayed inside the requested month in English and Hindi on the opening
  checks; the date fields held in Hindi, Marathi and Tamil; Extract read the MoSPI press-release PDF and IBJA's daily
  bullion PDFs; Crawl read DERC's tariff-order table; empty Map/Crawl calls were not charged, and a bad start address
  got a clear error.
- *What needs work:* Extract cannot read reuters.com or script-rendered data pages; Map returned nothing on several
  government and dairy sites with no error, and its `limit` cut off the newest pages; `/usage` did not update all
  day; `include_domains_mode="prefer"` let off-target results through; the Research endpoint has no date parameter;
  Extract has no as-of / crawl-timestamp field.
- *Onboarding:* key in `.env`, then the `checks.py` news search for a past month inside a date window, which passed
  on the opening run.
- *Would we build with it again?* Yes: explicit date windows are what kept later articles out of a historical
  search, and the date fields held in every language we tried.
