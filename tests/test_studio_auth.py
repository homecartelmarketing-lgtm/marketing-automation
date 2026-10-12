"""Unit tests for Studio email + password login (routes/studio_auth.py)."""

from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask, jsonify, request

PASSWORD = "correct horse battery"


class StudioAuthTests(unittest.TestCase):
    def setUp(self):
        routes_dir = Path(__file__).resolve().parents[1] / "UI Control"
        if str(routes_dir) not in sys.path:
            sys.path.insert(0, str(routes_dir))
        self.common = importlib.import_module("routes.common")
        self.auth = importlib.import_module("routes.studio_auth")

        self.temp = tempfile.TemporaryDirectory()
        env = {
            "STUDIO_USERS_PATH": str(Path(self.temp.name) / "users.json"),
            "STUDIO_SECRET_KEY": "test-secret",
            "STUDIO_ADMIN_EMAIL": "",
            "STUDIO_ADMIN_PASSWORD": "",
            "STUDIO_MAX_ACCOUNTS": "10",  # most tests need several accounts; the cap has its own tests
        }
        self.env_patch = patch.dict(os.environ, env)
        self.env_patch.start()
        self.pin_patch = patch.object(self.common, "DASHBOARD_PIN", "")
        self.pin_patch.start()
        self.common._FAILED_ATTEMPTS.clear()

        self.app = Flask(__name__)
        self.auth.init_app(self.app)
        self.app.register_blueprint(self.auth.auth_bp)

        @self.app.route("/protected", methods=["POST"])
        def protected():
            if not self.common.is_authorized(request):
                return jsonify({"error": "Unauthorized"}), 401
            return jsonify({"ok": True})

        self.client = self.app.test_client()

    def tearDown(self):
        self.common._FAILED_ATTEMPTS.clear()
        self.pin_patch.stop()
        self.env_patch.stop()
        self.temp.cleanup()

    def _login(self, email="Editor@HomeCartel.net", password=PASSWORD):
        return self.client.post("/api/auth/login", json={"email": email, "password": password})

    def test_open_mode_when_no_pin_and_no_accounts(self):
        self.assertEqual(self.client.get("/api/auth/me").get_json()["mode"], "open")
        self.assertEqual(self.client.post("/protected").status_code, 200)

    def test_login_success_sets_session_and_authorizes(self):
        self.auth.add_user("editor@homecartel.net", PASSWORD)
        self.assertEqual(self.client.post("/protected").status_code, 401)

        response = self._login()  # email is case-insensitive
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["user"]["email"], "editor@homecartel.net")

        me = self.client.get("/api/auth/me").get_json()
        self.assertTrue(me["authenticated"])
        self.assertEqual(me["mode"], "accounts")
        self.assertEqual(self.client.post("/protected").status_code, 200)

        cookie = response.headers.get("Set-Cookie", "")
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)

    def test_logout_ends_session(self):
        self.auth.add_user("editor@homecartel.net", PASSWORD)
        self._login()
        self.client.post("/api/auth/logout")
        self.assertFalse(self.client.get("/api/auth/me").get_json()["authenticated"])
        self.assertEqual(self.client.post("/protected").status_code, 401)

    def test_wrong_password_and_unknown_email_share_one_error(self):
        self.auth.add_user("editor@homecartel.net", PASSWORD)
        wrong = self._login(password="not the password")
        unknown = self._login(email="nobody@homecartel.net")
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(unknown.status_code, 401)
        self.assertEqual(wrong.get_json()["error"], unknown.get_json()["error"])
        self.assertFalse(self.client.get("/api/auth/me").get_json()["authenticated"])

    def test_missing_fields_rejected(self):
        self.auth.add_user("editor@homecartel.net", PASSWORD)
        response = self.client.post("/api/auth/login", json={"email": "editor@homecartel.net"})
        self.assertEqual(response.status_code, 400)

    def test_lockout_after_repeated_failures(self):
        self.auth.add_user("editor@homecartel.net", PASSWORD)
        for _ in range(self.common.MAX_FAILED_ATTEMPTS):
            self.assertEqual(self._login(password="nope").status_code, 401)
        # Even the right password is refused while locked out.
        self.assertEqual(self._login().status_code, 429)

    def test_removing_account_ends_its_session(self):
        self.auth.add_user("editor@homecartel.net", PASSWORD)
        self.auth.add_user("other@homecartel.net", PASSWORD)
        self._login()
        self.auth.remove_user("editor@homecartel.net")
        self.assertEqual(self.client.post("/protected").status_code, 401)

    def test_passwords_are_hashed_on_disk(self):
        self.auth.add_user("editor@homecartel.net", PASSWORD)
        stored = Path(os.environ["STUDIO_USERS_PATH"]).read_text(encoding="utf-8")
        self.assertNotIn(PASSWORD, stored)

    def test_add_user_validation(self):
        with self.assertRaises(ValueError):
            self.auth.add_user("not-an-email", PASSWORD)
        with self.assertRaises(ValueError):
            self.auth.add_user("editor@homecartel.net", "short")
        self.auth.add_user("editor@homecartel.net", PASSWORD)
        with self.assertRaises(ValueError):
            self.auth.add_user("EDITOR@homecartel.net", PASSWORD)

    def test_env_seeded_admin_can_log_in_without_a_users_file(self):
        with patch.dict(os.environ, {"STUDIO_ADMIN_EMAIL": "boss@homecartel.net", "STUDIO_ADMIN_PASSWORD": PASSWORD}):
            self.assertEqual(self._login(email="boss@homecartel.net").status_code, 200)
            self.assertFalse(Path(os.environ["STUDIO_USERS_PATH"]).exists())

    def test_env_seeded_admin_from_password_hash(self):
        self.auth.add_user("owner@homecartel.net", PASSWORD)
        stored = self.auth.load_users()["owner@homecartel.net"]["password_hash"]
        Path(os.environ["STUDIO_USERS_PATH"]).unlink()  # a fresh deploy has no accounts file
        env = {"STUDIO_ADMIN_EMAIL": "owner@homecartel.net", "STUDIO_ADMIN_PASSWORD_HASH": stored}
        with patch.dict(os.environ, env):
            self.assertEqual(self._login(email="owner@homecartel.net").status_code, 200)
            self.assertEqual(self._login(email="owner@homecartel.net", password="wrong password").status_code, 401)

    def test_malformed_password_hash_does_not_crash_login(self):
        env = {"STUDIO_ADMIN_EMAIL": "owner@homecartel.net", "STUDIO_ADMIN_PASSWORD_HASH": "not-a-hash"}
        with patch.dict(os.environ, env):
            self.assertEqual(self._login(email="owner@homecartel.net").status_code, 401)

    def test_internal_token_authorizes_loopback_calls(self):
        self.auth.add_user("editor@homecartel.net", PASSWORD)
        good = self.client.post("/protected", headers=self.common.internal_auth_headers())
        bad = self.client.post("/protected", headers={self.common.INTERNAL_TOKEN_HEADER: "guess"})
        self.assertEqual(good.status_code, 200)
        self.assertEqual(bad.status_code, 401)

    def test_pin_mode_and_pin_header_still_work(self):
        with patch.object(self.common, "DASHBOARD_PIN", "secret"):
            me = self.client.get("/api/auth/me").get_json()
            self.assertEqual(me["mode"], "pin")
            self.assertTrue(me["auth_required"])
            self.assertEqual(self.client.post("/protected").status_code, 401)
            ok = self.client.post("/protected", headers={"X-Dashboard-PIN": "secret"})
            self.assertEqual(ok.status_code, 200)

    def test_pin_header_still_works_alongside_accounts(self):
        self.auth.add_user("editor@homecartel.net", PASSWORD)
        with patch.object(self.common, "DASHBOARD_PIN", "secret"):
            ok = self.client.post("/protected", headers={"Authorization": "Bearer secret"})
            self.assertEqual(ok.status_code, 200)

    def test_default_limit_is_one_account(self):
        with patch.dict(os.environ, {"STUDIO_MAX_ACCOUNTS": ""}):
            self.assertEqual(self.auth.max_accounts(), 1)
            self.assertTrue(self.client.get("/api/auth/me").get_json()["can_request_access"])
            self.auth.add_user("owner@homecartel.net", PASSWORD)
            with self.assertRaises(ValueError) as ctx:
                self.auth.add_user("second@homecartel.net", PASSWORD)
            self.assertIn("limited to 1 account", str(ctx.exception))
            self.assertFalse(self.client.get("/api/auth/me").get_json()["can_request_access"])
            # The one account still works and can change its password.
            self.auth.set_password("owner@homecartel.net", "a brand new password")
            self.assertEqual(self._login(email="owner@homecartel.net", password="a brand new password").status_code, 200)

    def test_env_seeded_admin_counts_toward_the_limit(self):
        env = {"STUDIO_MAX_ACCOUNTS": "1", "STUDIO_ADMIN_EMAIL": "boss@homecartel.net", "STUDIO_ADMIN_PASSWORD": PASSWORD}
        with patch.dict(os.environ, env):
            with self.assertRaises(ValueError):
                self.auth.add_user("second@homecartel.net", PASSWORD)

    def test_limit_can_be_raised(self):
        with patch.dict(os.environ, {"STUDIO_MAX_ACCOUNTS": "2"}):
            self.auth.add_user("a@homecartel.net", PASSWORD)
            self.auth.add_user("b@homecartel.net", PASSWORD)
            with self.assertRaises(ValueError):
                self.auth.add_user("c@homecartel.net", PASSWORD)

    def test_login_refused_when_no_accounts_exist(self):
        self.assertEqual(self._login().status_code, 400)


if __name__ == "__main__":
    unittest.main()
