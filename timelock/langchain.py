"""TimeLockedTavilySearch: a LangChain search tool that cannot see past a cutoff. Optional: pip install "timelock[langchain]".

    from timelock.langchain import TimeLockedTavilySearch
    tool = TimeLockedTavilySearch(cutoff="2026-10-06")          # TAVILY_API_KEY, or client=...
    tool.invoke({"query": "RBI repo rate decision October 2026"})

Use it where Tavily's own LangChain search tool goes (an agent's tool list, a ToolNode). The cutoff is fixed when the
tool is built, so the agent cannot move it. Every call goes through timelocked_search. Only results dated on or before
the cutoff (status safe) are returned; undated and post-cutoff results are counted, never shown. `time_range`, `days`
and `auto_parameters` are refused, as in the core. `import timelock` never imports this module.
"""
try:
    from langchain_core.tools import BaseTool
except ImportError as e:                                    # langchain is optional; the core never needs it
    raise ImportError('timelock.langchain needs langchain-core: pip install "timelock[langchain]"') from e

from typing import Any, Optional

from pydantic import BaseModel, Field

from timelock.clients import TavilyHTTP
from timelock.search import REFUSED, TimeLockError, timelocked_search


class _Input(BaseModel):
    query: str = Field(description="search query")
    start_date: Optional[str] = Field(default=None, description="narrow the window: YYYY-MM-DD, never after the cutoff")
    end_date: Optional[str] = Field(default=None, description="narrow the window: YYYY-MM-DD, never after the cutoff")
    time_range: Optional[str] = Field(default=None, description="refused: the time lock owns the window")
    days: Optional[int] = Field(default=None, description="refused: the time lock owns the window")
    auto_parameters: Optional[bool] = Field(default=None, description="refused: the time lock owns the window")


class TimeLockedTavilySearch(BaseTool):
    name: str = "timelocked_tavily_search"
    description: str = ("Search the web as it was on the cutoff date: nothing published after it. Returns dated results "
                        "with title, url and snippet, plus counts of results held back (undated or dated after the "
                        "cutoff). A snippet is a pointer; read the page before quoting it.")
    args_schema: type[BaseModel] = _Input
    cutoff: str                                             # required, ISO date; checked on every call
    client: Any = None                                      # anything with .search(); default TavilyHTTP()
    max_results: int = 5
    topic: str = "general"
    search_depth: str = "basic"
    include_domains: Optional[list[str]] = None
    exclude_domains: Optional[list[str]] = None

    def __init__(self, **data):
        bad = sorted(k for k in data if k in REFUSED)
        if bad:                                             # TimeLockError, not pydantic's wrapper
            raise TimeLockError(f"the time lock owns the window; remove {', '.join(bad)}")
        super().__init__(**data)

    def _run(self, query, start_date=None, end_date=None, time_range=None, days=None, auto_parameters=None,
             run_manager=None):
        refused = {"time_range": time_range, "days": days, "auto_parameters": auto_parameters}
        bad = sorted(k for k, v in refused.items() if v is not None)
        if bad:
            raise TimeLockError(f"the time lock owns the window; remove {', '.join(bad)}")
        client = self.client or TavilyHTTP()
        kw = {"topic": self.topic, "max_results": self.max_results, "search_depth": self.search_depth,
              "include_published_date": True, "include_domains": self.include_domains,
              "exclude_domains": self.exclude_domains, "start_date": start_date, "end_date": end_date}
        res = timelocked_search(client, query, self.cutoff, **{k: v for k, v in kw.items() if v is not None})
        return {"query": query, "cutoff": res.cutoff, "window": res.window, "counts": res.counts,
                "request_id": res.request_id, "response_sha256": res.response_sha256,
                "results": [{k: v for k, v in r.items() if k != "raw_content"} for r in res.safe()]}
