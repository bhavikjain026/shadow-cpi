# Leak check P: full-page date check (exploratory)

Run 2026-10-26T11:45 UTC by `python -m v2.leakcheck P`, pre-registered in `v2/LEAKCHECK_PREREG.md`. Descriptive only: no scored verdict changes. Every page that passed a date window, its whole text searched for explicit dates after its cutoff. Outcomes of flagged pages were **judged by Claude Code** from the flagged line in context (`results/leakcheck_full_page_labels.json`).

| Source | Pages | With text | Flagged (Wilson 95%) | Later content (Wilson 95%) | Sidebar or related | Benign | Unclear |
|---|---|---|---|---|---|---|---|
| (a) date test arm C | 51 | 47 | 28 (45%–72%) | 0 (0%–8%) | 22 | 6 | 0 |
| (b) finance check arm D | 66 | 65 | 38 (46%–70%) | 1 (0%–8%) | 16 | 15 | 6 |
| (c) v2 replay verified evidence (date window only, no filter_by_published_date) | 20 | 20 | 5 (11%–47%) | 0 (0%–16%) | 5 | 0 | 0 |

Credits: 13 (Extract of pages with no saved text). Pages with no text are left out of the rates and listed in the JSON.

Source (c) is **date window only, no filter_by_published_date**: the v2 replay sent start/end dates but not the filter; its pages passed that window plus the code's own date checks.

A page takes the first outcome any of its flagged lines has: later content > unclear > sidebar or related links > benign. Flagged lines by label: later content 2, unclear 6, sidebar or related links 197, benign 85.

## Later-content pages

- (b) cutoff 2026-02-05: https://groww.in/blog/rbi-repo-rate-remains-unchanged — the article's dateline, 06 February 2026, under the headline 'RBI Repo Rate Remains Unchanged at 5.25%'

## Example flagged lines per outcome (one per page, sources a, b, c in turn; for checking the labels)

**later content** (1 shown)

| Source | Cutoff | Date found | Line (shortened) | Claude Code's reason |
|---|---|---|---|---|
| (b) groww.in | 2026-02-05 | 2026-02-06 | 06 February 2026… | the article's dateline, 06 February 2026, under the headline 'RBI Repo Rate Remains Unchanged at 5.25%' |

**unclear** (5 shown)

| Source | Cutoff | Date found | Line (shortened) | Claude Code's reason |
|---|---|---|---|---|
| (b) www.business-standard.com | 2026-02-05 | 2026-02-06 | 3 min read Last Updated : Feb 06 2026 / 8:12 AMIST… | the article's own published/updated stamp is after the cutoff, but its body only previews the scheduled event; whether the pre-cutoff version differed cannot be told |
| (b) www.business-standard.com | 2026-08-04 | 2026-08-05 | 3 min read Last Updated : Aug 05 2026 / 8:59 AMIST… | the article's own published/updated stamp is after the cutoff, but its body only previews the scheduled event; whether the pre-cutoff version differed cannot be told |
| (b) www.business-standard.com | 2026-07-08 | 2026-07-09 | 5 min read Last Updated : Jul 09 2026 / 7:34 AMIST… | the article's own published/updated stamp is after the cutoff, but its body only previews the scheduled event; whether the pre-cutoff version differed cannot be told |
| (b) www.moneycontrol.com | 2026-07-16 | 2026-07-17 | July 17, 2026 / 09:44 IST… | the article's own published/updated stamp is after the cutoff, but its body only previews the scheduled event; whether the pre-cutoff version differed cannot be told |
| (b) upstox.com | 2026-07-22 | 2026-07-23 | 4 min read / Updated on July 23, 2026, 08:32 IST… | the article's own published/updated stamp is after the cutoff, but its body only previews the scheduled event; whether the pre-cutoff version differed cannot be told |

**sidebar or related links** (5 shown)

| Source | Cutoff | Date found | Line (shortened) | Claude Code's reason |
|---|---|---|---|---|
| (a) www.thehindu.com | 2026-04-29 | 2026-10-20 | [Weather News]October 20, 2026[e-Paper]… | site header date bar showing the day the page was fetched |
| (b) groww.in | 2026-02-05 | 2026-10-27 | [BLS Polymers IPO to Open on October 27, 2026: Check Price Band, Issue Size and Key Details][Sahajanand Medical Technologies IPO Day 3: Subscription Status, Timeline & Key Issue De… | link in a related-stories, navigation or archive list |
| (c) www.aajtak.in | 2026-01-29 | 2026-09-29 | ##### महंगा हो जाएगा रसोई गैस सिलेंडर? अगर नहीं किया ये काम]… (the date is further along the line) | link in a related-stories, navigation or archive list |
| (a) timesofindia.indiatimes.com | 2026-04-29 | 2026-10-14 | [Zoho pauses hikes and ad spend due to rising AI costs][Rupee up 49 paise, RBI governor says curbs to halt speculation](https://timesofindia.indiatimes.com/business/india-business/… (the date is further along the line) | link in a related-stories, navigation or archive list |
| (b) www.indiainfoline.com | 2026-02-05 | 2026-08-23 | 23 Aug 2026/02:05 PM… | date of an item in a related-stories or 'latest' list |

**benign** (5 shown)

| Source | Cutoff | Date found | Line (shortened) | Claude Code's reason |
|---|---|---|---|---|
| (a) www.edie.net | 2026-04-29 | 2031-03-01 | …ctricity transmission infrastructure. The new charging framework will run until March 2031 and introduces higher fixed costs for many commercial and industrial energy users.… | the new UK network-charging framework 'will run until March 2031' (a fixed price-control period) |
| (b) m.economictimes.com | 2026-02-05 | 2026-02-06 | …nd investors are watching closely. The decision on the repo rate is expected on February 6, 2026. Analysts anticipate the repo rate will remain unchanged at 5.25%.… | the MPC meeting's scheduled decision date |
| (a) www.birminghammail.co.uk | 2026-04-29 | 2026-06-30 | Between 1 April and 30 June 2026, the energy price cap is set at £1,641 per year for a typical household who use electricity and gas and pay by Direct Debit.… | the energy price cap 'set' for 1 April to 30 June 2026, announced in advance |
| (b) www.indiainfoline.com | 2026-02-05 | 2026-12-01 | …February and December 2025. The average CPI inflation for the nine months up to December 2026 is already at a low 1.7%, which means inflation is broadly tracking the RBI’s projecti… | 'nine months up to December 2026' in a February 2026 preview: an evident typo for December 2025 (FY26), not later content |
| (a) timesofindia.indiatimes.com | 2026-04-29 | 2026-07-01 | New Delhi: Electricity in Delhi is likely to get more expensive for consumers as the Appellate Tribunal for Electricity (APTEL) on Monday ordered the city’s power regulator, Delhi … (the date is further along the line) | quotes DERC's request for an extension 'till July 1, 2026' from an April order |
