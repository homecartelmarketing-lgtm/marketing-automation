#!/usr/bin/env python
"""HomeCartel Marketing Studio - Unified All-in-One API & Web UI Server.

Entrypoint server registering modular Flask Blueprints:
- CTA Story: /api/cta/* (routes/cta_story.py)
- Tips & Educational Story: /api/tips-edu/* (routes/tips_edu_story.py)
- Static Frontend SPA Serving from dist/
"""

from __future__ import annotations

import hmac
import os
from pathlib import Path
import sys

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix

# Resolve paths
CURRENT_DIR = Path(__file__).resolve().parent
MARKETING_DIR = CURRENT_DIR.parent
DIST_DIR = CURRENT_DIR / "dist"

if str(MARKETING_DIR) not in sys.path:
    sys.path.insert(0, str(MARKETING_DIR))
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from routes.common import DASHBOARD_PIN, clamp_pin, is_authorized
from routes.cta_story import cta_bp
from routes.tips_edu_story import tips_edu_bp
from routes.collection_story import collection_story_bp
from routes.product_specs_story import product_specs_bp
from routes.style_this_story import style_this_bp
from routes.one_product_three_styles_feed import one_product_three_styles_bp
from routes.day_night_story import day_night_story_bp
from routes.moodboard_story import moodboard_story_bp
from routes.myth_fact_story import myth_fact_story_bp
from routes.product_description_story import product_description_story_bp
from routes.this_or_that_story import this_or_that_story_bp
from routes.tips_edu_feed import tips_edu_feed_bp
from routes.collection_feed import collection_feed_bp
from routes.moodboard_1_feed import moodboard_1_feed_bp
from routes.moodboard_2_feed import moodboard_2_feed_bp
from routes.day_night_feed import day_night_feed_bp
from routes.product_showcase_feed import product_showcase_feed_bp
from routes.product_closeup_reel import product_closeup_reel_bp
from routes.day_night_reel import day_night_reel_bp
from routes.before_after_reel import before_after_reel_bp
from routes.style_reel_slideshow import style_reel_slideshow_bp
from routes.moodboard_reel import moodboard_reel_bp
from routes.one_product_three_styles_reel import one_product_three_styles_reel_bp
from routes.one_at_a_time_lights_reel import one_at_a_time_lights_reel_bp
from routes.room_build_up_reel import room_build_up_reel_bp
from routes.house_tour_reel import house_tour_reel_bp
from routes.this_mood_every_night_reel import this_mood_every_night_reel_bp
from routes.sketch_to_draw_reel import sketch_to_draw_reel_bp
from routes.virtual_staging_reel import virtual_staging_reel_bp
from routes.ad_cover import ad_cover_bp
from routes.christmas_banner import christmas_banner_bp
from routes.sale_banner import sale_banner_bp
from routes.rows import rows_bp
from routes.queue_manager import queue_bp, set_server_port
from routes.calendar import calendar_bp
from routes import studio_auth

app = Flask(
    __name__,
    static_folder=str(DIST_DIR / "assets") if (DIST_DIR / "assets").exists() else None,
    static_url_path="/assets",
)

# Email + password login (cookie session) for the Studio
studio_auth.init_app(app)
app.register_blueprint(studio_auth.auth_bp)

# Behind Railway (and any reverse proxy) request.remote_addr is the proxy's IP,
# not the user's. The lockout/rate-limit in routes.common keys on remote_addr, so
# without ProxyFix a single attacker's 10 bad guesses lock out *every* user behind
# the shared proxy IP. Trust X-Forwarded-For for exactly one hop (the platform's
# edge proxy). This is a no-op on the local dev server and the Cloudflare tunnel,
# where remote_addr is already the real client.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=0, x_port=0, x_prefix=0)

# Register modular Blueprints
app.register_blueprint(cta_bp)
app.register_blueprint(tips_edu_bp)
app.register_blueprint(collection_story_bp)
app.register_blueprint(product_specs_bp)
app.register_blueprint(style_this_bp)
app.register_blueprint(one_product_three_styles_bp)
app.register_blueprint(day_night_story_bp)
app.register_blueprint(moodboard_story_bp)
app.register_blueprint(myth_fact_story_bp)
app.register_blueprint(product_description_story_bp)
app.register_blueprint(this_or_that_story_bp)
app.register_blueprint(tips_edu_feed_bp)
app.register_blueprint(collection_feed_bp)
app.register_blueprint(moodboard_1_feed_bp)
app.register_blueprint(moodboard_2_feed_bp)
app.register_blueprint(day_night_feed_bp)
app.register_blueprint(product_showcase_feed_bp)
app.register_blueprint(product_closeup_reel_bp)
app.register_blueprint(day_night_reel_bp)
app.register_blueprint(before_after_reel_bp)
app.register_blueprint(style_reel_slideshow_bp)
app.register_blueprint(moodboard_reel_bp)
app.register_blueprint(one_product_three_styles_reel_bp)
app.register_blueprint(one_at_a_time_lights_reel_bp)
app.register_blueprint(room_build_up_reel_bp)
app.register_blueprint(house_tour_reel_bp)
app.register_blueprint(this_mood_every_night_reel_bp)
app.register_blueprint(sketch_to_draw_reel_bp)
app.register_blueprint(virtual_staging_reel_bp)
app.register_blueprint(ad_cover_bp)
app.register_blueprint(christmas_banner_bp)
app.register_blueprint(sale_banner_bp)
app.register_blueprint(rows_bp)
app.register_blueprint(queue_bp)
app.register_blueprint(calendar_bp)


# Public endpoints reachable without a session. Keep this list minimal.
#   /api/health         - liveness probe (no data)
#   /api/auth/*         - login / logout / me / config / verify (the auth flow itself)
# Everything else under /api/* requires authentication (see require_api_auth below).
PUBLIC_API_PATHS = (
    "/api/health",
    "/api/auth/config",
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/me",
    "/api/auth/verify",
)

# Optional service token so an external liveness/uptime probe can hit /api/health
# and receive a truthful status even when the Studio requires auth. Leave empty to
# keep /api/health fully open (it leaks nothing beyond uptime + build presence).
HEALTHCHECK_TOKEN = os.getenv("HEALTHCHECK_TOKEN", "").strip()

# Hard cap on incoming request bodies (the largest legitimate uploads are small
# XLSX calendar files). Prevents memory-exhaustion via huge JSON/image payloads.
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_CONTENT_LENGTH", str(64 * 1024 * 1024)))  # 64 MiB


@app.before_request
def require_api_auth():
    """Block-by-default gate for /api/*.

    Unauthenticated access is allowed only for the explicit PUBLIC_API_PATHS
    allowlist and CORS preflight (OPTIONS). Everything else falls through to the
    per-route is_authorized() checks, so in open mode (no PIN and no accounts)
    is_authorized() returns True and the Studio behaves exactly as before.
    """
    if request.method == "OPTIONS":
        return None  # preflight is handled by add_cors_headers
    path = request.path
    if not path.startswith("/api/"):
        return None  # SPA/static routes are served by serve_frontend
    for public in PUBLIC_API_PATHS:
        if path == public or path.startswith(public + "/"):
            return None
    if path == "/api/health":
        token = request.args.get("token", "").strip()
        if HEALTHCHECK_TOKEN and token and hmac.compare_digest(token, HEALTHCHECK_TOKEN):
            return None
    if is_authorized(request):
        return None
    return (
        jsonify(
            {
                "status": "error",
                "error": "Unauthorized",
                "auth_required": True,
                "mode": studio_auth.auth_mode(),
            }
        ),
        401,
    )


@app.after_request
def add_security_headers(response):
    """Clickjacking / MIME-sniffing / referrer hardening on every response."""
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault(
        "X-Frame-Options", "DENY"
    )  # frames are not used anywhere -> deny is safe
    response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
    response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
    response.headers.setdefault(
        "Content-Security-Policy",
        "frame-ancestors 'none'; base-uri 'self'; object-src 'none'",
    )
    return response


@app.errorhandler(OSError)
@app.errorhandler(RuntimeError)
@app.errorhandler(ValueError)
@app.errorhandler(500)
@app.errorhandler(Exception)
def report_studio_error(error):
    """Give all unhandled exceptions a JSON response the UI can display."""
    return jsonify({"status": "error", "error": str(error)}), 500


@app.errorhandler(404)
def handle_not_found(error):
    if request.path.startswith("/api/"):
        return jsonify({"status": "error", "error": f"API endpoint not found: {request.path}"}), 404
    if (DIST_DIR / "index.html").exists():
        return send_from_directory(DIST_DIR, "index.html")
    return jsonify({"status": "error", "error": "Page not found"}), 404


@app.errorhandler(405)
def handle_method_not_allowed(error):
    return jsonify({"status": "error", "error": f"Method {request.method} not allowed on {request.path}"}), 405


@app.after_request
def add_cors_headers(response):
    allowed = os.getenv("ALLOWED_ORIGINS", "").strip()
    if allowed:
        origins = [o.strip() for o in allowed.split(",") if o.strip()]
        req_origin = request.headers.get("Origin", "")
        if req_origin in origins:
            response.headers["Access-Control-Allow-Origin"] = req_origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        elif "*" in origins:
            response.headers["Access-Control-Allow-Origin"] = "*"
    else:
        # No allowlist configured -> same-origin only. We intentionally do NOT
        # emit Access-Control-Allow-Origin, so browsers block cross-origin use
        # with credentials. Set ALLOWED_ORIGINS (comma-separated, or "*") to opt
        # into cross-origin access.
        pass

    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Dashboard-PIN"
    return response


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "homecartel-marketing-studio",
        "auth_required": studio_auth.auth_mode() != "open",
        "dist_exists": DIST_DIR.exists(),
        "modules": [
            "cta_story",
            "tips_edu_story",
            "collection_story",
            "day_night_story",
            "moodboard_story",
            "product_specs_story",
            "style_this_story",
            "myth_fact_story",
            "product_description_story",
            "this_or_that_story",
            "one_product_three_styles_feed",
            "tips_edu_feed",
            "collection_feed",
            "moodboard_1_feed",
            "moodboard_2_feed",
            "day_night_feed",
            "product_showcase_feed",
            "product_closeup_reel",
            "day_night_reel",
            "before_after_reel",
            "style_reel_slideshow",
            "moodboard_reel",
            "one_product_three_styles_reel",
            "one_at_a_time_lights_reel",
            "room_build_up_reel",
            "house_tour_reel",
            "this_mood_every_night_reel",
            "sketch_to_draw_reel",
            "virtual_staging_reel",
            "ad_cover",
            "christmas_banner",
            "sale_banner",
        ],
    })


@app.route("/api/auth/config", methods=["GET"])
def auth_config():
    """Return whether authentication is required and which kind (accounts | pin | open)."""
    mode = studio_auth.auth_mode()
    return jsonify({
        "auth_required": mode != "open",
        "mode": mode,
    })


@app.route("/api/auth/verify", methods=["POST"])
def auth_verify():
    """Verify user PIN with timing-safe comparison and rate limiting."""
    if not DASHBOARD_PIN:
        return jsonify({"valid": True, "auth_required": False})

    from routes.common import clamp_pin
    from routes.common import _check_pin, clear_failed_attempts, is_rate_limited, record_failed_attempt

    client_ip = getattr(request, "remote_addr", None) or "unknown"
    if is_rate_limited(client_ip):
        return jsonify({
            "valid": False,
            "auth_required": True,
            "error": "Too many failed attempts. Temporary lockout active (5 minutes).",
        }), 429

    data = request.get_json(silent=True) or {}
    pin = clamp_pin(str(data.get("pin", "")).strip())
    if _check_pin(pin):
        clear_failed_attempts(client_ip)
        return jsonify({"valid": True, "auth_required": True})

    record_failed_attempt(client_ip)
    return jsonify({"valid": False, "auth_required": True, "error": "Invalid Studio Security PIN"}), 401


@app.route("/api/tunnel/status", methods=["GET"])
def tunnel_status():
    """Return whether a Cloudflare Tunnel is active and its public URL."""
    tunnel_file = MARKETING_DIR / "output" / "public_tunnel_url.txt"
    url = ""
    if tunnel_file.exists():
        try:
            url = tunnel_file.read_text(encoding="utf-8").strip()
        except Exception:
            url = ""
    return jsonify({
        "active": bool(url),
        "public_url": url,
    })


@app.route("/api/maintenance/cleanup", methods=["POST"])
def maintenance_cleanup():
    """Trigger scratchpad cleanup for temporary files in containerized hosting.

    Requires the same authorization as any other /api route. `hours` is clamped to a
    safe minimum so a zero/negative value can never delete files a running job is
    actively using.
    """
    if not is_authorized(request):
        return jsonify({"status": "error", "error": "Unauthorized"}), 401
    try:
        from content_automation.cleanup import prune_scratchpad
        try:
            hours = float(request.values.get("hours", 12.0))
        except (TypeError, ValueError):
            return jsonify({"status": "error", "error": "hours must be a number"}), 400
        hours = max(hours, 1.0)  # never prune anything younger than 1 hour
        result = prune_scratchpad(max_age_hours=hours)
        return jsonify(result)
    except Exception as err:
        return jsonify({"status": "error", "error": str(err)}), 500


# SPA Catch-all Route: Serve compiled React App from UI Control/dist
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path: str):
    if path.startswith("api/"):
        return jsonify({"error": f"API endpoint not found: /{path}"}), 404

    target = DIST_DIR / path
    if path and target.exists() and target.is_file():
        return send_from_directory(DIST_DIR, path)

    if (DIST_DIR / "index.html").exists():
        return send_from_directory(DIST_DIR, "index.html")

    return (
        "<html><body style='font-family:sans-serif;padding:40px;text-align:center;'>"
        "<h2>HomeCartel Marketing Studio API</h2>"
        "<p>Backend is active. Frontend build not found in <code>dist/</code>.</p>"
        "<p>Run <code>pnpm run build</code> inside <code>UI Control/</code> to compile the frontend.</p>"
        "</body></html>"
    )


if __name__ == "__main__":
    # Support Zoho Catalyst AppSail dynamic port ($X_ZOHO_CATALYST_LISTEN_PORT) with fallback to $PORT or 5200
    port_env = os.environ.get("X_ZOHO_CATALYST_LISTEN_PORT") or os.environ.get("PORT") or "5200"
    port = int(port_env)
    set_server_port(port)
    host = os.environ.get("HOST", "0.0.0.0")
    print(f"Starting HomeCartel All-in-One Studio on http://{host}:{port}")
    print(f"  Root Dir : {MARKETING_DIR}")
    print(f"  Dist Dir : {DIST_DIR} (exists: {DIST_DIR.exists()})")
    print(f"  Auth     : {studio_auth.auth_mode().upper()} (accounts | pin | open)")
    print(f"  Blueprints: 10 Story blueprints + 7 Feed blueprints + 7 Reel blueprints + rows inspector (/api/rows)")
    app.run(host=host, port=port, debug=False, threaded=True)
