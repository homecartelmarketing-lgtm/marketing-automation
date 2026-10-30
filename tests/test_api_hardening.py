"""Security hardening for the Studio API surface.

Covers the deny-by-default gate (UI Control/api_server.py::require_api_auth),
the security headers, PIN clamping, and the max_items clamp on pipeline runs.
These build a tiny Flask app that registers the same hook + header functions
the real server uses, so the behaviour is verified without importing every
blueprint.
"""

from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask, jsonify, request

REPO_ROOT = Path(__file__).resolve().parents[1]
UI_CONTROL = REPO_ROOT / "UI Control"


def _load_common():
    if str(UI_CONTROL) not in sys.path:
        sys.path.insert(0, str(UI_CONTROL))
    return importlib.import_module("routes.common")


PUBLIC_API_PATHS = (
    "/api/health",
    "/api/auth/config",
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/me",
    "/api/auth/verify",
)


def _build_app(common):
    """Mirror of api_server.py's before_request gate + after_request headers."""
    app = Flask(__name__)
    from routes import studio_auth  # noqa: F401  (auth_mode referenced below)

    @app.before_request
    def require_api_auth():
        if request.method == "OPTIONS":
            return None
        path = request.path
        if not path.startswith("/api/"):
            return None
        for public in PUBLIC_API_PATHS:
            if path == public or path.startswith(public + "/"):
                return None
        if common.is_authorized(request):
            return None
        return (
            jsonify({"status": "error", "error": "Unauthorized", "auth_required": True}),
            401,
        )

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Content-Security-Policy",
            "frame-ancestors 'none'; base-uri 'self'; object-src 'none'",
        )
        return response

    @app.route("/api/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"})

    @app.route("/api/auth/config", methods=["GET"])
    def auth_config():
        return jsonify({"mode": "open"})

    @app.route("/api/rows", methods=["GET"])
    def rows():
        return jsonify({"rows": []})

    @app.route("/api/queue/status", methods=["GET"])
    def queue_status():
        return jsonify({"is_busy": False})

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def spa(path):
        return "spa"

    return app


class ApiHardeningTests(unittest.TestCase):
    def setUp(self):
        self.common = _load_common()
        self.app = _build_app(self.common)
        self.client = self.app.test_client()

    def test_public_paths_reachable_in_pin_mode(self):
        # With a PIN set (auth required), the auth flow + health must stay open.
        with patch.object(self.common, "DASHBOARD_PIN", "secret"):
            self.assertEqual(self.client.get("/api/health").status_code, 200)
            self.assertEqual(self.client.get("/api/auth/config").status_code, 200)
            # A non-allowlisted data route is now blocked by default.
            self.assertEqual(self.client.get("/api/rows").status_code, 401)
            self.assertEqual(self.client.get("/api/queue/status").status_code, 401)

    def test_data_routes_require_auth_when_pin_set(self):
        with patch.object(self.common, "DASHBOARD_PIN", "secret"):
            anon = self.client.get("/api/rows")
            self.assertEqual(anon.status_code, 401)
            self.assertEqual(anon.get_json()["auth_required"], True)
            ok = self.client.get("/api/rows", headers={"X-Dashboard-PIN": "secret"})
            self.assertEqual(ok.status_code, 200)

    def test_spa_and_static_are_not_gated(self):
        with patch.object(self.common, "DASHBOARD_PIN", "secret"):
            self.assertEqual(self.client.get("/").status_code, 200)
            self.assertEqual(self.client.get("/assets/app.js").status_code, 200)

    def test_options_preflight_passes_the_gate(self):
        with patch.object(self.common, "DASHBOARD_PIN", "secret"):
            resp = self.client.options("/api/rows")
            self.assertNotEqual(resp.status_code, 401)

    def test_open_mode_still_allows_data_routes(self):
        # No PIN and no accounts -> is_authorized() True -> unchanged behaviour.
        # accounts_enabled is forced False so a real users file on the host can't
        # flip this into account mode (open mode == no PIN AND no accounts).
        from routes import studio_auth
        with patch.object(self.common, "DASHBOARD_PIN", ""), patch.object(
            studio_auth, "accounts_enabled", return_value=False
        ):
            self.assertEqual(self.client.get("/api/rows").status_code, 200)

    def test_security_headers_present(self):
        resp = self.client.get("/")
        self.assertEqual(resp.headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(resp.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(resp.headers.get("Referrer-Policy"), "no-referrer")
        self.assertIn("frame-ancestors 'none'", resp.headers.get("Content-Security-Policy", ""))


class PinClampTests(unittest.TestCase):
    def setUp(self):
        self.common = _load_common()

    def test_clamp_pin_bounds_length(self):
        self.assertEqual(self.common.clamp_pin(None), "")
        self.assertEqual(self.common.clamp_pin(""), "")
        self.assertEqual(self.common.clamp_pin("abc"), "abc")
        long_pin = "x" * (self.common.MAX_PIN_LENGTH + 5000)
        self.assertEqual(len(self.common.clamp_pin(long_pin)), self.common.MAX_PIN_LENGTH)

    def test_oversized_pin_is_rejected_not_crashed(self):
        with patch.object(self.common, "DASHBOARD_PIN", "short"):
            huge = "z" * 100000
            self.assertFalse(self.common._check_pin(self.common.clamp_pin(huge)))

    def test_run_items_ceiling_is_ten(self):
        # Single documented ceiling for every /run + /enqueue max_items clamp.
        self.assertEqual(self.common.MAX_RUN_ITEMS, 10)

    def test_pin_in_query_string_is_rejected(self):
        # ?pin= must never authenticate: URLs leak into logs/history/Referer.
        with patch.object(self.common, "DASHBOARD_PIN", "secret"):
            req = SimpleNamespace(
                headers={},
                args={"pin": "secret"},
                is_json=False,
                get_json=lambda silent=True: {},
                remote_addr="127.0.0.2",
                host="studio.local",
                method="POST",
                path="/api/cta/run",
            )
            with self.assertRaises(ValueError):
                self.common._forbid_pin_in_query(req)
            # is_authorized refuses the request by raising (never authenticates
            # a query-string PIN).
            with self.assertRaises(ValueError):
                self.common.is_authorized(req)

    def test_security_headers_present_on_api_responses(self):
        app_client = _build_app(self.common).test_client()
        with patch.object(self.common, "DASHBOARD_PIN", "secret"):
            resp = app_client.get("/api/auth/config")
            self.assertEqual(resp.headers.get("X-Content-Type-Options"), "nosniff")
            self.assertEqual(resp.headers.get("X-Frame-Options"), "DENY")
            self.assertIn("frame-ancestors 'none'", resp.headers.get("Content-Security-Policy", ""))


class QueueEndpointSsrfTests(unittest.TestCase):
    """The queue worker POSTs client-supplied endpoints over loopback, so they
    must be plain same-host /api/ paths (no scheme/host/traversal -> no SSRF)."""

    def setUp(self):
        if str(UI_CONTROL) not in sys.path:
            sys.path.insert(0, str(UI_CONTROL))
        self.common = _load_common()
        self.qm = importlib.import_module("routes.queue_manager")

    def test_accepts_normal_api_paths(self):
        for good in (
            "/api/cta/run",
            "/api/queue/status",
            "/api/ad-cover/run",
            "/api/moodboard-2-feed/stop",
            # NOTE: "" is intentionally NOT accepted: the validator requires a
            # plain /api/ path, and the enqueue call site skips empty
            # stop_endpoint via `if endpoint and not ...` (queue_manager.py).
        ):
            self.assertTrue(self.qm._is_safe_local_endpoint(good), good)

    def test_rejects_off_loopback_and_malicious_paths(self):
        for bad in (
            "/api/run?x=http://evil.com",           # query smuggling
            "/api/run#@evil.com",                    # fragment/userinfo
            "http://evil.com/api/run",               # absolute URL
            "//evil.com/api/run",                    # protocol-relative
            "/api/../../etc/passwd",                 # traversal
            "/api/run @evil",                        # whitespace/host
            "/api/run\\evil",                        # backslash
            "not-an-api-path",                       # missing /api/ prefix
        ):
            self.assertFalse(self.qm._is_safe_local_endpoint(bad), bad)

    def test_enqueue_rejects_unsafe_endpoint_with_400(self):
        from flask import Flask

        app = Flask(__name__)
        app.register_blueprint(self.qm.queue_bp)
        # Force authorized so we exercise the validator, not the auth gate.
        with patch.object(self.qm, "is_authorized", return_value=True), patch.object(
            self.qm, "ensure_worker_started", lambda: None
        ):
            client = app.test_client()
            resp = client.post(
                "/api/queue/enqueue",
                json={
                    "pipeline_type": "cta_story",
                    "fixture_id": "chandelier",
                    "run_endpoint": "http://evil.com/steal",
                    "status_endpoint": "/api/cta/status",
                },
            )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("run_endpoint", resp.get_json()["error"])

    def test_dispatch_job_stop_derives_endpoint_from_run_endpoint(self):
        with patch.object(self.qm.urllib.request, "urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = b'{"status": "stopped"}'
            ok, msg = self.qm._dispatch_job_stop({
                "run_endpoint": "/api/day-night-feed/run",
            })
            self.assertTrue(ok)
            # Verify the request URL derived /stop
            req = mock_urlopen.call_args[0][0]
            self.assertTrue(req.full_url.endswith("/api/day-night-feed/stop"))
            self.assertEqual(req.headers.get("X-internal-token"), self.common.INTERNAL_TOKEN)

    def test_fetch_job_status_includes_internal_auth(self):
        with patch.object(self.qm.urllib.request, "urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = b'{"status": "running", "logs": []}'
            res = self.qm._fetch_job_status({
                "status_endpoint": "/api/day-night-feed/status",
            })
            self.assertEqual(res.get("status"), "running")
            req = mock_urlopen.call_args[0][0]
            self.assertTrue(req.full_url.endswith("/api/day-night-feed/status"))
            self.assertEqual(req.headers.get("X-internal-token"), self.common.INTERNAL_TOKEN)


class StudioUsersFilePermissionsTests(unittest.TestCase):
    """Password hashes must be written owner-only (0600) where the OS allows."""

    def setUp(self):
        self.common = _load_common()
        self.auth = importlib.import_module("routes.studio_auth")
        self.temp = tempfile.TemporaryDirectory()
        self.env_patch = patch.dict(
            os.environ,
            {
                "STUDIO_USERS_PATH": str(Path(self.temp.name) / "users.json"),
                "STUDIO_ADMIN_EMAIL": "",
                "STUDIO_ADMIN_PASSWORD": "",
                "DATABASE_URL": "",
                "POSTGRES_URL": "",
            },
        )
        self.env_patch.start()

    def tearDown(self):
        self.env_patch.stop()
        self.temp.cleanup()

    def test_write_hardens_permissions_and_roundtrips(self):
        from werkzeug.security import check_password_hash

        self.auth.add_user("editor@homecartel.net", "correct horse battery")
        path = Path(self.temp.name) / "users.json"
        self.assertTrue(path.exists())
        # Content still round-trips after the permission hardening.
        stored = self.auth._read_file_users()["editor@homecartel.net"]
        self.assertTrue(check_password_hash(stored["password_hash"], "correct horse battery"))
        if os.name == "posix":
            mode = path.stat().st_mode & 0o777
            self.assertEqual(mode, 0o600, oct(mode))


if __name__ == "__main__":
    unittest.main()
