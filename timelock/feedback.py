"""Optional report-back to Tavily: tell Tavily which results our date check flagged (standard library only).

Tavily's feedback endpoint (https://docs.tavily.com/documentation/api-reference/endpoint/feedback): "Beta. This
endpoint is in beta: the request shape may still change", `POST https://api.tavily.com/feedback` with a Bearer key.
`request_id` and `session_id` are both optional in the schema, but a request with neither is a 400. Per-result notes
go in `urls_scores` (each item needs `id` or `url`; `comment` up to 2000 characters). "Submitting feedback is free
-- it does not consume API credits." Tavily asks that a failure be treated as non-fatal, so a failed send is
returned, never raised.

    payload = build_feedback(request_id, result, "published 2026-05-02, after the requested end_date 2026-04-29")
    send_feedback(request_id, result, reason)                                  # dry run: returns the payload
    send_feedback(request_id, result, reason, dry_run=False, own_request_ids=ids)   # one POST, own requests only

Only results from our own requests that sent an end_date are reported (report_leaks): a search with no date filter
is a control, and its leaks are not a fault of Tavily's filter. Off by default everywhere: dry_run=True here,
report_to_tavily=False on the MCP check_leaks tool.
"""
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from timelock.check import LEAK, check_result
from timelock.dates import iso_date, url_date

ENDPOINT = "https://api.tavily.com/feedback"
COMMENT_MAX = 2000                  # urls_scores[].comment limit in Tavily's reference


def build_feedback(request_id, result, reason):
    """The /feedback body for one result of one request. No score is sent: Tavily's reference defines no scale
    for agent_score (its examples use 1 and -1), so the note is the reason in `comment`. The result is identified by its `id` when it has
    one, else its `url`."""
    if not request_id:
        raise ValueError("request_id is required")
    ident = {"id": result["id"]} if result.get("id") else {"url": result.get("url")}
    if not next(iter(ident.values())):
        raise ValueError("the result needs an id or a url")
    return {"request_id": request_id, "urls_scores": [{**ident, "comment": str(reason)[:COMMENT_MAX]}]}


def reason_for(result, cutoff, *, end_date=None, captures=None):
    """One sentence saying what our check saw: the dates found and the cutoff. `end_date` is the end_date the request
    sent, if any (the sentence then says it was after the requested end_date; without one it says the request sent
    none, and report_leaks does not send such a note). `captures` (Wayback capture dates, if the caller looked) adds the archive finding."""
    seen = [f"{name} {d}" for name, d in (("published_date", iso_date(result.get("published_date"))),
                                          ("url date", url_date(result.get("url"))),
                                          ("page date", iso_date(result.get("page_date")))) if d]
    after = f"after the requested end_date {end_date}" if end_date else f"after the cutoff {cutoff} (this request sent no end_date)"
    text = f"{'; '.join(seen) or 'no date'}: {after}"
    if captures is not None:
        early = [c for c in captures if c <= cutoff]
        text += (f"; earliest archive copy {min(captures)}" if captures and not early else
                 f"; archive copy on or before the cutoff {min(early)}" if early else
                 f"; no archive copy on or before the cutoff {cutoff}")
    return text


def own_request_ids(path):
    """request_ids from our credit ledger's receipts (results/call_receipts.json: {"rows": [{"request_id": ...}]}),
    or a plain JSON list of ids."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = data["rows"] if isinstance(data, dict) else data
    return {r["request_id"] if isinstance(r, dict) else r for r in rows if (r["request_id"] if isinstance(r, dict) else r)}


def own_end_dates(path):
    """{request_id: end_date} for ledger rows that record the end_date the request sent (rows without one map to
    None, so report_leaks skips them). results/call_receipts.json records none."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = data["rows"] if isinstance(data, dict) else data
    return {r["request_id"]: r.get("end_date") for r in rows if isinstance(r, dict) and r.get("request_id")}


def _post(payload, api_key, timeout=30):
    req = urllib.request.Request(ENDPOINT, data=json.dumps(payload).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer " + api_key})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def send_feedback(request_id, result, reason, *, dry_run=True, own_request_ids=None, api_key=None, post=_post):
    """Dry run (the default): returns {"dry_run": True, "payload": ...} and sends nothing. With dry_run=False: sends
    one POST, but only for a request_id in `own_request_ids`; any other id is skipped, not sent. Returns
    {"sent": True, "response": ...}, or {"sent": False, "error": ...} (a failure is not raised: the endpoint is in
    beta). The key comes from `api_key` or TAVILY_API_KEY and is never returned."""
    payload = build_feedback(request_id, result, reason)
    if dry_run:
        return {"dry_run": True, "payload": payload}
    if request_id not in (own_request_ids or ()):
        return {"sent": False, "skipped": "not_our_request", "payload": payload}
    key = api_key or os.environ.get("TAVILY_API_KEY")
    if not key:
        return {"sent": False, "error": "no Tavily key: pass api_key or set TAVILY_API_KEY", "payload": payload}
    try:
        return {"sent": True, "response": post(payload, key), "payload": payload}
    except (urllib.error.URLError, OSError, ValueError) as e:
        return {"sent": False, "error": f"{type(e).__name__}: {getattr(e, 'code', '')}".strip(": "), "payload": payload}


def report_leaks(results, cutoff, request_id, *, own_request_ids=None, dry_run=True, end_date=None, **send_kw):
    """Feedback for each result our check labels `leak` (undated results are not reported) in one request's
    results. Returns a list of send_feedback outcomes. Skipped, not sent (also on a dry run, so it shows exactly what
    a real send would do): a request_id not in `own_request_ids` ("not_our_request"), and a request that sent no
    `end_date` ("no_end_date": an undated control search; its leaks are not a fault of the date filter)."""
    out = []
    for r in results:
        if check_result(r, cutoff, page_date=iso_date(r.get("page_date")) or None) != LEAK:
            continue
        if not request_id or request_id not in (own_request_ids or ()):
            out.append({"sent": False, "skipped": "not_our_request", "url": r.get("url")})
        elif not end_date:
            out.append({"sent": False, "skipped": "no_end_date", "url": r.get("url")})
        else:
            out.append(send_feedback(request_id, r, reason_for(r, cutoff, end_date=end_date), dry_run=dry_run,
                                     own_request_ids=own_request_ids, **send_kw))
    return out
