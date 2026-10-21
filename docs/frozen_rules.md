# Frozen rules (2026-10-21)

Every event rule, filter and factor that the nowcast uses. They were set before any test month was scored. Calibration
used **2025 only**: the pass-through fits, the spine-use rule and the 2025 recall audit. Nothing here was changed
because of a 2026 result. After this file is committed, the test months (Jan–Sep 2026) are re-run **from cache only**
(zero new Tavily calls) and are still not scored. Changing anything below after the freeze needs the owner's
agreement, and the change must be recorded here with its date.

Code: `shadow_cpi/evidence.py`, `shadow_cpi/event_rules.py`, `shadow_cpi/spine.py`, `shadow_cpi/budget.py`.
Configuration: `config/items.yaml`, `config/passthrough.json`, `config/budget.json`.

## 1. Event layer: what is searched

| Kind | Languages | CPI item | Scope |
|---|---|---|---|
| milk | English + Hindi | 01.1.4.1.1.01 Milk: liquid | regional |
| lpg | English + Hindi | 04.5.2.2.1.01 LPG cylinder and piped natural gas | national |
| electricity | English + Hindi | 04.5.1.0.2.01 Electricity charges | regional |
| mobile | English | 08.3.4.0.2.01 Telephone charges: mobile | national |
| rail | English | 07.3.1.1.2.01 Rail fare | national |
| medicine | English | 06.1.1.1.1.01 Medicine | national |
| school_fee | English | 10.1.0.2.2.01 Tuition fees (primary) | regional |
| gst | English | (no single item) | national |
| fuel (petrol/diesel) | English | 07.2.2.2.1.01 Petrol | national; used only for months PPAC's Delhi petrol series does not cover (before 15 May 2026) |

Queries, match words and reject words are in `config/items.yaml`.

- **Search:** Tavily `topic="news"`, `search_depth="basic"`, `max_results=8`, Indian (English) or Hindi news domains
  with `include_domains_mode="prefer"`, `mospi.gov.in` excluded.
- **Two windows per query:** the target month, plus the last 10 days of the previous month. Changes are often
  announced before the month they take effect in.
- **Page date:** the date in the page address, else Tavily's `published_date`. Pages with no date are dropped. The
  2025 audit found Tavily gives no `published_date` for these pages, and snippet dates recovered only 2 of 124, so
  this rule was kept.
- **Extract:** the top 6 dated pages inside the window, `query=…`, `chunks_per_source=5`.

## 2. Page filters (in order)

1. **Leak guard:** drop a page with a line stating an official CPI or retail-inflation figure for the target month.
2. **Gatekeeper:** the small model (`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`) answers yes/no to "does the page state
   an Indian price or an announced price change?". **Code backstop:** a page that visibly carries a rupee price
   (₹ / Rs / रुपये next to a number) is never skipped.
3. **Extraction:** the mid model (`nvidia/nemotron-3-super-120b-a12b`) lists events, each citing one numbered line.
   The model never writes the quote.

## 3. Event filters (`judge_event`, in order)

1. **Kind:** the event's text must contain one of the kind's match words and none of its reject words (for example,
   commercial cylinders and jet fuel are not LPG).
2. **India only:** the line, region or page address must not point outside India (country, city or site lists in
   `evidence.py`; mentions of dollars do not count).
3. **Verified number:** one of the claimed numbers (new price, old price, % change) must appear in the cited line.
   *2025 audit:* failing that, an amount written in the line with a direction ("hike … by Rs 50", "2 रुपये …
   इजाफा") counts. A line with no hike or cut word, or with both, is not usable.
4. **Effective date:** must be readable. *2025 audit:* dates in words are read using the page's date: "April 8" →
   the page's year; "today"/"आज" → the page date; a weekday → its next occurrence.
5. **Applied by effective date only:** the effective date must be inside the target month. The share of the month
   is (days from the effective date to month end) ÷ days in the month.
6. **The change** comes from old and new prices, else the % change, else (*2025 audit*) the amount ÷ an official base
   price from the day or month before: IOCL domestic LPG (4-metro mean), or DoCA milk (all-India simple mean of
   zones, previous month). Otherwise the event is dropped as "change not computable". This is why GST cuts are not
   applied: they have no single number.

## 4. Event rules (`event_rules.py`)

- **National kinds** (lpg, fuel, rail, mobile, medicine, gst) apply to all of India with weight 1, whatever city a
  page quotes.
- **Regional kinds** (milk, electricity, school_fee) apply to the state(s) found in the model's region field, then
  the seller (e.g. UPPCL → Uttar Pradesh), then the cited line. Cities map to states (Mumbai → Maharashtra).
  *2025 audit:* a regional event counts as national only if the cited **line** says nationwide or across the
  country (देशभर …). The word "India" in the region field alone does not make it national. With no state found, the
  event is not applied.
- **Regional weight** = the state's share of that CPI item, from MoSPI's official 2024-series item weights by state
  (Expert Group report, Annex 5.3d, rural + urban). Several states: shares are added. Applied change = change ×
  share of the month × weight.
- **Duplicates:** (i) *2025 audit:* events extracted from the same cited line are one event, at the mean change
  (a range such as "दो से तीन रुपये"). (ii) Events of the same kind, effective date and scope, with % changes within
  0.5 percentage points, are one event; their sources are pooled.

## 5. Quote filters (`judge_quote`, in order)

Verified number in the line → item named in the cited line → outside India → line about another month → wholesale
(unit quintal/tonne, or wholesale words without retail words) → CPI variety (LPG: 14.2 kg / domestic; not
commercial or 19 kg) → table rows use the last price cell (retail) → price ranges use the midpoint ("from X to Y" is a
change, not a range) → unit convertible → sanity range (`config/items.yaml`) → dated inside the month. Syndicated
copies are counted once. A month-on-month change from quotes needs at least 3 matched cities (same city last
month, else the spine price for that city).

Replay months (Jan–Sep 2026) quote only LPG and petrol. Live months (Oct, Nov 2026) quote all tracked items.

## 6. Observed series and pass-through factors (fitted on Feb–Dec 2025 only)

Factor = least-squares slope through the origin of MoSPI's item month-on-month change on the observed change.

| Item | Observed from | Factor | Months | Fit R² | Used |
|---|---|---|---|---|---|
| Gold | IBJA daily PM rates (≥ 5 trading days a month) | 0.494 | 8 | – | yes |
| Silver | IBJA daily PM rates (≥ 5 trading days a month) | 0.676 | 8 | – | yes |
| LPG | IOCL domestic 14.2 kg, 4-metro mean, day-weighted | 0.491 | 11 | – | yes |
| Petrol | PPAC Delhi (from 15 May 2026); fuel events before that | 1.0 (fixed: no 2025 movement to fit) | 0 | – | yes |
| Onion | DoCA spine (zones) | 1.201 | 11 | 0.96 | yes |
| Tomato | DoCA spine | 1.068 | 11 | 0.96 | yes |
| Potato | DoCA spine | 1.136 | 11 | 0.95 | yes |
| Tur dal | DoCA spine | 1.019 | 11 | 0.98 | yes |
| Edible oils | DoCA spine, 6 packed oils pooled | 1.831 | 11 | 0.71 | yes |
| Rice | DoCA spine | −0.188 | 11 | 0.03 | **no: carried on trend** |
| Atta | DoCA spine | 0.996 | 11 | 0.75 | yes |
| Milk | DoCA spine | 0.748 | 11 | 0.52 | yes |
| Eggs | DoCA spine | 1.329 | 11 | 0.92 | yes |

**Spine-use rule (2025):** a food uses the spine only if its 2025 factor is above 0 and its R² (through the origin)
is at least 0.5.

**Spine details:** DoCA zone-wise monthly average retail prices (5 zones), Dec 2024 – Oct 2026. The item change is
the geometric mean over zones present in both months. The all-India rows are a simple mean of the zones and are not
used in changes.

## 7. Baselines (from Prompt 1)

- **B1:** last month's year-on-year rate.
- **B2:** each group follows its own trend (3-month average month-on-month change + 0.5 × the seasonal deviation),
  aggregated as levels with the official weights.

## 8. Credit caps

Hard limits in `config/budget.json`, enforced in `shadow_cpi/budget.py` before every uncached Tavily call. The
re-run after this freeze uses **cache-only** mode: a call that is not cached is skipped and recorded, never sent.

## 9. 2025 recall audit (the evidence for the *2025 audit* rules above)

- **Reference list:** 4 announcements, each with a dated source, listed in `tools/recall_audit.py`.
- **Recall before the rules:** 0 of 4.
- **Recall after:** 3 of 4.
- **Remaining miss:** the GST rate cuts of 22 Sep 2025. They have no single price change, so this miss is structural.
- **Files:** `results/recall_audit/`.

## Amendment 1 (before any scoring)

**Date:** 2026-10-21. **Commit:** see the line at the end of this section.

**Why:** the frozen re-run (cache-only) showed events that break scope rules already written down before any test
data was seen:
- CLAUDE.md / PROMPTS.md track **domestic** LPG (14.2 kg) and **retail** consumer prices;
- §3.1 of this file rejects commercial cylinders;
- §5 makes quotes retail only.

These fixes enforce those rules as **general rules for every kind and month**: no month-specific patch, no factor or
parameter change, nothing tuned on a 2026 result. **No test month has been scored.**

| # | Rule (general) | Reason (scope rule already written down) |
|---|---|---|
| a | The event layer no longer produces **LPG** events (`config/items.yaml`: lpg `disabled`). LPG comes only from IOCL's official domestic 14.2 kg price list (observed series). A month IOCL's list does not cover is recorded as a **gap**, with no fallback to events. | The CPI item is domestic LPG; the official list is exact. News LPG events mixed in commercial and 5 kg cylinders and would double-count the IOCL series. |
| b | **Non-domestic variants are rejected for every kind**, in English and Hindi: commercial, 19 kg, 5 kg / FTL / free trade, bulk, industrial, non-domestic, वाणिज्यिक, व्यावसायिक, कमर्शियल, कॉमर्शियल, औद्योगिक. Applied to the event's subject, and to its line unless the line also names the domestic/household variant. | §3.1 already rejected commercial cylinders, but only in English and only in the event's subject (`event_rules.non_consumer_reason`). |
| c | **Penalties, fines and charges for violations are not prices** (penalty, fine, ticketless, without a ticket, violation, जुर्माना, दंड, पेनल्टी). Only fares and tariffs paid by ordinary consumers count. A tariff surcharge on all bills, such as a fuel-cost surcharge, is still a tariff. | The CPI prices what ordinary households pay. |
| d | **Events are retail only:** a line saying wholesale, mandi, dealer or bulk rate (also थोक, मंडी, डीलर) is dropped. (Quotes keep §5's rule: wholesale words without retail words, so a line giving both a wholesale and a retail price keeps the retail one.) | §5 and PROMPTS.md: retail prices only. |
| e | **Duplicates:** the same kind and scope (cities mapped to states), % changes within 0.5 pp, and effective dates **within 15 days** are one event, using the **earliest** effective date. Two items more than 15 days apart stay separate. | §4 already merged duplicates, but only with identical effective dates. |

**Re-check on 2025 (cache-only, 0 credits):** recall stays **3 of 4**.
- R1, the LPG hike of 8 Apr 2025, is now found through IOCL's official revision dated 2025-04-08.
- **Lost:** one event, the news-layer LPG hike of 8 Apr 2025, by rule (a). It is replaced by the IOCL series.
- **Gained:** none. All other 2025 events are unchanged. Files: `results/recall_audit/amend1_*`.

**Commit:** `6faa66b` (Amendment 1 code, config, tests and this section).

**Amendment 1 bug fix (2026-10-21, before any scoring):** rule (e) ran before the same-line merge (§4 (i)). An event
whose same-line group was averaged afterwards was never compared with its twins (e.g. one notification listing
three milk types next to another report of the same hike). The two steps now run in order: same-line merge first,
then rule (e). This is how the written rules read, so no rule changed. 2025 re-check: recall 3 of 4, no event
gained or lost (`results/recall_audit/amend1b_*`).
