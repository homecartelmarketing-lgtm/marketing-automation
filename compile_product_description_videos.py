"""Compile 9:16 Video Reels for Product Closeup w/ Description.

Workflow:
1. Inspects Airtable records that have 'Product Closeup Description Converted' attached.
2. Resolves 'outro_layout.jpg' (from local assets or record attachment).
3. Generates luxury background music via Fal AI ElevenLabs Music API (fal-ai/elevenlabs/music).
4. Assembles 9:16 vertical MP4 video reel (Slide 1: Converted Closeup Card ~5s -> Fade transition -> Slide 2: Outro ~3s).
5. Appends log to 'output/logs/product_closeup_video_compilation_logs.json'.
6. Uploads video to Airtable attachment field 'Product Closeup Video Reel' and updates Status = 'Complete'.
7. Saves local copy to 'output/content/product_closeup_video/...'.

Usage::

    python compile_product_description_videos.py
    python compile_product_description_videos.py --target chandelier --limit 1
    python compile_product_description_videos.py --target pendant_lights --music-prompt "Warm acoustic lounge"
    python compile_product_description_videos.py --record-id recXXXXXXXXXXXXXX
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import cv2
import imageio_ffmpeg
import numpy as np
from PIL import Image
import requests

from content_automation.config import load_settings
from content_automation.errors import AutomationError
from content_automation.fal_client import FalClient
from content_automation.media import download_to_temp_file
from content_automation.models import LocalImage
from content_automation.scraping import (
    ScrapeAirtableClient,
    load_scrape_settings,
)

PRODUCT_DESCRIPTION_PIPELINE_TABLES: dict[str, dict[str, str]] = {
    "chandelier": {
        "category_code": "chandelier_product_description_story",
        "label": "Chandelier Product Closeup w/ Description",
        "default_table_id": "tblDcT6jovdAbKnfw",
        "env_table_key": "AIRTABLE_TABLE_ID_CHANDELIER_PRODUCT_DESCRIPTION",
    },
    "chandeliers": {
        "category_code": "chandelier_product_description_story",
        "label": "Chandelier Product Closeup w/ Description",
        "default_table_id": "tblDcT6jovdAbKnfw",
        "env_table_key": "AIRTABLE_TABLE_ID_CHANDELIER_PRODUCT_DESCRIPTION",
    },
    "pendant_light": {
        "category_code": "pendant_lights_product_description_story",
        "label": "Pendant Light Product Closeup w/ Description",
        "default_table_id": "tblDD2w4v0Idb4jAZ",
        "env_table_key": "AIRTABLE_TABLE_ID_PENDANT_LIGHTS_PRODUCT_DESCRIPTION",
    },
    "pendant_lights": {
        "category_code": "pendant_lights_product_description_story",
        "label": "Pendant Light Product Closeup w/ Description",
        "default_table_id": "tblDD2w4v0Idb4jAZ",
        "env_table_key": "AIRTABLE_TABLE_ID_PENDANT_LIGHTS_PRODUCT_DESCRIPTION",
    },
    "floor_lamp": {
        "category_code": "floor_lamp_product_description_story",
        "label": "Floor Lamp Product Closeup w/ Description",
        "default_table_id": "tblPvHyKGByWJCMtY",
        "env_table_key": "AIRTABLE_TABLE_ID_FLOOR_LAMP_PRODUCT_DESCRIPTION",
    },
    "floor_lamps": {
        "category_code": "floor_lamp_product_description_story",
        "label": "Floor Lamp Product Closeup w/ Description",
        "default_table_id": "tblPvHyKGByWJCMtY",
        "env_table_key": "AIRTABLE_TABLE_ID_FLOOR_LAMP_PRODUCT_DESCRIPTION",
    },
    "cluster_chandelier": {
        "category_code": "cluster_chandelier_product_description_story",
        "label": "Cluster Chandelier Product Closeup w/ Description",
        "default_table_id": "tblnIOQVywHcTgAtv",
        "env_table_key": "AIRTABLE_TABLE_ID_CLUSTER_CHANDELIER_PRODUCT_DESCRIPTION",
    },
    "cluster_chandeliers": {
        "category_code": "cluster_chandelier_product_description_story",
        "label": "Cluster Chandelier Product Closeup w/ Description",
        "default_table_id": "tblnIOQVywHcTgAtv",
        "env_table_key": "AIRTABLE_TABLE_ID_CLUSTER_CHANDELIER_PRODUCT_DESCRIPTION",
    },
    "table_lamp": {
        "category_code": "table_lamps_product_description_story",
        "label": "Table Lamps Product Closeup w/ Description",
        "default_table_id": "tbl5S9JEHSrjrLwxA",
        "env_table_key": "AIRTABLE_TABLE_ID_TABLE_LAMPS_PRODUCT_DESCRIPTION",
    },
    "table_lamps": {
        "category_code": "table_lamps_product_description_story",
        "label": "Table Lamps Product Closeup w/ Description",
        "default_table_id": "tbl5S9JEHSrjrLwxA",
        "env_table_key": "AIRTABLE_TABLE_ID_TABLE_LAMPS_PRODUCT_DESCRIPTION",
    },
    "wall_light": {
        "category_code": "wall_lights_product_description_story",
        "label": "Wall Lights Product Closeup w/ Description",
        "default_table_id": "tblYqudlgjYMNRROM",
        "env_table_key": "AIRTABLE_TABLE_ID_WALL_LIGHTS_PRODUCT_DESCRIPTION",
    },
    "wall_lights": {
        "category_code": "wall_lights_product_description_story",
        "label": "Wall Lights Product Closeup w/ Description",
        "default_table_id": "tblYqudlgjYMNRROM",
        "env_table_key": "AIRTABLE_TABLE_ID_WALL_LIGHTS_PRODUCT_DESCRIPTION",
    },
    "wall_sconces": {
        "category_code": "wall_lights_product_description_story",
        "label": "Wall Lights Product Closeup w/ Description",
        "default_table_id": "tblYqudlgjYMNRROM",
        "env_table_key": "AIRTABLE_TABLE_ID_WALL_LIGHTS_PRODUCT_DESCRIPTION",
    },
}

FIELD_OUTPUT_CONVERTED = "Product Closeup Description Converted"
FIELD_OUTPUT_VIDEO = "Product Closeup Video Reel"
FIELD_ITEM_NAME = "Item Name"
FIELD_STATUS = "Status"
FIELD_SKU = "SKU"

STATUS_COMPLETE = "Complete"
DEFAULT_MUSIC_PROMPT = (
    "Smooth luxury modern lounge instrumental, warm ambient chords, elegant boutique vibe, seamless loop"
)

OUTRO_CANDIDATE_PATHS = [
    Path("assets/outro_layout.jpg"),
    Path("Outro for All Reels/Outro.jpg"),
    Path("JSON Prompts/Myth and Fact/outro_layout.jpg"),
]

LOG_DIR = Path("output") / "logs"
LOG_FILE = LOG_DIR / "product_closeup_video_compilation_logs.json"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Compile 9:16 Video Reels for Product Closeup w/ Description with Fal ElevenLabs Music."
    )
    parser.add_argument(
        "--target",
        "-t",
        choices=[
            "chandelier", "chandeliers",
            "pendant_light", "pendant_lights",
            "floor_lamp", "floor_lamps",
            "cluster_chandelier", "cluster_chandeliers",
            "table_lamp", "table_lamps",
            "wall_light", "wall_lights", "wall_sconces",
            "all",
        ],
        default="all",
        help="Target lighting category (default: all)",
    )
    parser.add_argument(
        "--table-id",
        default=None,
        help="Airtable destination table ID override",
    )
    parser.add_argument(
        "--max-items",
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Process at most N records",
    )
    parser.add_argument(
        "--record-id",
        default=None,
        help="Process a single specific Airtable record ID",
    )
    parser.add_argument(
        "--music-prompt",
        default=os.getenv("PRODUCT_CLOSEUP_MUSIC_PROMPT", DEFAULT_MUSIC_PROMPT),
        help=f"Custom prompt for Fal ElevenLabs music (default: {DEFAULT_MUSIC_PROMPT})",
    )
    parser.add_argument(
        "--no-music",
        action="store_true",
        help="Skip background music generation and compile silent video",
    )
    parser.add_argument(
        "--model",
        default="fal-ai/elevenlabs/music",
        help="Fal AI ElevenLabs music model endpoint (default: fal-ai/elevenlabs/music)",
    )
    return parser.parse_args(argv)


def append_json_log(log_entry: dict[str, Any], log_path: Path = LOG_FILE) -> None:
    """Append a log record to the JSON log file."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logs: list[dict[str, Any]] = []
    if log_path.exists():
        try:
            content = log_path.read_text(encoding="utf-8").strip()
            if content:
                logs = json.loads(content)
                if not isinstance(logs, list):
                    logs = [logs]
        except Exception:
            logs = []
    logs.append(log_entry)
    log_path.write_text(json.dumps(logs, indent=2, ensure_ascii=False), encoding="utf-8")


def extract_attachment_url(val: Any) -> str:
    if isinstance(val, list) and val:
        item = val[0]
        if isinstance(item, dict):
            return str(item.get("url") or "").strip()
        if isinstance(item, str):
            return item.strip()
    elif isinstance(val, str):
        return val.strip()
    return ""


def resolve_local_outro_path() -> Path | None:
    for candidate in OUTRO_CANDIDATE_PATHS:
        if candidate.is_file():
            return candidate.resolve()
    return None


def build_product_closeup_slideshow_video(
    closeup_image_path: Path | str,
    outro_image_path: Path | str,
    output_mp4_path: Path,
    audio_path: Path | str | None = None,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
    card_duration: float = 5.0,
    outro_duration: float = 3.0,
    fade_duration: float = 1.0,
) -> Path:
    """Build a 9:16 vertical H.264 MP4 slideshow video for Product Closeup.

    Slide 1 (Product Closeup Description Card): 5.0s duration, with 1.0s fade to black at the end.
    Slide 2 (Outro Layout): 3.0s duration, with 0.5s fade in.
    Audio: Background music merged via FFmpeg with -shortest.
    """
    closeup_p = Path(closeup_image_path)
    if not closeup_p.is_file():
        raise AutomationError(f"Cannot build video: Closeup card image missing ({closeup_p})")

    outro_p = Path(outro_image_path)
    if not outro_p.is_file():
        raise AutomationError(f"Cannot build video: Outro layout image missing ({outro_p})")

    output_mp4_path.parent.mkdir(parents=True, exist_ok=True)
    temp_raw = output_mp4_path.with_name(f"raw_{output_mp4_path.name}")

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(temp_raw), fourcc, fps, (width, height))

    # 1. Slide 1: Converted Product Closeup Card (with fade to black transition)
    with Image.open(closeup_p) as pil_img:
        pil_img = pil_img.convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
        card_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

        total_card_frames = int(card_duration * fps)
        fade_frames = int(fade_duration * fps)
        normal_card_frames = max(0, total_card_frames - fade_frames)

        for _ in range(normal_card_frames):
            writer.write(card_bgr)

        for i in range(fade_frames):
            factor = 1.0 - (i / max(1, fade_frames))
            faded = (card_bgr.astype(np.float32) * factor).astype(np.uint8)
            writer.write(faded)

    # 2. Slide 2: Outro Layout (with fade in)
    with Image.open(outro_p) as outro_pil:
        outro_pil = outro_pil.convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
        outro_bgr = cv2.cvtColor(np.array(outro_pil), cv2.COLOR_RGB2BGR)

        total_outro_frames = int(outro_duration * fps)
        fade_in_frames = int(0.5 * fps)

        for i in range(fade_in_frames):
            factor = i / max(1, fade_in_frames)
            faded_in = (outro_bgr.astype(np.float32) * factor).astype(np.uint8)
            writer.write(faded_in)

        for _ in range(max(0, total_outro_frames - fade_in_frames)):
            writer.write(outro_bgr)

    writer.release()

    # 3. FFmpeg encoding (with optional audio merge)
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    if audio_path and Path(audio_path).is_file():
        cmd = [
            ffmpeg_exe, "-y",
            "-i", str(temp_raw),
            "-i", str(audio_path),
            "-c:v", "libx264",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            "-movflags", "+faststart",
            str(output_mp4_path),
        ]
    else:
        cmd = [
            ffmpeg_exe, "-y",
            "-i", str(temp_raw),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(output_mp4_path),
        ]

    completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if temp_raw.exists():
        try:
            temp_raw.unlink(missing_ok=True)
        except Exception:
            pass

    if completed.returncode != 0:
        raise AutomationError(f"FFmpeg slideshow encoding failed: {completed.stderr}")

    return output_mp4_path


def compile_videos_for_table(
    fal: FalClient | None,
    airtable: ScrapeAirtableClient,
    label: str,
    category_key: str,
    max_items: int | None = None,
    record_id: str | None = None,
    music_prompt: str = DEFAULT_MUSIC_PROMPT,
    no_music: bool = False,
    music_model: str = "fal-ai/elevenlabs/music",
) -> bool:
    airtable.ensure_fields({
        FIELD_OUTPUT_VIDEO: "multipleAttachments",
        FIELD_OUTPUT_CONVERTED: "multipleAttachments",
        FIELD_STATUS: "singleSelect",
        FIELD_ITEM_NAME: "singleLineText",
    })

    records = airtable.list_records([
        FIELD_OUTPUT_CONVERTED,
        FIELD_OUTPUT_VIDEO,
        FIELD_ITEM_NAME,
        FIELD_STATUS,
        FIELD_SKU,
        "Outro",
        "Outro Layout",
    ])
    if not records:
        print(f"[OK] No records found in table {label}.")
        return True

    if record_id:
        records = [r for r in records if r["id"] == record_id]

    eligible = []
    for r in records:
        fields = r.get("fields", {})
        converted = fields.get(FIELD_OUTPUT_CONVERTED)
        video = fields.get(FIELD_OUTPUT_VIDEO)
        if not converted:
            continue
        if video and not record_id:
            continue
        eligible.append(r)

    if not eligible:
        print(f"[OK] No pending records requiring video compilation in {label}.")
        return True

    if max_items is not None:
        eligible = eligible[:max_items]

    print("=" * 68)
    print(f"[VIDEO] Compiling Product Closeup Video Reels for {label}")
    print(f"Targeting {len(eligible)} eligible record(s) | Music: {'Disabled' if no_music else 'Fal ElevenLabs'}")
    print("=" * 68)

    local_outro = resolve_local_outro_path()
    if not local_outro:
        print("[WARN] Local outro_layout.jpg not found in standard asset directories.")

    local_save_base = Path("output") / "content" / "product_closeup_video" / category_key
    local_save_base.mkdir(parents=True, exist_ok=True)

    succeeded = 0
    failed = 0

    for idx, record in enumerate(eligible, start=1):
        rec_id = record["id"]
        fields = record.get("fields", {})
        item_name = str(fields.get(FIELD_ITEM_NAME) or fields.get("SKU") or rec_id).strip()
        safe_item_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in item_name).replace(" ", "_")

        converted_url = extract_attachment_url(fields.get(FIELD_OUTPUT_CONVERTED))
        if not converted_url:
            print(f"[SKIP] Record {rec_id} ({item_name}) missing converted image URL.")
            continue

        print(f"\n[{idx}/{len(eligible)}] Compiling video for record {rec_id}: '{item_name}'")

        # Resolve Outro image (record attachment or local file)
        record_outro_url = extract_attachment_url(fields.get("Outro") or fields.get("Outro Layout"))
        outro_temp = None
        outro_file_path = None
        if record_outro_url:
            try:
                resp = requests.get(record_outro_url, stream=True, timeout=60)
                outro_temp = download_to_temp_file(
                    resp, prefix="outro_att_", suffix=".jpg", context=f"Outro for {rec_id}"
                )
                outro_file_path = outro_temp.path
            except Exception as o_err:
                print(f"[WARN] Failed downloading record outro attachment: {o_err}")

        if not outro_file_path and local_outro:
            outro_file_path = local_outro

        if not outro_file_path or not Path(outro_file_path).is_file():
            print(f"[ERROR] Cannot compile video for record {rec_id}: outro image could not be resolved.")
            failed += 1
            continue

        # Download Converted card
        card_temp = None
        audio_temp = None
        timestamp_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        try:
            card_resp = requests.get(converted_url, stream=True, timeout=60)
            card_temp = download_to_temp_file(
                card_resp, prefix="card_conv_", suffix=".jpg", context=f"Closeup card for {rec_id}"
            )

            # Generate ElevenLabs music via Fal API if requested
            if fal and not no_music and music_prompt:
                try:
                    print(f"    [MUSIC] Generating background music via Fal AI ElevenLabs ({music_model})...")
                    audio_url = fal.generate_elevenlabs_music(
                        prompt=music_prompt,
                        duration=8,
                        model=music_model,
                    )
                    if audio_url:
                        audio_resp = requests.get(audio_url, stream=True, timeout=60)
                        audio_temp = download_to_temp_file(
                            audio_resp,
                            prefix="elevenlabs_music_",
                            suffix=".mp3",
                            context=f"ElevenLabs music for {rec_id}",
                        )
                        print(f"    [OK] Downloaded ElevenLabs audio for record {rec_id}")
                except Exception as music_err:
                    print(f"    [WARN] Fal AI ElevenLabs music notice: {music_err} (proceeding without audio)")

            # Assemble video
            final_mp4_path = local_save_base / f"{safe_item_name}_{rec_id}.mp4"
            print(f"    [BUILD] Assembling 9:16 video reel (5s card + 3s outro) -> {final_mp4_path}...")
            build_product_closeup_slideshow_video(
                closeup_image_path=card_temp.path,
                outro_image_path=outro_file_path,
                output_mp4_path=final_mp4_path,
                audio_path=audio_temp.path if audio_temp else None,
                width=1080,
                height=1920,
                fps=30,
                card_duration=5.0,
                outro_duration=3.0,
                fade_duration=1.0,
            )
            print(f"    [OK] Video generated successfully ({final_mp4_path.stat().st_size // 1024} KB)")

            # Upload video to Airtable
            video_filename = f"video_{safe_item_name}_{rec_id}.mp4"
            local_video = LocalImage(final_mp4_path, video_filename, "video/mp4")
            airtable.upload_attachment(rec_id, FIELD_OUTPUT_VIDEO, local_video, video_filename)
            airtable.update_records([(rec_id, {FIELD_STATUS: STATUS_COMPLETE})])
            print(f"    [OK] Uploaded video to '{FIELD_OUTPUT_VIDEO}' and set Status = '{STATUS_COMPLETE}'")

            # Append log
            log_entry = {
                "timestamp": timestamp_str,
                "record_id": rec_id,
                "item_name": item_name,
                "category": category_key,
                "card_image_url": converted_url,
                "outro_image": str(outro_file_path),
                "music_prompt": music_prompt if (not no_music and audio_temp) else None,
                "output_video_path": str(final_mp4_path),
                "status": STATUS_COMPLETE,
            }
            append_json_log(log_entry, LOG_FILE)
            succeeded += 1

        except Exception as vid_err:
            failed += 1
            print(f"    [ERROR] Failed video compilation for record {rec_id}: {vid_err}")
            log_entry = {
                "timestamp": timestamp_str,
                "record_id": rec_id,
                "item_name": item_name,
                "category": category_key,
                "card_image_url": converted_url,
                "status": "Failed",
                "error": str(vid_err),
            }
            append_json_log(log_entry, LOG_FILE)
        finally:
            if card_temp:
                card_temp.cleanup()
            if outro_temp:
                outro_temp.cleanup()
            if audio_temp:
                audio_temp.cleanup()

    print(f"\n[SUMMARY] {label}: {succeeded} video(s) compiled successfully, {failed} failed.")
    return failed == 0


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.max_items is not None and args.max_items < 1:
        raise SystemExit("--max-items must be at least 1")

    base_settings = load_settings()
    fal = None
    if not args.no_music:
        try:
            base_settings.require({"fal"})
            fal = FalClient(api_key=base_settings.fal_key)
        except Exception as f_err:
            print(f"[WARN] Fal API key notice: {f_err}. Running without music.")

    if args.target in ("all", None):
        targets = [
            ("chandelier", PRODUCT_DESCRIPTION_PIPELINE_TABLES["chandelier"]),
            ("pendant_lights", PRODUCT_DESCRIPTION_PIPELINE_TABLES["pendant_lights"]),
            ("floor_lamps", PRODUCT_DESCRIPTION_PIPELINE_TABLES["floor_lamps"]),
            ("cluster_chandeliers", PRODUCT_DESCRIPTION_PIPELINE_TABLES["cluster_chandeliers"]),
            ("table_lamps", PRODUCT_DESCRIPTION_PIPELINE_TABLES["table_lamps"]),
            ("wall_lights", PRODUCT_DESCRIPTION_PIPELINE_TABLES["wall_lights"]),
        ]
    else:
        cfg = PRODUCT_DESCRIPTION_PIPELINE_TABLES.get(args.target.lower())
        if not cfg:
            raise AutomationError(f"Unknown target '{args.target}'.")
        targets = [(args.target.lower(), cfg)]

    overall_success = True
    for cat_key, cfg in targets:
        table_id = args.table_id or os.getenv(cfg["env_table_key"], "").strip() or cfg["default_table_id"]
        airtable = ScrapeAirtableClient(
            base_settings.airtable_token,
            base_settings.airtable_base_id,
            table_id,
        )
        if not compile_videos_for_table(
            fal=fal,
            airtable=airtable,
            label=cfg["label"],
            category_key=cat_key,
            max_items=args.max_items,
            record_id=args.record_id,
            music_prompt=args.music_prompt,
            no_music=args.no_music,
            music_model=args.model,
        ):
            overall_success = False

    return 0 if overall_success else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutomationError as error:
        print(f"[FATAL] {error}", file=sys.stderr)
        raise SystemExit(2)
