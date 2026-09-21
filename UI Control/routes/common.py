import hmac
import json
import os
from pathlib import Path
import sys
import threading
import time
from typing import Any

from dotenv import load_dotenv

CURRENT_DIR = Path(__file__).resolve().parent.parent
MARKETING_DIR = CURRENT_DIR.parent
DIST_DIR = CURRENT_DIR / "dist"
OVERRIDES_FILE = Path(os.getenv("CONFIG_OVERRIDES_PATH", str(MARKETING_DIR / "output" / "config_overrides.json")))

if str(MARKETING_DIR) not in sys.path:
    sys.path.insert(0, str(MARKETING_DIR))

# Load .env from workspace root
load_dotenv(MARKETING_DIR / ".env")

# Apply persistent config overrides onto os.environ (Railway / container restart resilience)
try:
    if OVERRIDES_FILE.exists():
        _overrides_data = json.loads(OVERRIDES_FILE.read_text(encoding="utf-8"))
        if isinstance(_overrides_data, dict):
            for _k, _v in _overrides_data.items():
                if _v is not None:
                    os.environ[_k] = str(_v)
except Exception:
    pass

try:
    from content_automation.config import load_settings
except ImportError:
    load_settings = None

# Optional Dashboard PIN to protect paid AI generations
DASHBOARD_PIN = os.getenv("DASHBOARD_PIN", "").strip()

# Global pipeline concurrency tracker
_GLOBAL_LOCK = threading.Lock()
_ACTIVE_PIPELINES: dict[str, str] = {}  # name -> description

# Rate limiting for PIN authentication
_FAILED_ATTEMPTS: dict[str, list[float]] = {}
_RATE_LIMIT_LOCK = threading.Lock()
_OVERRIDES_LOCK = threading.Lock()
MAX_FAILED_ATTEMPTS = 10
LOCKOUT_SECONDS = 300  # 5 minutes lockout


def is_rate_limited(ip: str) -> bool:
    """Check if an IP has exceeded failed PIN attempts."""
    now = time.time()
    with _RATE_LIMIT_LOCK:
        attempts = _FAILED_ATTEMPTS.get(ip, [])
        recent = [t for t in attempts if now - t < LOCKOUT_SECONDS]
        _FAILED_ATTEMPTS[ip] = recent
        return len(recent) >= MAX_FAILED_ATTEMPTS


def record_failed_attempt(ip: str) -> None:
    """Record an invalid PIN attempt for rate limiting."""
    now = time.time()
    with _RATE_LIMIT_LOCK:
        if ip not in _FAILED_ATTEMPTS:
            _FAILED_ATTEMPTS[ip] = []
        _FAILED_ATTEMPTS[ip].append(now)


def clear_failed_attempts(ip: str) -> None:
    """Clear failed attempts upon successful authentication."""
    with _RATE_LIMIT_LOCK:
        _FAILED_ATTEMPTS.pop(ip, None)


def _check_pin(candidate: str) -> bool:
    """Timing-safe PIN comparison."""
    if not candidate or not DASHBOARD_PIN:
        return False
    return hmac.compare_digest(candidate.strip(), DASHBOARD_PIN.strip())


def is_authorized(req: Any = None) -> bool:
    """Verify authorization token or PIN with timing-safe comparison and rate limiting."""
    if not DASHBOARD_PIN:
        return True

    if req is None:
        try:
            from flask import request as flask_req
            req = flask_req
        except Exception:
            return False

    client_ip = getattr(req, "remote_addr", None) or "unknown"
    if is_rate_limited(client_ip):
        return False

    candidate: str | None = None

    # 1. Bearer Token
    auth_header = req.headers.get("Authorization", "").strip()
    if auth_header:
        candidate = auth_header[7:].strip() if auth_header.lower().startswith("bearer ") else auth_header

    # 2. X-Dashboard-PIN Header
    if not candidate:
        candidate = req.headers.get("X-Dashboard-PIN", "").strip() or None

    # 3. Query Param ?pin=...
    if not candidate and hasattr(req, "args"):
        candidate = req.args.get("pin", "").strip() or None

    # 4. JSON payload pin field
    if not candidate and getattr(req, "is_json", False):
        data = req.get_json(silent=True) or {}
        val = str(data.get("pin", "")).strip()
        if val:
            candidate = val

    if candidate and _check_pin(candidate):
        clear_failed_attempts(client_ip)
        return True

    if candidate:
        record_failed_attempt(client_ip)

    return False


def load_config_overrides() -> dict[str, str]:
    """Load persistent configuration overrides from output/config_overrides.json."""
    with _OVERRIDES_LOCK:
        if OVERRIDES_FILE.exists():
            try:
                return json.loads(OVERRIDES_FILE.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}


def save_config_override(key: str, value: str) -> None:
    """Persist an editable Studio setting before exposing it to running jobs."""
    if not key or not value.strip():
        raise ValueError("A configuration key and value are required")
    with _OVERRIDES_LOCK:
        OVERRIDES_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = load_config_overrides_unlocked()
        data[key] = value
        pending = OVERRIDES_FILE.with_name(OVERRIDES_FILE.name + ".pending")
        try:
            pending.write_text(json.dumps(data, indent=2), encoding="utf-8")
            env_file = MARKETING_DIR / ".env"
            if env_file.is_file():
                from dotenv import set_key

                if not set_key(str(env_file), key, value, quote_mode="always"):
                    raise OSError(f"Could not update {env_file}")
            pending.replace(OVERRIDES_FILE)
            os.environ[key] = value
        finally:
            pending.unlink(missing_ok=True)


def load_config_overrides_unlocked() -> dict[str, str]:
    """Read overrides while the caller already holds the settings lock."""
    if not OVERRIDES_FILE.is_file():
        return {}
    data = json.loads(OVERRIDES_FILE.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Studio configuration overrides must be a JSON object")
    return {str(key): str(value) for key, value in data.items() if value is not None}


class PipelineRunningResult(tuple):
    """
    Tuple subclass that evaluates to False in a boolean context if the running status is False.
    This preserves backwards compatibility with callers unpacking `running, desc = ...`
    and callers using `if is_any_pipeline_running(...):` directly.
    """
    def __new__(cls, running: bool = False, desc: str | None = None):
        return super().__new__(cls, (running, desc))

    def __bool__(self) -> bool:
        return bool(self[0])


def is_any_pipeline_running(exclude: str | None = None) -> PipelineRunningResult:
    """Check if another pipeline is currently running. Global lock is disabled to allow concurrency across tabs."""
    return PipelineRunningResult(False, None)


def register_pipeline(name: str, description: str) -> None:
    """Register a running pipeline in global tracker."""
    with _GLOBAL_LOCK:
        _ACTIVE_PIPELINES[name] = description


def unregister_pipeline(name: str) -> None:
    """Unregister a finished or cancelled pipeline."""
    with _GLOBAL_LOCK:
        _ACTIVE_PIPELINES.pop(name, None)


def extract_clean_error(
    logs: list[str],
    default_code: int | None = 1,
    default: str | None = None,
    *args: Any,
    **kwargs: Any,
) -> str:
    """Analyze stdout/stderr logs to extract a user-friendly error summary."""
    full_text = "\n".join(logs).lower()

    # 1. Krea Moodboard 404 / rejection
    if "moodboard not found" in full_text or ("moodboard" in full_text and ("404" in full_text or "not accessible" in full_text or "invalid for this api key" in full_text)):
        return "Moodboard Not Found: The specified Krea Moodboard ID was not found or is not accessible with your Krea API key. Please verify or update the Moodboard ID in the card."

    # 2. Akeneo / Shopify catalog check
    if "no eligible products found" in full_text:
        return "Catalog Check: No eligible products found matching this category that are live on Shopify."

    # 3. Airtable authentication or table not found (strict matching to avoid masking Python errors)
    if "airtable" in full_text and (
        "table_not_found" in full_text
        or "model_not_found" in full_text
        or "table not found" in full_text
        or "base not found" in full_text
        or "could not find table" in full_text
        or "invalid api key" in full_text
        or "401 client error" in full_text
        or "403 client error" in full_text
    ):
        return "Airtable Error: Check your AIRTABLE_TOKEN and Table ID in .env."

    # 4. Fal AI authentication
    if "fal" in full_text and ("401" in full_text or "unauthorized" in full_text or "invalid key" in full_text):
        return "Fal AI Auth Error: Check your FAL_KEY in .env."

    # 5. Look for specific line starting with [ERROR] or [FATAL]
    for line in reversed(logs):
        stripped = line.strip()
        if stripped.startswith("[ERROR]") or stripped.startswith("[FATAL]"):
            cleaned = stripped.split("]", 1)[-1].strip()
            if cleaned and "pipeline exited with code" not in cleaned.lower():
                return cleaned

    # 6. Look for Python exception / traceback line if present
    for line in reversed(logs):
        stripped = line.strip()
        if any(
            stripped.startswith(prefix)
            for prefix in (
                "AttributeError:",
                "TypeError:",
                "ValueError:",
                "KeyError:",
                "FileNotFoundError:",
                "RuntimeError:",
                "IndexError:",
                "ZeroDivisionError:",
                "NameError:",
                "Exception:",
            )
        ):
            return stripped

    if default:
        return str(default)
    if "default" in kwargs and kwargs["default"]:
        return str(kwargs["default"])

    code = default_code if default_code is not None else 1
    return f"Process exited with non-zero code {code}"
