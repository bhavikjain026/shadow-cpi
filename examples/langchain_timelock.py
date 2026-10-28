"""TimeLockedTavilySearch as a LangChain tool. Offline: a saved Tavily response, 0 credits. Needs: pip install ".[langchain]"."""
from pathlib import Path

from timelock import Replay
from timelock.langchain import TimeLockedTavilySearch

saved = Path(__file__).resolve().parent.parent / "tests/fixtures/timelock/rbi_2026-10-06_locked.json"
tool = TimeLockedTavilySearch(cutoff="2026-10-06", client=Replay(saved), topic="news")      # drop client= for live
print(tool.invoke({"query": "RBI monetary policy repo rate decision October 2026"})["counts"])
