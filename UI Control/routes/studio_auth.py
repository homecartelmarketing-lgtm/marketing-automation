"""Studio accounts: email + password login backed by a Flask session cookie.

Users live in a small JSON file (``STUDIO_USERS_PATH``, default
``output/studio_users.json``) and are managed by an admin with
``scripts/ops/manage_studio_users.py``. ``STUDIO_ADMIN_EMAIL`` +
``STUDIO_ADMIN_PASSWORD`` seed one in-memory admin so a wiped container disk can
never lock everyone out. ``routes.common.is_authorized`` accepts a valid session,
so the pipeline routes need no changes.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Blueprint, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from . import common
from .common import (
    MARKETING_DIR,
    clear_failed_attempts,
    is_rate_limited,
    record_failed_attempt,
)

auth_bp = Blueprint("studio_auth", __name__)

MIN_PASSWORD_LENGTH = 8
DEFAULT_MAX_ACCOUNTS = 1
VALID_ROLES = ("admin", "user")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_SESSION_KEY = "studio_user"

_USERS_LOCK = threading.Lock()
_SEED_CACHE: dict[str, Any] = {}
# Checked for unknown emails so a miss takes as long as a wrong password.
_DUMMY_HASH = generate_password_hash(secrets.token_urlsafe(16))


def _users_path() -> Path:
    default = MARKETING_DIR / "output" / "studio_users.json"
    return Path(os.getenv("STUDIO_USERS_PATH", "").strip() or default)


def normalize_email(email: Any) -> str:
    return str(email or "").strip().lower()


def _read_file_users() -> dict[str, dict[str, Any]]:
    path = _users_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    users = data.get("users") if isinstance(data, dict) else None
    if not isinstance(users, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for record in users:
        if isinstance(record, dict) and record.get("email") and record.get("password_hash"):
            result[normalize_email(record["email"])] = record
    return result


def _seed_user() -> dict[str, Any] | None:
    """Env-provided admin. STUDIO_ADMIN_PASSWORD_HASH (from `manage_studio_users.py env`) keeps
    the plaintext password out of Railway; STUDIO_ADMIN_PASSWORD is the simpler alternative."""
    email = normalize_email(os.getenv("STUDIO_ADMIN_EMAIL"))
    password = os.getenv("STUDIO_ADMIN_PASSWORD", "")
    password_hash = os.getenv("STUDIO_ADMIN_PASSWORD_HASH", "").strip()
    if not email or not (password or password_hash):
        return None
    key = f"{email}\0{password}\0{password_hash}"
    if _SEED_CACHE.get("key") != key:
        _SEED_CACHE["key"] = key
        _SEED_CACHE["record"] = {
            "email": email,
            "password_hash": password_hash or generate_password_hash(password),
            "role": "admin",
            "seeded": True,
        }
    return _SEED_CACHE["record"]


def load_users() -> dict[str, dict[str, Any]]:
    """All accounts keyed by lower-cased email (file users, plus the env-seeded admin)."""
    with _USERS_LOCK:
        users = _read_file_users()
    seed = _seed_user()
    if seed and seed["email"] not in users:
        users[seed["email"]] = seed
    return users


def accounts_enabled() -> bool:
    return bool(load_users())


def max_accounts() -> int:
    """How many accounts may exist (STUDIO_MAX_ACCOUNTS, default 1: one shared team login)."""
    try:
        return max(int(os.getenv("STUDIO_MAX_ACCOUNTS", str(DEFAULT_MAX_ACCOUNTS))), 1)
    except ValueError:
        return DEFAULT_MAX_ACCOUNTS


def accounts_full() -> bool:
    return len(load_users()) >= max_accounts()


def auth_mode() -> str:
    if accounts_enabled():
        return "accounts"
    # Read through the module so tests that patch common.DASHBOARD_PIN are honored.
    return "pin" if common.DASHBOARD_PIN else "open"


def _write_file_users(users: dict[str, dict[str, Any]]) -> None:
    path = _users_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    records = [u for u in users.values() if not u.get("seeded")]
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps({"users": records}, indent=2), encoding="utf-8")
    tmp.replace(path)


def add_user(email: str, password: str, role: str = "user") -> dict[str, Any]:
    email = normalize_email(email)
    if not _EMAIL_RE.match(email):
        raise ValueError("Enter a valid email address.")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if role not in VALID_ROLES:
        raise ValueError(f"Role must be one of: {', '.join(VALID_ROLES)}.")
    with _USERS_LOCK:
        users = _read_file_users()
        if email in users:
            raise ValueError(f"{email} already exists.")
    if accounts_full():
        limit = max_accounts()
        raise ValueError(
            f"This Studio is limited to {limit} account{'s' if limit != 1 else ''}. "
            "Use set-password to change the login, or raise STUDIO_MAX_ACCOUNTS."
        )
    with _USERS_LOCK:
        users = _read_file_users()
        users[email] = {
            "email": email,
            "password_hash": generate_password_hash(password),
            "role": role,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        _write_file_users(users)
        return users[email]


def set_password(email: str, password: str) -> None:
    email = normalize_email(email)
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    with _USERS_LOCK:
        users = _read_file_users()
        if email not in users:
            raise ValueError(f"No such user: {email}")
        users[email]["password_hash"] = generate_password_hash(password)
        _write_file_users(users)


def remove_user(email: str) -> None:
    email = normalize_email(email)
    with _USERS_LOCK:
        users = _read_file_users()
        if email not in users:
            raise ValueError(f"No such user: {email}")
        del users[email]
        _write_file_users(users)


def verify_credentials(email: str, password: str) -> dict[str, Any] | None:
    record = load_users().get(normalize_email(email))
    if record is None:
        check_password_hash(_DUMMY_HASH, password)
        return None
    try:
        matches = check_password_hash(record["password_hash"], password)
    except ValueError:  # malformed hash in the env var or file
        return None
    return record if matches else None


def _public_user(record: dict[str, Any]) -> dict[str, str]:
    return {"email": record["email"], "role": record.get("role", "user")}


def current_user() -> dict[str, str] | None:
    """The logged-in user for this request, or None. Removing an account ends its sessions."""
    try:
        email = session.get(_SESSION_KEY)
    except RuntimeError:  # no request context
        return None
    if not email:
        return None
    record = load_users().get(normalize_email(email))
    return _public_user(record) if record else None


def _secret_key() -> str:
    configured = os.getenv("STUDIO_SECRET_KEY", "").strip()
    if configured:
        return configured
    key_file = MARKETING_DIR / "output" / ".studio_secret_key"
    try:
        if key_file.exists():
            stored = key_file.read_text(encoding="utf-8").strip()
            if stored:
                return stored
        key_file.parent.mkdir(parents=True, exist_ok=True)
        generated = secrets.token_hex(32)
        key_file.write_text(generated, encoding="utf-8")
        return generated
    except OSError:
        # Read-only disk: sessions then last until the next restart.
        return secrets.token_hex(32)


def init_app(app) -> None:
    """Configure cookie sessions on the Flask app."""
    from datetime import timedelta

    try:
        hours = float(os.getenv("STUDIO_SESSION_HOURS", "12"))
    except ValueError:
        hours = 12.0
    app.secret_key = _secret_key()
    app.config.update(
        SESSION_COOKIE_NAME="hc_studio_session",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("STUDIO_COOKIE_SECURE", "").strip().lower() in ("1", "true", "yes"),
        PERMANENT_SESSION_LIFETIME=timedelta(hours=max(hours, 0.1)),
    )


def auth_state() -> dict[str, Any]:
    mode = auth_mode()
    user = current_user()
    return {
        "mode": mode,
        "auth_required": mode != "open",
        # False once the account limit is reached, so the login screen hides "Sign Up".
        "can_request_access": not accounts_full(),
        "authenticated": user is not None,
        "user": user,
    }


@auth_bp.route("/api/auth/me", methods=["GET"])
def auth_me():
    return jsonify(auth_state())


@auth_bp.route("/api/auth/login", methods=["POST"])
def auth_login():
    if not accounts_enabled():
        return jsonify({"ok": False, "error": "Accounts are not set up on this Studio."}), 400

    client_ip = getattr(request, "remote_addr", None) or "unknown"
    if is_rate_limited(client_ip):
        return jsonify({
            "ok": False,
            "error": "Too many failed attempts. Temporary lockout active (5 minutes).",
        }), 429

    data = request.get_json(silent=True) or {}
    email = normalize_email(data.get("email"))
    password = str(data.get("password") or "")
    if not email or not password:
        return jsonify({"ok": False, "error": "Enter your email and password."}), 400

    record = verify_credentials(email, password)
    if record is None:
        record_failed_attempt(client_ip)
        return jsonify({"ok": False, "error": "Incorrect email or password."}), 401

    clear_failed_attempts(client_ip)
    session.clear()
    session[_SESSION_KEY] = record["email"]
    session.permanent = True
    return jsonify({"ok": True, "user": _public_user(record)})


@auth_bp.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    session.clear()
    return jsonify({"ok": True})
