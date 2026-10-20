"""Tiny JSON-over-HTTP helper (standard library only) with polite retries."""
import json
import time
import urllib.error
import urllib.request


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(f"HTTP {status}: {message}")
        self.status = status


def request_json(method, url, token=None, body=None, timeout=120, retries=3):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:500]
            if e.code == 429 and attempt < retries:  # rate limited: honour Retry-After
                time.sleep(float(e.headers.get("Retry-After") or 2 ** attempt))
                continue
            if e.code in (500, 502, 503, 504) and attempt < retries:
                time.sleep(2 ** attempt)
                continue
            if e.code == 432:
                raise ApiError(432, "Tavily plan credit limit reached - upgrade or wait for the monthly reset") from None
            if e.code == 433:
                raise ApiError(433, "Tavily pay-as-you-go limit reached") from None
            raise ApiError(e.code, detail) from None
        except urllib.error.URLError as e:
            if attempt < retries:
                time.sleep(2 ** attempt)
                continue
            raise ApiError(0, f"network error: {e.reason}") from None
