"""Settings: API keys come from the environment (or a local .env file). Key values are never printed."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TAVILY_BASE = os.environ.get("SCPI_TAVILY_BASE_URL", "https://api.tavily.com")
NEBIUS_BASE = os.environ.get("SCPI_NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1")
MODELS_FILE = ROOT / "config" / "models.json"


def load_dotenv(path=ROOT / ".env"):
    """Minimal .env reader (KEY=value lines). Does not override variables already set."""
    if not Path(path).exists():
        return
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def key(*names, required=True):
    load_dotenv()
    for n in names:
        if os.environ.get(n):
            return os.environ[n]
    if required:
        raise SystemExit("Missing environment variable: " + " or ".join(names) + " (put it in .env)")
    return None


def tavily_key():
    return key("SCPI_TAVILY_API_KEY", "TAVILY_API_KEY")


def nebius_key():
    return key("SCPI_NEBIUS_API_KEY", "NEBIUS_API_KEY")


def models():
    """Model IDs chosen by checks.py (small = extraction, mid = event reading, large = brief)."""
    if MODELS_FILE.exists():
        return json.loads(MODELS_FILE.read_text(encoding="utf-8"))
    return {}
