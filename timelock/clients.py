"""Two small clients for timelocked_search: a live one (standard library, no SDK) and a saved-response replay."""
import copy
import json
import os
import urllib.request
from pathlib import Path


class TavilyHTTP:
    """Minimal live Tavily client: POST /search and /extract with the key from the argument or TAVILY_API_KEY."""

    def __init__(self, api_key=None, base="https://api.tavily.com", timeout=60):
        self.api_key = api_key or os.environ.get("TAVILY_API_KEY")
        if not self.api_key:
            raise ValueError("no Tavily key: pass api_key or set TAVILY_API_KEY")
        self.base, self.timeout = base.rstrip("/"), timeout

    def search(self, query, **params):
        return self._post("/search", {"query": query, **params})

    def extract(self, urls, **params):
        return self._post("/extract", {"urls": list(urls), **params})

    def _post(self, endpoint, body):
        body = json.dumps({**body, "include_usage": True}).encode("utf-8")
        req = urllib.request.Request(self.base + endpoint, data=body, method="POST",
                                     headers={"Content-Type": "application/json",
                                              "Authorization": "Bearer " + self.api_key})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.load(r)


class Replay:
    """Serves one saved Tavily /search response ({'request': ..., 'response': ...}) with no network call.
    Refuses any request other than the one recorded (include_usage aside), so a replay never answers a different
    question, window or filter with a saved response."""

    IGNORED = ("include_usage",)

    def __init__(self, path):
        saved = json.loads(Path(path).read_text(encoding="utf-8"))
        self.request, self.response = saved["request"], saved["response"]

    def search(self, query, **params):
        sent = {"query": query, **params}
        keys = (sent.keys() | self.request.keys()) - set(self.IGNORED)
        diff = {k: (sent.get(k), self.request.get(k)) for k in sorted(keys) if sent.get(k) != self.request.get(k)}
        if diff:
            raise ValueError(f"saved response was recorded for a different request (sent, recorded): {diff}")
        return copy.deepcopy(self.response)
