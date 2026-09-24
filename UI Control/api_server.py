#!/usr/bin/env python
"""HomeCartel Marketing Studio - Unified All-in-One API & Web UI Server.

Entrypoint server registering modular Flask Blueprints:
- CTA Story: /api/cta/* (routes/cta_story.py)
- Tips & Educational Story: /api/tips-edu/* (routes/tips_edu_story.py)
- Static Frontend SPA Serving from dist/
"""

from __future__ import annotations

import os
from pathlib import Path
import sys

from flask import Flask, jsonify, request, send_from_directory

# Resolve paths
CURRENT_DIR = Path(__file__).resolve().parent
MARKETING_DIR = CURRENT_DIR.parent
DIST_DIR = CURRENT_DIR / "dist"

if str(MARKETING_DIR) not in sys.path:
    sys.path.insert(0, str(MARKETING_DIR))
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from routes.common import DASHBOARD_PIN, is_authorized
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
from routes.ad_cover import ad_cover_bp
from routes.rows import rows_bp
from routes.queue_manager import queue_bp, set_server_port

app = Flask(
    __name__,
    static_folder=str(DIST_DIR / "assets") if (DIST_DIR / "assets").exists() else None,
    static_url_path="/assets",
)

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
app.register_blueprint(ad_cover_bp)
app.register_blueprint(rows_bp)
app.register_blueprint(queue_bp)


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
        response.headers["Access-Control-Allow-Origin"] = "*"

    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Dashboard-PIN"
    return response


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "homecartel-marketing-studio",
        "auth_required": bool(DASHBOARD_PIN),
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
        ],
    })


@app.route("/api/auth/config", methods=["GET"])
def auth_config():
    """Return whether PIN authentication is required."""
    return jsonify({
        "auth_required": bool(DASHBOARD_PIN),
    })


@app.route("/api/auth/verify", methods=["POST"])
def auth_verify():
    """Verify user PIN."""
    if not DASHBOARD_PIN:
        return jsonify({"valid": True, "auth_required": False})

    data = request.get_json(silent=True) or {}
    pin = str(data.get("pin", "")).strip()
    if pin == DASHBOARD_PIN:
        return jsonify({"valid": True, "auth_required": True})
    return jsonify({"valid": False, "auth_required": True, "error": "Invalid PIN"}), 401


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


@app.route("/api/maintenance/cleanup", methods=["GET", "POST"])
def maintenance_cleanup():
    """Trigger scratchpad cleanup for temporary files in containerized hosting."""
    try:
        from content_automation.cleanup import prune_scratchpad
        hours = float(request.args.get("hours", 12.0))
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
    print(f"  PIN Auth : {'ENABLED' if DASHBOARD_PIN else 'DISABLED (Open)'}")
    print(f"  Blueprints: 10 Story blueprints + 7 Feed blueprints + 5 Reel blueprints + rows inspector (/api/rows)")
    app.run(host=host, port=port, debug=False, threaded=True)
