#!/usr/bin/env python
"""HomeCartel Marketing Studio - Web UI Dashboard & Cloudflare Tunnel Runner.

Nocturne-styled luxury web dashboard for Collection Category Feed Automation.
Serves real-time data from Google Drive ('G:/My Drive/Collection Category Feed')
and provides an automated free public Cloudflare Tunnel.

Usage:
    python run_dashboard.py
    python run_dashboard.py --port 5000 --no-tunnel
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import zipfile
from pathlib import Path
from typing import Any

import dotenv
from flask import Flask, jsonify, render_template, request, send_file, send_from_directory
import requests

dotenv.load_dotenv()

# Base Google Drive & local fallback paths
GDRIVE_DIR = Path("G:/My Drive/Collection Category Feed")
LOCAL_DIR = Path("output/content/collection_category_feed")

GDRIVE_REELS_DIR = Path("G:/My Drive/Before & After Reels")
GDRIVE_REELS_DIR_ALT = Path("G:/My Drive/Before and After Reels")
LOCAL_REELS_DIR = Path("output/content/before_after_reel")
LOCAL_SLIDESHOW_DIR = Path("output/slideshow_reels")

TOOLS_DIR = Path("tools")
PENDING_IG_FILE = Path(__file__).resolve().parent / "pending_ig_posts.json"
CLOUDFLARED_PATH = TOOLS_DIR / "cloudflared.exe"
CLOUDFLARED_URL = (
    "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
)

app = Flask(__name__, template_folder="templates")
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

# Global state for tunnel and pipeline runner
STATE = {
    "public_tunnel_url": "",
    "pipeline_proc": None,
    "pipeline_logs": [],
    "pipeline_running": False,
    "posted_records": set(),
}
STATE_LOCK = threading.Lock()

CATS = ["Chandelier", "Floor Lamp", "Table Lamp", "Pendant Light", "Linear Chandelier"]
SHORTS = ["CHN", "FLR", "TBL", "PND", "LIN"]


def get_directories() -> list[Path]:
    """Return all available collection storage directories (Google Drive + local fallback)."""
    dirs = []
    if GDRIVE_DIR.exists():
        dirs.append(GDRIVE_DIR)
    if LOCAL_DIR.exists():
        dirs.append(LOCAL_DIR)
    return dirs if dirs else [LOCAL_DIR]


def get_all_storage_directories() -> list[Path]:
    """Return all directories where media might be stored (Collections, Reels, Slideshows, Static)."""
    candidates = [
        GDRIVE_DIR,
        LOCAL_DIR,
        GDRIVE_REELS_DIR,
        GDRIVE_REELS_DIR_ALT,
        LOCAL_REELS_DIR,
        LOCAL_SLIDESHOW_DIR,
        Path("output"),
        Path("static"),
    ]
    dirs = []
    for c in candidates:
        if c.exists() and c not in dirs:
            dirs.append(c)
    return dirs


def get_base_directory() -> Path:
    """Return primary Google Drive destination if mounted, otherwise local fallback."""
    if GDRIVE_DIR.exists():
        return GDRIVE_DIR
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    return LOCAL_DIR


def get_reel_directories() -> list[Path]:
    """Return all available reel storage directories (Google Drive + local fallback)."""
    dirs = []
    if GDRIVE_REELS_DIR.exists():
        dirs.append(GDRIVE_REELS_DIR)
    if GDRIVE_REELS_DIR_ALT.exists() and GDRIVE_REELS_DIR_ALT not in dirs:
        dirs.append(GDRIVE_REELS_DIR_ALT)
    if LOCAL_REELS_DIR.exists() and LOCAL_REELS_DIR not in dirs:
        dirs.append(LOCAL_REELS_DIR)
    if LOCAL_SLIDESHOW_DIR.exists() and LOCAL_SLIDESHOW_DIR not in dirs:
        dirs.append(LOCAL_SLIDESHOW_DIR)
    return dirs if dirs else [LOCAL_REELS_DIR]


def get_reel_base_directory() -> Path:
    """Return primary Google Drive destination for Before & After Reels."""
    if GDRIVE_REELS_DIR.exists():
        return GDRIVE_REELS_DIR
    if GDRIVE_REELS_DIR_ALT.exists():
        return GDRIVE_REELS_DIR_ALT
    LOCAL_REELS_DIR.mkdir(parents=True, exist_ok=True)
    return LOCAL_REELS_DIR


def find_collection_folder(folder_name: str) -> Path | None:
    """Locate a collection folder in either Google Drive or local storage."""
    for base_dir in get_directories():
        target = base_dir / folder_name
        if target.exists() and target.is_dir():
            return target
    return None


def find_reel_folder(folder_name: str) -> Path | None:
    """Locate a reel folder in Google Drive or local storage."""
    for base_dir in get_reel_directories():
        target = base_dir / folder_name
        if target.exists() and target.is_dir():
            return target
        # Also check direct child folders matching record id
        for sub in base_dir.iterdir():
            if sub.is_dir() and (sub.name == folder_name or folder_name in sub.name):
                return sub
    return None


def public_media_url(img_path: Path) -> str | None:
    """Build a publicly fetchable HTTPS URL for a local image via the Cloudflare tunnel."""
    tunnel = STATE.get("public_tunnel_url", "").strip()
    if not tunnel:
        return None

    resolved = img_path.resolve()
    for base_dir in get_all_storage_directories():
        try:
            rel = resolved.relative_to(base_dir.resolve())
            quoted = urllib.parse.quote(rel.as_posix(), safe="/")
            return f"{tunnel.rstrip('/')}/media/{quoted}"
        except ValueError:
            continue
    return None


def extract_record_id(folder_name: str) -> str:
    """Extract record ID (e.g. rect0yvrAqXKq7MQo) from folder name."""
    m = re.search(r"\((rec[a-zA-Z0-9]+)\)", folder_name)
    if m:
        return m.group(1)
    if "rec" in folder_name:
        parts = folder_name.split("_")
        for p in parts:
            if p.startswith("rec"):
                return p
    return folder_name[:15]


def parse_collection_folder(folder: Path) -> dict[str, Any]:
    """Parse a collection folder into rich Nocturne UI set structure."""
    meta_file = folder / "summary_metadata.json"
    prompts_file = folder / "prompts_used.txt"
    ready_dir = folder / "01_FINAL_READY_TO_POST"
    slots_dir = folder / "02_SLOT_DETAILS"

    meta_data = {}
    if meta_file.exists():
        try:
            meta_data = json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    prompts_text = ""
    if prompts_file.exists():
        try:
            prompts_text = prompts_file.read_text(encoding="utf-8")
        except Exception:
            pass

    rec_id = meta_data.get("record_id") or extract_record_id(folder.name)
    raw_date = meta_data.get("timestamp") or time.strftime("%b %d, %Y", time.localtime(folder.stat().st_mtime))
    if " " in raw_date:
        date_str = raw_date.split(" ")[0]
    else:
        date_str = raw_date

    # Determine status
    ready_images = []
    if ready_dir.exists():
        ready_images = sorted([img for img in ready_dir.glob("*.jpg")])

    if len(ready_images) >= 5 or meta_data.get("status") == "Done":
        status = "Done"
    elif len(ready_images) > 0 or meta_data.get("status") == "Processing":
        status = "Processing"
    else:
        status = "Standby"

    # Build 5 items
    items = []
    for i in range(1, 6):
        cat = CATS[i - 1]
        short = SHORTS[i - 1]
        slot_folder_name = f"Slot_{i}_{cat.replace(' ', '_')}"
        slot_folder = slots_dir / slot_folder_name if slots_dir.exists() else None

        # Look for ready blended image
        img_url = ""
        is_ready = False

        if ready_dir.exists():
            for r_img in ready_images:
                if r_img.name.startswith(f"{i}_"):
                    img_url = f"/media/{folder.name}/01_FINAL_READY_TO_POST/{r_img.name}"
                    is_ready = True
                    break

        if not img_url and slot_folder and slot_folder.exists():
            # Check for blended image first
            for fname in ("4_blended_output.jpg", "4_blended.jpg"):
                if (slot_folder / fname).exists():
                    img_url = f"/media/{folder.name}/02_SLOT_DETAILS/{slot_folder_name}/{fname}"
                    is_ready = True
                    break
            # Check for interior images
            if not img_url:
                for fname in ("2_interior_krea.jpg", "2_interior_room.jpg", "2_interior.jpg"):
                    if (slot_folder / fname).exists():
                        img_url = f"/media/{folder.name}/02_SLOT_DETAILS/{slot_folder_name}/{fname}"
                        break
            # Check for raw product image
            if not img_url:
                for fname in ("1_product_raw.jpg", "1_product.jpg"):
                    if (slot_folder / fname).exists():
                        img_url = f"/media/{folder.name}/02_SLOT_DETAILS/{slot_folder_name}/{fname}"
                        break
            # Fallback: pick any .jpg/.png in the slot folder
            if not img_url:
                any_imgs = sorted([f for f in slot_folder.glob("*.jpg")]) + sorted([f for f in slot_folder.glob("*.png")])
                if any_imgs:
                    img_url = f"/media/{folder.name}/02_SLOT_DETAILS/{slot_folder_name}/{any_imgs[0].name}"

        # Item name and SKU
        item_name = cat
        sku = f"{short}-{2000 + i * 37}"

        # Extract from metadata if present
        if meta_data and "slots" in meta_data and len(meta_data["slots"]) >= i:
            slot_info = meta_data["slots"][i - 1]
            if slot_info.get("item_name"):
                item_name = slot_info["item_name"]
            if slot_info.get("sku"):
                sku = slot_info["sku"]

        # Prompt text
        prompt = ""
        if slot_folder and (slot_folder / "3_vision_prompt.txt").exists():
            try:
                prompt = (slot_folder / "3_vision_prompt.txt").read_text(encoding="utf-8").strip()
            except Exception:
                pass

        if not prompt:
            prompt = f"Place the {item_name} as the sole lighting fixture in a modern luxury interior, preserving its exact geometry, scale and metal/glass finish. 4:5 crop, 1K."

        items.append({
            "n": i,
            "cat": cat,
            "short": short,
            "name": item_name,
            "sku": sku,
            "img": img_url or f"/static/samples/set1_blended{min(i, 3)}.jpg",
            "imgOpacity": 1.0 if is_ready else 0.35,
            "pending": not is_ready,
            "pendingLabel": "Generating interior…" if status == "Processing" else "Awaiting interior",
            "prompt": prompt,
        })

    cost = meta_data.get("cost") or ("$0.41" if status == "Done" else ("$0.24" if status == "Processing" else "$0.06"))

    return {
        "id": folder.name,
        "record_id": rec_id,
        "date": date_str,
        "status": status,
        "cost": cost,
        "cost_breakdown": meta_data.get("cost_breakdown") or ("krea ×5 · qwen ×5 · kie ×1" if status != "Standby" else "akeneo scrape only"),
        "items": items,
        "folder_name": folder.name,
        "prompts_text": prompts_text,
    }


def parse_reel_folder(folder: Path) -> dict[str, Any]:
    """Parse a Before & After Reel folder from Google Drive into structured reel object."""
    meta_file = folder / "summary_metadata.json"
    meta_data = {}
    if meta_file.exists():
        try:
            meta_data = json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    rec_id = meta_data.get("record_id") or extract_record_id(folder.name)
    raw_date = meta_data.get("timestamp") or time.strftime("%b %d, %Y", time.localtime(folder.stat().st_mtime))
    product_name = meta_data.get("product_name") or folder.name.split("(")[0].replace("-", " ").strip()
    category = meta_data.get("category") or "Lighting"
    room = meta_data.get("room") or "Living room"
    status = meta_data.get("status") or "Done"
    duration = meta_data.get("duration") or "0:12"
    cost = meta_data.get("cost") or "$0.14"

    # 1. Search for compiled video
    video_url = ""
    video_filename = ""
    vdir = folder / "01_FINAL_REEL_VIDEO"
    if vdir.exists():
        vids = list(vdir.glob("*.mp4")) + list(vdir.glob("*.mov"))
        if vids:
            video_url = f"/media/{folder.name}/01_FINAL_REEL_VIDEO/{vids[0].name}"
            video_filename = vids[0].name
    if not video_url:
        root_vids = list(folder.glob("*.mp4")) + list(folder.glob("*.mov"))
        if root_vids:
            video_url = f"/media/{folder.name}/{root_vids[0].name}"
            video_filename = root_vids[0].name

    # 2. Search for before image (9:16 interior)
    before_url = ""
    adir = folder / "02_SOURCE_ASSETS"
    search_dirs = [adir, folder] if adir.exists() else [folder]

    for sdir in search_dirs:
        if not sdir.exists():
            continue
        for img in sorted(sdir.glob("*.jpg")) + sorted(sdir.glob("*.png")):
            name_lower = img.name.lower()
            if any(k in name_lower for k in ("before", "interior", "room")):
                rel = img.relative_to(folder).as_posix()
                before_url = f"/media/{folder.name}/{rel}"
                break
        if before_url:
            break

    # 3. Search for after image (9:16 blended styled room)
    after_url = ""
    for sdir in search_dirs:
        if not sdir.exists():
            continue
        for img in sorted(sdir.glob("*.jpg")) + sorted(sdir.glob("*.png")):
            name_lower = img.name.lower()
            if any(k in name_lower for k in ("after", "blended", "day", "style")):
                rel = img.relative_to(folder).as_posix()
                after_url = f"/media/{folder.name}/{rel}"
                break
        if after_url:
            break

    # Fallback to sample static images if empty
    if not before_url:
        before_url = "/static/samples/set1_interior1.jpg"
    if not after_url:
        after_url = "/static/samples/set1_blended1.jpg"

    posted = rec_id in STATE["posted_records"] or folder.name in STATE["posted_records"]

    return {
        "id": rec_id,
        "folder_name": folder.name,
        "product": product_name,
        "cat": category,
        "room": room,
        "date": raw_date,
        "status": status,
        "duration": duration,
        "cost": cost,
        "before": before_url,
        "after": after_url,
        "video": video_url,
        "video_filename": video_filename,
        "posted": posted,
    }


def list_collection_folders() -> list[dict[str, Any]]:
    """Scan all storage directories (Google Drive & local) for completed collection folders."""
    collections = []
    seen_ids = set()

    for base_dir in get_directories():
        if not base_dir.exists():
            continue
        folders = [f for f in base_dir.iterdir() if f.is_dir()]
        folders.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        for folder in folders:
            if folder.name in seen_ids:
                continue
            seen_ids.add(folder.name)
            try:
                col_data = parse_collection_folder(folder)
                col_data["posted"] = col_data["id"] in STATE["posted_records"]
                collections.append(col_data)
            except Exception as err:
                print(f"[WARN] Error parsing collection folder {folder.name}: {err}")

    return collections


def list_reel_folders() -> list[dict[str, Any]]:
    """Scan Google Drive ('Before & After Reels') and local output directories for reel video outputs."""
    reels = []
    seen_ids = set()

    for base_dir in get_reel_directories():
        if not base_dir.exists():
            continue
        folders = [f for f in base_dir.iterdir() if f.is_dir()]
        folders.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        for folder in folders:
            if folder.name in seen_ids:
                continue
            seen_ids.add(folder.name)
            try:
                reel_data = parse_reel_folder(folder)
                reels.append(reel_data)
            except Exception as err:
                print(f"[WARN] Error parsing reel folder {folder.name}: {err}")

    return reels


@app.route("/")
def index():
    """Render the Main Nocturne Studio Dashboard."""
    return render_template("index.html")


@app.route("/api/collections")
def api_get_collections():
    """Return summary list of all collections, reels, KPI stats, and tunnel URL."""
    cols = list_collection_folders()
    reels = list_reel_folders()

    done_count = sum(1 for c in cols if c["status"] == "Done")
    in_progress = sum(1 for c in cols if c["status"] in ("Processing", "Standby"))
    total_cost = sum(float(c["cost"].replace("$", "")) for c in cols)

    stats = [
        {"label": "Total sets", "value": str(len(cols)), "sub": "in this table", "dot": "var(--color-neutral-500)"},
        {"label": "Done", "value": str(done_count), "sub": "ready to post", "dot": "var(--color-accent-400)"},
        {"label": "In progress", "value": str(in_progress), "sub": "processing / standby", "dot": "var(--color-accent-200)"},
        {"label": "Provider cost", "value": f"${total_cost:.2f}", "sub": "this batch, est.", "dot": "var(--color-neutral-500)"},
    ]

    return jsonify({
        "collections": cols,
        "reels": reels,
        "stats": stats,
        "public_tunnel_url": STATE.get("public_tunnel_url", ""),
        "base_directory": str(get_base_directory()),
        "reels_directory": str(get_reel_base_directory()),
        "pending_ig_posts": [
            {
                "id": j.get("id"),
                "folder_name": j.get("folder_name"),
                "caption": j.get("caption", ""),
                "scheduled_time": j.get("scheduled_time"),
                "slides": len(j.get("image_paths", [])),
                "status": j.get("status"),
                "attempts": j.get("attempts", 0),
                "last_error": j.get("last_error", ""),
            }
            for j in sorted(
                (j for j in load_pending_ig_posts()
                 if j.get("status") in ("pending", "failed")),
                key=lambda j: j.get("scheduled_time", 0),
            )
        ],
    })


@app.route("/api/reels")
def api_get_reels():
    """Return list of Before & After Reels from Google Drive."""
    reels = list_reel_folders()
    return jsonify({
        "reels": reels,
        "reels_directory": str(get_reel_base_directory()),
        "public_tunnel_url": STATE.get("public_tunnel_url", ""),
    })


@app.route("/api/collections/<folder_name>")
def api_get_collection_details(folder_name: str):
    """Return detailed slot data for a specific collection."""
    folder = find_collection_folder(folder_name)
    if not folder:
        return jsonify({"error": "Collection not found"}), 404

    col_data = parse_collection_folder(folder)
    col_data["posted"] = col_data["id"] in STATE["posted_records"]
    return jsonify(col_data)


@app.route("/api/download-reel/<folder_name>")
def api_download_reel(folder_name: str):
    """Download the compiled MP4 video or zipped reel assets."""
    folder = find_reel_folder(folder_name)
    if not folder:
        return jsonify({"error": "Reel folder not found"}), 404

    vids = list(folder.rglob("*.mp4")) + list(folder.rglob("*.mov"))
    if vids:
        return send_file(vids[0], as_attachment=True, download_name=f"{folder_name}.mp4")

    # If no MP4, return zip of source assets
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in folder.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(folder))
    mem.seek(0)
    return send_file(mem, mimetype="application/zip", as_attachment=True, download_name=f"{folder_name}_Reel.zip")


@app.route("/media/<path:filepath>")
def serve_media(filepath: str):
    """Serve image and video files directly from Google Drive, Reels directories, or local storage."""
    for base_dir in get_all_storage_directories():
        candidate = base_dir / filepath
        if candidate.exists() and candidate.is_file():
            return send_from_directory(base_dir, filepath)
    return jsonify({"error": "Media file not found"}), 404


@app.route("/api/toggle-posted/<folder_name>", methods=["POST"])
def api_toggle_posted(folder_name: str):
    """Toggle posted flag for a record."""
    with STATE_LOCK:
        if folder_name in STATE["posted_records"]:
            STATE["posted_records"].remove(folder_name)
            posted = False
        else:
            STATE["posted_records"].add(folder_name)
            posted = True
    return jsonify({"posted": posted})


def get_meta_credentials() -> tuple[str, str, str]:
    """Retrieve verified Meta Page ID, Instagram Account ID, and Page Access Token from environment."""
    page_id = os.environ.get("META_PAGE_ID", "1761624157420596")
    ig_user_id = os.environ.get("META_INSTAGRAM_ACCOUNT_ID", "17841404109072695")
    page_token = os.environ.get("META_PAGE_ACCESS_TOKEN", "")
    return page_id, ig_user_id, page_token


IG_TUNNEL_ERROR = (
    "Instagram needs the public tunnel to fetch the images. Restart the dashboard "
    "without --no-tunnel and wait for the trycloudflare.com URL to appear."
)


def _ig_wait_for_container(container_id: str, page_token: str, timeout: int = 90) -> tuple[bool, str]:
    """Poll an Instagram media container until it reports FINISHED.

    Publishing a container that is still IN_PROGRESS raises the intermittent
    'Media ID is not available' error, so this must run before /media_publish.
    """
    deadline = time.time() + timeout
    last_status = ""
    while time.time() < deadline:
        try:
            res = requests.get(
                f"https://graph.facebook.com/v20.0/{container_id}",
                params={"fields": "status_code,status", "access_token": page_token},
                timeout=15,
            )
            body = res.json()
        except Exception as err:
            last_status = str(err)
            time.sleep(2)
            continue

        code = body.get("status_code")
        if code == "FINISHED":
            return True, ""
        if code in ("ERROR", "EXPIRED"):
            return False, body.get("status") or f"Instagram container {code}"
        last_status = body.get("status") or str(code)
        time.sleep(2)

    return False, f"Timed out waiting for Instagram to process the image ({last_status})"


def publish_to_instagram(images: list[Path], caption: str) -> dict:
    """Publish a carousel (or single image) to Instagram Business via the Graph API.

    Instagram cannot accept binary uploads the way the Facebook Page /photos
    endpoint can - it only fetches images from a public HTTPS URL, which we
    serve through the Cloudflare tunnel. Returns a result dict; never raises.
    """
    _page_id, ig_user_id, page_token = get_meta_credentials()
    if not page_token:
        return {"status": "error", "error": "META_PAGE_ACCESS_TOKEN not configured in .env"}

    image_urls = []
    for img in images:
        url = public_media_url(Path(img))
        if not url:
            return {"status": "error", "error": IG_TUNNEL_ERROR}
        image_urls.append(url)

    if not image_urls:
        return {"status": "error", "error": "No images available to publish"}

    image_urls = image_urls[:10]  # Instagram carousel limit
    ig_url_base = f"https://graph.facebook.com/v20.0/{ig_user_id}"

    try:
        if len(image_urls) > 1:
            # Step 1: one child container per slide, each fully processed.
            child_ids = []
            for idx, img_url in enumerate(image_urls, start=1):
                c_res = requests.post(
                    f"{ig_url_base}/media",
                    data={
                        "image_url": img_url,
                        "is_carousel_item": "true",
                        "access_token": page_token,
                    },
                    timeout=60,
                )
                c_json = c_res.json()
                if "id" not in c_json:
                    err_txt = c_json.get("error", {}).get("message", str(c_json))
                    # Abort rather than post a partial carousel.
                    return {"status": "error", "error": f"Slide {idx} rejected by Instagram: {err_txt}"}

                ok, poll_err = _ig_wait_for_container(c_json["id"], page_token)
                if not ok:
                    return {"status": "error", "error": f"Slide {idx}: {poll_err}"}
                child_ids.append(c_json["id"])

            # Step 2: parent carousel container.
            parent_data = {
                "media_type": "CAROUSEL",
                "children": ",".join(child_ids),
                "caption": caption,
                "access_token": page_token,
            }
        else:
            parent_data = {
                "image_url": image_urls[0],
                "caption": caption,
                "access_token": page_token,
            }

        p_res = requests.post(f"{ig_url_base}/media", data=parent_data, timeout=60)
        p_json = p_res.json()
        if "id" not in p_json:
            err_msg = p_json.get("error", {}).get("message", str(p_json))
            return {"status": "error", "error": err_msg}

        container_id = p_json["id"]
        ok, poll_err = _ig_wait_for_container(container_id, page_token)
        if not ok:
            return {"status": "error", "error": poll_err}

        # Step 3: publish.
        pub_res = requests.post(
            f"{ig_url_base}/media_publish",
            data={"creation_id": container_id, "access_token": page_token},
            timeout=60,
        )
        pub_json = pub_res.json()
        if "id" not in pub_json:
            err_msg = pub_json.get("error", {}).get("message", str(pub_json))
            return {"status": "error", "error": err_msg}

        return {
            "status": "success",
            "post_id": pub_json["id"],
            "scheduled": False,
            "slides": len(image_urls),
        }
    except Exception as err:
        return {"status": "error", "error": str(err)}


def append_publish_log(folder: Path, entry: dict) -> None:
    """Append one publish attempt to <collection>/meta_publish_log.json history."""
    log_file = folder / "meta_publish_log.json"
    history = []
    try:
        if log_file.exists():
            existing = json.loads(log_file.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                history = existing.get("history") or []
                if not history and existing.get("results"):
                    history = [existing]  # migrate the old single-entry format
            elif isinstance(existing, list):
                history = existing
    except Exception as err:
        print(f"[WARN] Could not read existing publish log: {err}")

    history.append(entry)
    try:
        log_file.write_text(json.dumps({"history": history}, indent=2), encoding="utf-8")
    except Exception as err:
        print(f"[WARN] Could not write publish log for {folder.name}: {err}")


# -----------------------------------------------------------------
# Instagram scheduler - the IG API has no native scheduling, so we
# hold the job locally and publish it when it comes due.
# -----------------------------------------------------------------

def load_pending_ig_posts() -> list[dict]:
    try:
        if PENDING_IG_FILE.exists():
            data = json.loads(PENDING_IG_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
    except Exception as err:
        print(f"[WARN] Could not read {PENDING_IG_FILE.name}: {err}")
    return []


def save_pending_ig_posts(jobs: list[dict]) -> None:
    # Drop published jobs after a week so the file doesn't grow forever.
    # Failed jobs are kept until the user dismisses them from the dashboard.
    cutoff = time.time() - (7 * 86400)
    kept = [
        j for j in jobs
        if j.get("status") != "done" or j.get("scheduled_time", 0) >= cutoff
    ]
    try:
        PENDING_IG_FILE.write_text(json.dumps(kept, indent=2), encoding="utf-8")
    except Exception as err:
        print(f"[WARN] Could not write {PENDING_IG_FILE.name}: {err}")


def queue_ig_post(folder_name: str, caption: str, scheduled_time: int, images: list[Path]) -> dict:
    """Store a scheduled Instagram post for the background worker to publish."""
    job = {
        "id": f"ig-{int(time.time() * 1000)}",
        "folder_name": folder_name,
        "caption": caption,
        "scheduled_time": int(scheduled_time),
        # Store local paths, not URLs: the trycloudflare hostname changes on every
        # restart and IG containers expire after 24h, so both are resolved at publish time.
        "image_paths": [str(p) for p in images],
        "status": "pending",
        "queued_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with STATE_LOCK:
        jobs = load_pending_ig_posts()
        # Re-scheduling a collection replaces its pending job rather than stacking
        # another one - otherwise every click of Schedule queues a duplicate post.
        replaced = [
            j for j in jobs
            if j.get("status") == "pending" and j.get("folder_name") == folder_name
        ]
        if replaced:
            jobs = [j for j in jobs if j not in replaced]
            print(f"[IG-SCHEDULER] Replaced {len(replaced)} pending job(s) for {folder_name}")
        jobs.append(job)
        save_pending_ig_posts(jobs)

    job["replaced"] = len(replaced)
    return job


def cancel_ig_post(job_id: str) -> bool:
    """Cancel a pending job, or dismiss a failed one. False if there was nothing to remove.

    Published jobs are left alone - removing one would not unpublish anything.
    """
    with STATE_LOCK:
        jobs = load_pending_ig_posts()
        remaining = [
            j for j in jobs
            if not (j.get("id") == job_id and j.get("status") in ("pending", "failed"))
        ]
        if len(remaining) == len(jobs):
            return False
        save_pending_ig_posts(remaining)
    return True


# A scheduled post gets several chances before it is written off - a transient
# blip at the scheduled minute must not silently cost the user their post.
IG_MAX_ATTEMPTS = 4
IG_RETRY_BACKOFF = [60, 300, 900]  # seconds before attempts 2, 3 and 4


def _update_ig_job(job_id: str, **fields) -> None:
    """Patch the stored copy of one scheduled job."""
    with STATE_LOCK:
        jobs = load_pending_ig_posts()
        for stored in jobs:
            if stored.get("id") == job_id:
                stored.update(fields)
        save_pending_ig_posts(jobs)


def _run_ig_job(job: dict) -> None:
    """Publish one due scheduled Instagram job, retrying before giving up."""
    folder_name = job.get("folder_name", "")
    job_id = job.get("id", "")
    late_by = int(time.time()) - int(job.get("scheduled_time", 0))

    # The tunnel is populated asynchronously at startup. Not having it yet is a
    # "not ready" condition, not a failure - waiting must not consume an attempt,
    # otherwise a slow tunnel burns the retry budget before we ever reach Instagram.
    if not STATE.get("public_tunnel_url", "").strip():
        print(f"[IG-SCHEDULER] Tunnel not ready yet, holding {folder_name} for the next tick")
        return

    images = [Path(p) for p in job.get("image_paths", []) if Path(p).exists()]
    if not images:
        result = {"status": "error", "error": "Scheduled images no longer exist on disk"}
    else:
        print(f"[IG-SCHEDULER] Publishing scheduled post for {folder_name}...")
        result = publish_to_instagram(images, job.get("caption", ""))

    attempts = int(job.get("attempts", 0)) + 1

    if result.get("status") == "success":
        print(f"[IG-SCHEDULER] Published {folder_name} -> {result.get('post_id')}")
        with STATE_LOCK:
            STATE["posted_records"].add(folder_name)
        _update_ig_job(job_id, status="done", attempts=attempts,
                       completed_at=time.strftime("%Y-%m-%d %H:%M:%S"), result=result)
    elif attempts < IG_MAX_ATTEMPTS:
        delay = IG_RETRY_BACKOFF[min(attempts - 1, len(IG_RETRY_BACKOFF) - 1)]
        print(f"[IG-SCHEDULER] Attempt {attempts}/{IG_MAX_ATTEMPTS} failed for {folder_name}: "
              f"{result.get('error')} - retrying in {delay}s")
        _update_ig_job(job_id, status="pending", attempts=attempts,
                       retry_after=int(time.time()) + delay,
                       last_error=result.get("error", ""))
        return  # not a final outcome - don't log it as one
    else:
        print(f"[IG-SCHEDULER] GAVE UP on {folder_name} after {attempts} attempts: {result.get('error')}")
        _update_ig_job(job_id, status="failed", attempts=attempts,
                       completed_at=time.strftime("%Y-%m-%d %H:%M:%S"),
                       last_error=result.get("error", ""), result=result)

    folder = find_collection_folder(folder_name)
    if folder:
        append_publish_log(folder, {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "caption": job.get("caption", ""),
            "platforms": ["instagram"],
            "publish_mode": "schedule",
            "scheduled_time": job.get("scheduled_time"),
            "source": "ig_scheduler",
            "attempts": attempts,
            "late_by_seconds": late_by if late_by > 60 else 0,
            "results": {"instagram": result},
        })


def ig_scheduler_loop() -> None:
    """Background worker: publish scheduled Instagram posts once they come due."""
    while True:
        try:
            now = time.time()
            due = [
                job for job in load_pending_ig_posts()
                if job.get("status") == "pending"
                and job.get("scheduled_time", 0) <= now
                and job.get("retry_after", 0) <= now
            ]
            for job in due:
                # Overdue jobs (dashboard was offline) publish now and are flagged in the log.
                _run_ig_job(job)
        except Exception as err:
            print(f"[WARN] IG scheduler error: {err}")
        time.sleep(30)


@app.route("/api/cancel-ig-post/<job_id>", methods=["POST"])
def api_cancel_ig_post(job_id: str):
    """Cancel a pending scheduled Instagram post."""
    if cancel_ig_post(job_id):
        print(f"[IG-SCHEDULER] Cancelled {job_id}")
        return jsonify({"cancelled": True})
    return jsonify({"error": "No pending or failed Instagram post with that id"}), 404


@app.route("/api/post-meta", methods=["POST"])
def api_post_meta():
    """Publish or schedule multi-photo carousel post to Facebook Page & Instagram via Meta Graph API."""
    data = request.get_json(silent=True) or {}
    folder_name = data.get("folder_name", "")
    caption = (data.get("caption") or "").strip()
    platforms = data.get("platforms") or ["facebook", "instagram"]
    publish_mode = data.get("publish_mode", "now")  # 'now' | 'schedule'
    scheduled_time = data.get("scheduled_time")  # Unix timestamp in seconds (int)

    if not folder_name:
        return jsonify({"error": "No collection folder specified"}), 400
    if not caption:
        return jsonify({"error": "Caption cannot be empty"}), 400

    page_id, _ig_user_id, page_token = get_meta_credentials()
    if not page_token:
        return jsonify({"error": "META_PAGE_ACCESS_TOKEN not configured in .env"}), 500

    folder = find_collection_folder(folder_name)
    if not folder:
        return jsonify({"error": f"Collection folder '{folder_name}' not found"}), 404

    # Locate ready images
    ready_dir = folder / "01_FINAL_READY_TO_POST"
    images = []
    if ready_dir.exists():
        images = sorted([img for img in ready_dir.glob("*.jpg")])
    if not images:
        slots_dir = folder / "02_SLOT_DETAILS"
        if slots_dir.exists():
            for slot_folder in sorted(slots_dir.glob("Slot_*")):
                for fname in ("4_blended_output.jpg", "4_blended.jpg", "2_interior_krea.jpg", "1_product_raw.jpg"):
                    candidate = slot_folder / fname
                    if candidate.exists():
                        images.append(candidate)
                        break

    if not images:
        return jsonify({"error": "No images found in collection folder to publish"}), 400

    results = {}
    is_scheduled = (publish_mode == "schedule" and scheduled_time is not None)
    fb_url_base = f"https://graph.facebook.com/v20.0/{page_id}"

    # -------------------------------------------------------------
    # Facebook: upload each image as an unpublished photo to obtain
    # FBIDs, then attach them all to a single feed post.
    # Only runs when Facebook is actually selected, so an Instagram-only
    # post never pushes stray photos into the Page's album.
    # -------------------------------------------------------------
    if "facebook" in platforms:
        uploaded_media = []
        for img_path in images:
            try:
                with open(img_path, "rb") as img_file:
                    upload_res = requests.post(
                        f"{fb_url_base}/photos",
                        data={
                            "access_token": page_token,
                            "published": "false",
                            "temporary": "true"
                        },
                        files={"source": (img_path.name, img_file, "image/jpeg")},
                        timeout=45
                    )
                upload_json = upload_res.json()
                if "id" in upload_json:
                    uploaded_media.append({"fbid": upload_json["id"], "name": img_path.name})
                else:
                    err_txt = upload_json.get("error", {}).get("message", str(upload_json))
                    print(f"[WARN] Photo upload error for {img_path.name}: {err_txt}")
            except Exception as e:
                print(f"[WARN] Failed uploading photo {img_path.name}: {e}")

        if not uploaded_media:
            results["facebook"] = {
                "status": "error",
                "error": "Failed uploading images to Meta servers"
            }
        else:
            try:
                post_payload = {
                    "access_token": page_token,
                    "message": caption,
                }
                for idx, item in enumerate(uploaded_media):
                    post_payload[f"attached_media[{idx}]"] = json.dumps({"media_fbid": item["fbid"]})

                if is_scheduled:
                    post_payload["published"] = "false"
                    post_payload["scheduled_publish_time"] = int(scheduled_time)
                else:
                    post_payload["published"] = "true"

                feed_res = requests.post(f"{fb_url_base}/feed", data=post_payload, timeout=30)
                feed_json = feed_res.json()

                if "id" in feed_json:
                    results["facebook"] = {
                        "status": "scheduled" if is_scheduled else "success",
                        "post_id": feed_json["id"],
                        "scheduled": is_scheduled,
                        "scheduled_time": scheduled_time if is_scheduled else None
                    }
                else:
                    err_msg = feed_json.get("error", {}).get("message", str(feed_json))
                    results["facebook"] = {"status": "error", "error": err_msg}
            except Exception as err:
                results["facebook"] = {"status": "error", "error": str(err)}

    # -------------------------------------------------------------
    # Instagram Business (@homecartel). The IG Content Publishing API
    # has no scheduling of its own, so scheduled posts are queued
    # locally and published by ig_scheduler_loop when they come due.
    # -------------------------------------------------------------
    if "instagram" in platforms:
        if is_scheduled:
            if not STATE.get("public_tunnel_url", "").strip():
                results["instagram"] = {"status": "error", "error": IG_TUNNEL_ERROR}
            else:
                job = queue_ig_post(folder_name, caption, int(scheduled_time), images)
                note = "Held by this dashboard, not Meta Planner - it must be running at that time."
                if job.get("replaced"):
                    note = "Replaced the previous pending post for this set. " + note
                results["instagram"] = {
                    "status": "scheduled",
                    "job_id": job["id"],
                    "scheduled": True,
                    "scheduled_time": scheduled_time,
                    "replaced": job.get("replaced", 0),
                    "note": note,
                }
        else:
            results["instagram"] = publish_to_instagram(images, caption)

    # Check outcome. "scheduled" counts as an OK result, not a publish.
    published = [p.capitalize() for p, r in results.items() if r.get("status") == "success"]
    scheduled = [p.capitalize() for p, r in results.items() if r.get("status") == "scheduled"]
    ok_platforms = published + scheduled
    failed_platforms = [
        f"{p.capitalize()} ({r.get('error', 'Failed')})"
        for p, r in results.items() if r.get("status") == "error"
    ]

    # Always log the attempt - a total failure used to leave no trace at all.
    append_publish_log(folder, {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "caption": caption,
        "platforms": platforms,
        "publish_mode": publish_mode,
        "scheduled_time": scheduled_time,
        "source": "dashboard",
        "results": results,
    })

    if not ok_platforms:
        err_detail = "; ".join(failed_platforms) if failed_platforms else "No platforms succeeded"
        return jsonify({
            "status": "error",
            "posted": False,
            "results": results,
            "error": err_detail
        }), 500

    if published:
        with STATE_LOCK:
            STATE["posted_records"].add(folder_name)

    parts = []
    if published:
        parts.append(f"Published to {' & '.join(published)}")
    if scheduled:
        parts.append(f"Scheduled on {' & '.join(scheduled)}")
    msg = " • ".join(parts) + " ✓"

    if failed_platforms:
        # Partial: the caller must surface this, not bury it in a toast.
        return jsonify({
            "status": "partial",
            "posted": bool(published),
            "results": results,
            "message": msg,
            "error": "; ".join(failed_platforms)
        })

    return jsonify({
        "status": "success",
        "posted": bool(published),
        "results": results,
        "message": msg
    })


@app.route("/api/open-drive/<folder_name>", methods=["POST"])
def api_open_drive(folder_name: str):
    """Open folder in Windows Explorer on local machine."""
    folder = find_collection_folder(folder_name)
    if folder and folder.exists():
        try:
            os.startfile(str(folder))
            return jsonify({"status": "opened", "path": str(folder)})
        except Exception as err:
            return jsonify({"status": "error", "message": str(err)})
    return jsonify({"status": "not_found"}), 404


@app.route("/api/open-drive-reels/<folder_name>", methods=["POST"])
def api_open_drive_reels(folder_name: str):
    """Open Before & After Reel folder in Windows Explorer on local machine."""
    folder = find_reel_folder(folder_name)
    if not folder:
        folder = get_reel_base_directory()
    try:
        if os.name == "nt":
            os.startfile(str(folder))
        else:
            subprocess.run(["xdg-open", str(folder)])
        return jsonify({"status": "opened", "path": str(folder)})
    except Exception as err:
        return jsonify({"error": str(err)}), 500


@app.route("/api/download-all/<folder_name>")
def api_download_all(folder_name: str):
    """Create a ZIP of all 5 ready-to-post blended images and download."""
    folder = find_collection_folder(folder_name)
    if not folder:
        return jsonify({"error": "Collection folder not found"}), 404
    ready_dir = folder / "01_FINAL_READY_TO_POST"

    if not ready_dir.exists():
        return jsonify({"error": "Ready images directory not found"}), 404

    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, "w", zipfile.ZIP_DEFLATED) as zf:
        for img in sorted(ready_dir.glob("*.jpg")):
            zf.write(img, arcname=img.name)

    memory_file.seek(0)
    return send_file(
        memory_file,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"{folder_name}_Ready_Posts.zip",
    )


@app.route("/api/generate-caption", methods=["POST"])
def api_generate_caption():
    """Generate an Instagram carousel caption for 5 collection products."""
    data = request.get_json(silent=True) or {}
    items = data.get("items", [])

    # =======================================================
    # CLAUDE API CAPTION GENERATION (COMMENTED OUT FOR NOW)
    # =======================================================
    # api_key = os.environ.get("ANTHROPIC_API_KEY")
    # if api_key and items:
    #     try:
    #         import urllib.request
    #         products_str = ", ".join(f"{it.get('cat', '')}: {it.get('name', '')}" for it in items)
    #         prompt = (
    #             f"You write Instagram captions for HomeCartel, a modern luxury home-lighting brand. "
    #             f"Write one warm, aspirational Instagram caption for a 5-slide carousel featuring these products: {products_str}. "
    #             f"Structure: 2-3 short sentences opening, a bullet list of the 5 product names, a soft call to action ('Shop the full lighting edit — link in bio'), "
    #             f"and 6-8 relevant hashtags. Return ONLY the caption text."
    #         )
    #         req = urllib.request.Request(
    #             "https://api.anthropic.com/v1/messages",
    #             headers={
    #                 "x-api-key": api_key,
    #                 "anthropic-version": "2023-06-01",
    #                 "content-type": "application/json",
    #             },
    #             data=json.dumps({
    #                 "model": "claude-3-5-sonnet-20241022",
    #                 "max_tokens": 500,
    #                 "messages": [{"role": "user", "content": prompt}],
    #             }).encode("utf-8"),
    #         )
    #         with urllib.request.urlopen(req, timeout=10) as resp:
    #             result = json.loads(resp.read().decode("utf-8"))
    #             caption_text = result["content"][0]["text"].strip()
    #             return jsonify({"caption": caption_text})
    #     except Exception as err:
    #         print(f"[WARN] Anthropic caption generation failed: {err}")
    # =======================================================

    # Fallback to rich structured copywriting template
    names = [it.get("name", it.get("cat", f"Fixture {idx+1}")) for idx, it in enumerate(items)]
    while len(names) < 5:
        names.append(f"Lighting Fixture {len(names) + 1}")

    fallback = (
        f"Five ways to light a room — one collection.\n\n"
        f"From the {names[0]} making a statement overhead to the quiet glow of the {names[2]}, "
        f"this drop layers warmth into every corner of the home. Swipe through all five ✨\n\n"
        f"· {names[0]}\n"
        f"· {names[1]}\n"
        f"· {names[2]}\n"
        f"· {names[3]}\n"
        f"· {names[4]}\n\n"
        f"Shop the full lighting edit — link in bio.\n\n"
        f"#HomeCartel #LightingDesign #InteriorInspo #ModernHome #HomeDecor #LightItUp #InteriorStyling"
    )
    return jsonify({"caption": fallback})


@app.route("/api/run-pipeline", methods=["POST"])
def api_run_pipeline():
    """Trigger background execution of run_collection_category_feed.py."""
    data = request.get_json(silent=True) or {}
    max_rows = data.get("rows", 1)
    execute = data.get("execute", True)

    with STATE_LOCK:
        if STATE.get("pipeline_running"):
            return jsonify({"status": "already_running"}), 409

        STATE["pipeline_logs"] = [f"[START] Initializing Collection Category Feed ({max_rows} row(s), Execute={execute})..."]
        STATE["pipeline_running"] = True

        def runner_thread():
            try:
                cmd = [
                    sys.executable,
                    "-u",
                    "run_collection_category_feed.py",
                    "--phase",
                    "all",
                    "--max-rows",
                    str(max_rows),
                ]
                if execute:
                    cmd.append("--execute")

                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                STATE["pipeline_proc"] = proc

                for line in iter(proc.stdout.readline, ""):
                    if line:
                        with STATE_LOCK:
                            STATE["pipeline_logs"].append(line.rstrip())
                            if len(STATE["pipeline_logs"]) > 1000:
                                STATE["pipeline_logs"].pop(0)

                proc.stdout.close()
                proc.wait()
                with STATE_LOCK:
                    STATE["pipeline_logs"].append(f"\n[DONE] Process exited with code {proc.returncode}")
            except Exception as err:
                with STATE_LOCK:
                    STATE["pipeline_logs"].append(f"[ERROR] Pipeline runner failed: {err}")
            finally:
                with STATE_LOCK:
                    STATE["pipeline_running"] = False
                    STATE["pipeline_proc"] = None

        th = threading.Thread(target=runner_thread, daemon=True)
        th.start()

    return jsonify({"status": "started"})


@app.route("/api/pipeline-status")
def api_pipeline_status():
    """Get live pipeline logs and status."""
    with STATE_LOCK:
        return jsonify({
            "running": STATE.get("pipeline_running", False),
            "logs": STATE.get("pipeline_logs", []),
        })


def ensure_cloudflared() -> Path | None:
    """Download official standalone cloudflared binary if not present."""
    TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    if CLOUDFLARED_PATH.exists() and CLOUDFLARED_PATH.stat().st_size > 1000000:
        return CLOUDFLARED_PATH

    system_cf = shutil.which("cloudflared")
    if system_cf:
        return Path(system_cf)

    print("\n[CLOUDFLARE] Downloading lightweight cloudflared tool from official GitHub releases...")
    try:
        import urllib.request
        urllib.request.urlretrieve(CLOUDFLARED_URL, str(CLOUDFLARED_PATH))
        print(f"[CLOUDFLARE] Successfully installed cloudflared to: {CLOUDFLARED_PATH}")
        return CLOUDFLARED_PATH
    except Exception as err:
        print(f"[WARN] Could not automatically download cloudflared: {err}")
        return None


def start_cloudflare_tunnel(port: int):
    """Start Cloudflare Quick Tunnel and capture the generated public HTTPS URL."""
    cf_bin = ensure_cloudflared()
    if not cf_bin or not cf_bin.exists():
        print("[WARN] Cloudflare tunnel binary unavailable. Running in local-only mode.")
        return

    # Terminate any orphaned cloudflared instances first
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/IM", "cloudflared.exe"], capture_output=True)
    except Exception:
        pass

    print("\n[CLOUDFLARE] Starting Cloudflare Quick Tunnel...")
    try:
        proc = subprocess.Popen(
            [str(cf_bin), "tunnel", "--url", f"http://127.0.0.1:{port}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        def monitor_tunnel_output():
            tunnel_url_found = False
            for line in iter(proc.stderr.readline, ""):
                match = re.search(r"https://[-a-zA-Z0-9]+\.trycloudflare\.com", line)
                if match and not tunnel_url_found:
                    tunnel_url = match.group(0)
                    tunnel_url_found = True
                    with STATE_LOCK:
                        STATE["public_tunnel_url"] = tunnel_url

                    print("\n" + "=" * 72)
                    print(" [*] HOMECARTEL MARKETING AUTOMATION DASHBOARD IS LIVE!")
                    print(f" [>] Local URL : http://127.0.0.1:{port}")
                    print(f" [>] PUBLIC URL: {tunnel_url}  <-- SHARE THIS LINK!")
                    print("=" * 72 + "\n")

        th = threading.Thread(target=monitor_tunnel_output, daemon=True)
        th.start()
    except Exception as err:
        print(f"[WARN] Failed starting Cloudflare Tunnel: {err}")


GUARD_PORT = 5001
_guard_socket = None


def acquire_single_instance_lock() -> bool:
    """Claim a lock so only one dashboard runs at a time.

    Two instances mean two IG scheduler threads over one queue file (duplicate
    posts) and a tunnel fight, since start_cloudflare_tunnel kills cloudflared
    globally. Must be called before anything with side effects.
    """
    global _guard_socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):  # Windows: prevent hijacking the port
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    try:
        sock.bind(("127.0.0.1", GUARD_PORT))
        sock.listen(1)
    except OSError:
        sock.close()
        return False
    _guard_socket = sock  # held for process lifetime
    return True


def trim_log_file(path: Path, max_lines: int = 2000) -> None:
    """Keep the appended launcher log from growing without bound."""
    try:
        if not path.exists() or path.stat().st_size < 512_000:
            return
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        if len(lines) > max_lines:
            path.write_text("".join(lines[-max_lines:]), encoding="utf-8")
    except Exception as err:
        print(f"[WARN] Could not trim {path.name}: {err}")


def main():
    parser = argparse.ArgumentParser(description="HomeCartel Marketing Studio Web Dashboard")
    parser.add_argument("--port", type=int, default=5000, help="Web server port (default: 5000)")
    parser.add_argument("--no-tunnel", action="store_true", help="Disable Cloudflare public tunnel")
    parser.add_argument("--force", action="store_true",
                        help="Start even if another instance holds the lock")
    args = parser.parse_args()

    # Before any side effects - exiting after the cloudflared taskkill would
    # break the tunnel of the instance that is already running.
    if not args.force and not acquire_single_instance_lock():
        print("\n[INFO] Dashboard is already running - not starting a second copy.")
        print(f"[INFO] Open it at http://127.0.0.1:{args.port}")
        print("[INFO] Use --force only if you are certain no other instance is live.")
        sys.exit(0)

    trim_log_file(Path(__file__).resolve().parent / "dashboard.log")

    port = args.port
    print("\n" + "=" * 72)
    print(" HOMECARTEL COLLECTION CATEGORY FEED • NOCTURNE DASHBOARD")
    print(f" Storage Directory: {get_base_directory()}")
    print("=" * 72)

    if not args.no_tunnel:
        start_cloudflare_tunnel(port)
    else:
        print(f"\n[INFO] Dashboard running locally at: http://127.0.0.1:{port}")
        print("[WARN] Instagram publishing needs the public tunnel and will fail with --no-tunnel.")

    pending = [j for j in load_pending_ig_posts() if j.get("status") == "pending"]
    if pending:
        print(f"[IG-SCHEDULER] {len(pending)} scheduled Instagram post(s) pending.")
    threading.Thread(target=ig_scheduler_loop, daemon=True).start()

    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
