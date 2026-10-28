# Questions a skeptical Tavily engineer would ask

Each answer is read from this repository's results files; the numbers are filled in by `tools/sync_doc_numbers.py`.
Back to the [README](../README.md#honest-limits).

## Isn't this just "pass `start_date` / `end_date`"?

Passing the dates is one half, and we measure it: with dates and `filter_by_published_date`, {{pool_dated}} of
{{pool_cases}} cases kept a confirmed leak; with no dates, {{pool_nodates}} of {{pool_cases}} did (date-test rule, pilot plus replication). The
other half is what dates cannot do: Tavily dated `{{ex_row}}`, a {{ex_company}} results preview, {{ex_published}}, before its {{ex_cutoff}} cutoff, but
the page was updated on {{ex_updated}} and Extract returns the updated page. `extract_as_of` fixes that by serving the
latest Wayback copy on or before the cutoff (or nothing), at the price of one more Extract credit per page, and the
`timelock/` wrapper is reusable by any agent.

## {{pool_cases}} cases is small?

Yes. Zero leaks in {{pool_cases}} cases gives a Wilson {{wilson}} interval of {{pool_dated_w}}, and the rule of three puts the upper bound near
{{pool_rule3}}, so a leak rate of a few percent is not ruled out. The count is a pre-registered pilot ({{dt_cases}} cases) plus a
pre-registered replication ({{rep_cases}} new cases) under one rule; both are India-focused, so they show the effect and its size
here, not Tavily's behaviour in general.

## Why Wayback as ground truth, and what can it not prove?

It is the only independent record of whether a page existed by the cutoff, so a leak counts only when the Wayback
Machine confirms one. Absence from the archive is not non-existence: pages it never saw can only be flagged, and lookups
can fail, so the no-dates counts are lower bounds. The logged retry shows it: {{rr_dt_failed}} failed lookups, and recovering them moved the date
test's no-dates count from {{dt_nodates}} to {{dt_nodates_retry}} of {{dt_cases}}.

## Is this a Tavily bug?

Mostly no. `published_date` was later than the page's own date on {{pd_later}} of {{pd_pages}} distinct date-test pages, which
is consistent with Tavily's documented definition (published or last updated, beta); we ask only for separate original and
last-modified dates. Each item in [`tavily_bug_reports.md`](tavily_bug_reports.md) states what we observed and what we expected, with request IDs,
and the date-semantics item is framed as a feature request, not a defect.

## What about the filter dropping valid evidence?

It does, and we report the cost: the filter dropped {{dt_lost_filter}} of the date test's {{dt_valid_total}} pieces of valid evidence on the
initial pass ({{dt_lost_filter_retry}} of {{dt_valid_total_retry}} after the archive retry). Adding our own page-date check lost {{dt_lost_pagecheck}} of {{dt_valid_total}} on the initial
pass. Whether that trade is worth it depends on how costly a leak is for your backtest.

## Dates are estimates. Can a wrong date pass the filter?

Yes: `{{ex_row}}` passed because its date said {{ex_published}} while the content changed on {{ex_updated}}; the filter reads a page's
date, not its edit history. That is why the code also checks the date printed on the page, why `extract_as_of` exists,
and why the drift monitor re-reads pages, though none of them covers the gap completely.

## What was the `auto_parameters` claim?

On {{auto_searches}} searches about past months with no dates, {{auto_oct}} of {{auto_results}} results came from {{live_month}} ({{auto_note}}). The report therefore says "observed", not
"reproduced". With our dates added,
{{autod_inside}} of {{autod_dated}} dated results fell inside the window, though the echo still reports a `time_range`.

## Does the model already know the answers?

Possibly, and we have not measured it: a replay cannot rule out that a model's training data holds the outcome. The
pipeline limits the exposure (the model only extracts quotes, and code checks that each cited number is on the page),
but the clean test is a sealed forward forecast: the {{live_month}} nowcast is sealed (SHA-256 and git tag) before MoSPI's {{release_day}} release, so
nothing about the outcome can be known when it is written; the README gives the seal's status.

## Did you beat the economists?

No; about a tie. On the {{poll_months}} months with a dated economists' poll, our nowcast missed by {{mae_poll_c}} percentage points
and the poll by {{mae_poll}}. Over all {{months}} test months it missed by {{mae_c}}, and the {{range_level}} range held the official figure
in only {{inside}} of {{months}}.

## Why should a Tavily user care?

Any agent backtest that searches the past has this look-ahead problem, whatever the topic; inflation is just where we
measured it. The fix is small and reusable: [`timelock/`](../timelock/) (standard library only), a LangChain tool, an MCP
server with `check_leaks`, a labelled benchmark of {{tl_cases}} cases, and a Colab notebook to reproduce the leak with your own key.
