"""Shared by the repro scripts. Standard library only.

Each script sends ONE Tavily request with your own key (environment variable TAVILY_API_KEY), prints the request_id
and the credits Tavily reports for the call, and refuses before sending if its own cost estimate is above
MAX_CREDITS. The key is never printed or written. Set REPRO_RECEIPT=<file> to also append one JSON line per call.
"""
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

BASE = "https://api.tavily.com"
MAX_CREDITS = 2                                                 # no script may estimate more than this


def transport(method, url, key, body):
    """The one place that touches the network (tests replace it)."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Tavily answered HTTP {e.code} {e.reason}: {e.read().decode('utf-8', 'replace')[:300]}")


def api_key():
    key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not key:
        raise SystemExit("Set TAVILY_API_KEY to your own Tavily key (export TAVILY_API_KEY=...). Nothing was sent.")
    return key


def sha256(response):
    blob = json.dumps(response, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def call(endpoint, body=None, *, estimate, method="POST"):
    """Send one request. `estimate` is the script's upper bound in credits; above MAX_CREDITS nothing is sent."""
    if estimate > MAX_CREDITS:
        raise SystemExit(f"Estimated {estimate} credits is above this kit's cap of {MAX_CREDITS}. Nothing was sent.")
    resp = transport(method, BASE + endpoint, api_key(), body)
    credits = (resp.get("usage") or {}).get("credits", 0) if isinstance(resp, dict) else 0
    print(f"{method} {endpoint}: request_id {resp.get('request_id')}, credits reported {credits} "
          f"(estimate {estimate}, cap {MAX_CREDITS})")
    path = os.environ.get("REPRO_RECEIPT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"endpoint": endpoint, "request_id": resp.get("request_id"), "credits": credits,
                                "response_time": resp.get("response_time"), "response_sha256": sha256(resp)}) + "\n")
    return resp


def month_of(date_text):
    """'YYYY-MM' of an ISO-looking date text, or None."""
    return str(date_text)[:7] if date_text and str(date_text)[:4].isdigit() else None


def tally(values):
    out = {}
    for v in values:
        out[v] = out.get(v, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: str(kv[0])))


def run(main):
    sys.exit(main() or 0)
