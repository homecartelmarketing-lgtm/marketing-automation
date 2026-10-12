import hmac
import json
import os
from pathlib import Path
import secrets
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

# Per-process secret for the Studio's own loopback calls (queue worker, calendar
# import). Lets them authenticate without the browser's session cookie or a PIN.
INTERNAL_TOKEN = secrets.token_urlsafe(32)
INTERNAL_TOKEN_HEADER = "X-Internal-Token"


def internal_auth_headers() -> dict[str, str]:
    """Headers for Studio -> Studio loopback requests."""
    return {INTERNAL_TOKEN_HEADER: INTERNAL_TOKEN}


# Global pipeline concurrency tracker
_GLOBAL_LOCK = threading.Lock()
_ACTIVE_PIPELINES: dict[str, str] = {}  # name -> description

# Rate limiting for PIN authentication
_FAILED_ATTEMPTS: dict[str, list[float]] = {}
_RATE_LIMIT_LOCK = threading.Lock()
_OVERRIDES_LOCK = threading.Lock()
MAX_FAILED_ATTEMPTS = 10
LOCKOUT_SECONDS = 300  # 5 minutes lockout

# Single ceiling for how many fresh products one /run may scrape+generate.
# Every pipeline /run route AND the queue /enqueue clamp the client-supplied
# max_items to 1..MAX_RUN_ITEMS so a forged request can't spin up an unbounded
# number of paid AI generations in one job.
MAX_RUN_ITEMS = 10


def is_same_origin(req: Any = None) -> bool:
    """True when the request has no cross-site Origin (same-origin or non-browser).

    Same-origin fetches send either no Origin header or one equal to our host;
    cross-site browsers send a foreign Origin. A *present* Origin that doesn't
    match the request host is rejected — this is the CSRF guard for the internal
    token / cookie-session paths.
    """
    try:
        if req is None:
            from flask import request as flask_req

            req = flask_req
        origin = (req.headers.get("Origin") or "").strip()
        if not origin:
            return True  # same-origin GET/curl/queue loopback: no Origin header
        try:
            from urllib.parse import urlparse

            host = urlparse(origin).netloc.lower()
        except Exception:
            return False
        if not host:
            return False
        if host == (req.host or "").lower():
            return True
        allowed = {
            h.strip().lower()
            for h in os.getenv("STUDIO_ALLOWED_ORIGINS", "").split(",")
            if h.strip()
        }
        return host in allowed
    except Exception:
        return False


def _forbid_pin_in_query(req: Any) -> None:
    """Reject a PIN smuggled in the query string.

    URLs leak into access logs, proxy logs, browser history and the Referer
    header, so a PIN passed as ``?pin=...`` would be recorded in cleartext in
    places we don't control. We no longer *read* the PIN from the query string;
    if one is present we raise so the request is refused rather than silently
    ignored (a silent ignore would look like a wrong-PIN to the caller).
    """
    try:
        raw = (req.args.get("pin", "") if hasattr(req, "args") else "") or ""
        if raw.strip():
            raise ValueError("PIN must not be sent in the query string")
    except ValueError:
        raise
    except Exception:
        return


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


# Reject over-long PINs before any comparison. compare_digest short-circuits on
# length, so an unbounded submitted PIN can't leak via timing, and we avoid
# wasting work on absurdly long inputs. 256 chars is far above any real PIN.
MAX_PIN_LENGTH = 256


def clamp_pin(candidate: str | None) -> str:
    """Return a length-bounded candidate safe to compare against the PIN."""
    if not candidate:
        return ""
    return candidate[:MAX_PIN_LENGTH]


def is_authorized(req: Any = None) -> bool:
    """Verify session, internal token or PIN with timing-safe comparison and rate limiting."""
    try:
        from routes import studio_auth
        accounts_enabled = studio_auth.accounts_enabled()
    except Exception:
        studio_auth = None
        accounts_enabled = False

    if not DASHBOARD_PIN and not accounts_enabled:
        return True

    if req is None:
        try:
            from flask import request as flask_req
            req = flask_req
        except Exception:
            return False

    # Reject cross-site browser requests outright (CSRF). A same-origin fetch
    # carries no Origin header or one matching our host; the queue worker's
    # urllib loopback sends none. A present foreign Origin is dropped before we
    # even look at credentials, so a stolen session cookie alone can't act.
    if not is_same_origin(req):
        return False

    # Studio's own loopback calls (queue dispatch, calendar enqueue)
    internal = req.headers.get(INTERNAL_TOKEN_HEADER, "").strip()
    if internal and hmac.compare_digest(internal, INTERNAL_TOKEN):
        return True

    # Logged-in browser session (email + password)
    if studio_auth is not None and studio_auth.current_user() is not None:
        return True

    if not DASHBOARD_PIN:
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

    # NOTE: the ?pin= query param is intentionally no longer accepted. URLs leak
    # into access logs, proxy logs, and Referer headers, so a PIN passed that way
    # ends up recorded in cleartext. Credentials belong in the Authorization /
    # X-Dashboard-PIN headers or the JSON body only.
    if not candidate and getattr(req, "args", None) is not None:
        _forbid_pin_in_query(req)

    # 4. JSON payload pin field
    if not candidate and getattr(req, "is_json", False):
        data = req.get_json(silent=True) or {}
        val = str(data.get("pin", "")).strip()
        if val:
            candidate = val

    if candidate and _check_pin(clamp_pin(candidate)):
        clear_failed_attempts(client_ip)
        return True

    if candidate:
        record_failed_attempt(client_ip)

    return False


def _log_auth_event(event: str, req: Any = None, allowed: bool = False) -> None:
    """Emit a single-line auth decision to stderr (gunicorn/Railway capture it).

    Deliberately never logs the candidate secret (PIN/token), only the outcome
    and a few request attributes, so the logs can't leak credentials.
    """
    try:
        ip = getattr(req, "remote_addr", None) or "unknown"
        method = getattr(req, "method", "-")
        path = getattr(req, "path", "-")
        print(
            f"[AUTH] {'ALLOW' if allowed else 'DENY'} {event} "
            f"{method} {path} ip={ip}",
            file=sys.stderr,
            flush=True,
        )
    except Exception:
        pass


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
    """Persist an editable Studio setting before exposing it to running jobs.

    Studio settings live in ``output/config_overrides.json`` (overlaid onto
    ``os.environ`` at startup) and are never written to ``.env`` — the secrets
    file must not be rewritten by a UI action. Standalone CLI runs pick the
    same values up via ``content_automation.fixture_catalog.load_studio_overrides``.
    """
    if not key or not value.strip():
        raise ValueError("A configuration key and value are required")
    if value.strip().lower() in ("none", "null", "undefined"):
        # Never persist a stringified missing value (it would shadow the real default).
        print(f"[WARN] Ignoring placeholder value {value!r} for {key}")
        return
    with _OVERRIDES_LOCK:
        OVERRIDES_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = load_config_overrides_unlocked()
        data[key] = value
        pending = OVERRIDES_FILE.with_name(OVERRIDES_FILE.name + ".pending")
        try:
            pending.write_text(json.dumps(data, indent=2), encoding="utf-8")
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


MOODBOARD_NOT_FOUND_MESSAGE = (
    "Moodboard Not Found: The specified Krea Moodboard ID was not found or is not "
    "accessible with your Krea API key. Please verify or update the Moodboard ID in the card."
)


def extract_clean_error(
    logs: list[str],
    default_code: int | None = 1,
    default: str | None = None,
    *args: Any,
    **kwargs: Any,
) -> str:
    """Analyze stdout/stderr logs to extract a user-friendly error summary."""
    full_text = "\n".join(logs).lower()

    # 1. Krea Moodboard rejection. Only trust the explicit "Moodboard Not Found"
    #    raised by KreaClient (it carries the moodboard ID + Krea's raw reply), and
    #    show that actual line so the Run Center tells you WHICH board and WHY.
    #    (The old rule also fired on any log that merely mentioned "moodboard"
    #    next to a "404", masking unrelated failures.)
    if "moodboard not found" in full_text:
        for line in reversed(logs):
            stripped = line.strip()
            if "moodboard not found" in stripped.lower():
                idx = stripped.lower().find("moodboard not found")
                return stripped[idx:idx + 500]
        return MOODBOARD_NOT_FOUND_MESSAGE

    # 1b. Krea API credit / balance depleted (HTTP 402)
    if "api balance is separate from your workspace compute balance" in full_text or (
        "krea" in full_text and ("402" in full_text or "balance" in full_text)
    ):
        return (
            "Krea API Error (402 Payment Required): Krea API balance is depleted. "
            "Please top up your API balance at krea.ai/api."
        )

    # 1c. Krea API authentication (HTTP 401)
    if "krea" in full_text and ("401" in full_text or "unauthorized" in full_text):
        return "Krea Auth Error: Check your KREA_API_TOKEN in .env or Railway variables."

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
                "ProviderError:",
                "content_automation.errors.ProviderError:",
                "AutomationError:",
                "content_automation.errors.AutomationError:",
                "ConfigurationError:",
                "content_automation.errors.ConfigurationError:",
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
        ) or (":" in stripped and any(stripped.split(":", 1)[0].endswith(err_name) for err_name in ("Error", "Exception"))):
            return stripped

    if default:
        return str(default)
    if "default" in kwargs and kwargs["default"]:
        return str(kwargs["default"])

    code = default_code if default_code is not None else 1
    return f"Process exited with non-zero code {code}"
