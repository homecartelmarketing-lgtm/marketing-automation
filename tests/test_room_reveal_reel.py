"""Unit tests for the Room Reveal Reel pipeline (timeline, prompts, route)."""

from __future__ import annotations

import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask
from PIL import Image, ImageDraw

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

routes_dir = REPO_ROOT / "UI Control"
if str(routes_dir) not in sys.path:
    sys.path.insert(0, str(routes_dir))

from content_automation.foreign_key import generate_foreign_key, resolve_table_prefix
from generate_room_reveal_reel_pipeline import (
    ALL_STATES,
    FINAL_SECONDS,
    KEEP_IDENTICAL_SUFFIX,
    OUTRO_FRAME,
    OUTRO_FRAMES,
    OUTRO_SECONDS,
    REVEAL_ORDER,
    STATE_FRAMES,
    TOTAL_FRAMES,
    TOTAL_SECONDS,
    VIDEO_FPS,
    DEFAULT_REMOVAL_PROMPTS,
    build_removal_plan_instruction,
    cut_frames,
    edge_density,
    evaluate_removal_step,
    final_sequence,
    image_similarity,
    parse_removal_plan,
    reel_sequence,
    resolve_outro_card,
    sfx_hits,
)
from routes.room_reveal_reel import PHASE_LABELS, TOTAL_PHASES, update_phase_from_log
import generate_room_build_up_reel_pipeline as build_up
from content_automation.errors import ProviderTimeout


class RoomRevealTimelineTests(unittest.TestCase):
    def test_frames_add_up_to_the_build_up_duration(self):
        self.assertEqual(STATE_FRAMES, (24, 20, 20, 36))
        self.assertEqual(TOTAL_FRAMES, 100)
        self.assertAlmostEqual(TOTAL_SECONDS, 3.333, places=3)
        self.assertEqual(len(STATE_FRAMES), len(REVEAL_ORDER))

    def test_cut_frames(self):
        self.assertEqual(cut_frames(), (24, 44, 64))

    def test_reveal_order_starts_empty_and_ends_on_the_finished_room(self):
        self.assertEqual(REVEAL_ORDER, ("Empty", "Layer 1", "Layer 2", "Full"))

    def test_reel_sequence_uses_the_playing_order(self):
        images = {state: Path(f"{state}.png") for state in ALL_STATES}
        sequence = [path.stem for path in reel_sequence(images)]
        self.assertEqual(tuple(sequence), REVEAL_ORDER)

    def test_final_sequence_appends_the_outro_card(self):
        images = {state: Path(f"{state}.png") for state in ALL_STATES}
        sequence = final_sequence(images, Path("outro.jpg"))
        self.assertEqual([path.stem for path in sequence], [*REVEAL_ORDER, "outro"])

    def test_sfx_hits(self):
        hits = sfx_hits()
        self.assertEqual(
            hits,
            [
                ("whoosh", 0.08),
                ("pop", 0.8),
                ("pop", 1.467),
                ("pop", 2.133),
                ("whoosh", 3.333),
            ],
        )
        self.assertEqual(
            [kind for kind, _ in hits].count("whoosh"), 2, "whoosh only at the open and on the outro"
        )
        self.assertTrue(all(second < FINAL_SECONDS for _, second in hits))
        self.assertAlmostEqual(OUTRO_FRAME / VIDEO_FPS, 3.333, places=3)

    def test_outro_card_timing_and_asset(self):
        self.assertEqual(OUTRO_FRAME, TOTAL_FRAMES)
        self.assertEqual(OUTRO_FRAMES, round(OUTRO_SECONDS * VIDEO_FPS))
        self.assertAlmostEqual(FINAL_SECONDS, TOTAL_SECONDS + OUTRO_SECONDS, places=6)
        card = resolve_outro_card()
        self.assertTrue(card.is_file())
        self.assertEqual(card.name, "outro_layout.jpg")


class RoomRevealPromptTests(unittest.TestCase):
    def test_removal_plan_instruction_pins_the_camera(self):
        instruction = build_removal_plan_instruction("Chandelier", "Mina Chandelier")
        self.assertIn("room reveal", instruction)
        self.assertIn("Mina Chandelier", instruction)
        self.assertIn("camera never moves", instruction)
        self.assertIn('"prompts"', instruction)
        self.assertIn("3 CUMULATIVE", instruction)

    def test_parse_removal_plan_reads_json(self):
        raw = json.dumps({"inventory": ["sofa", "rug"], "prompts": ["a", "b", "c"]})
        plan = parse_removal_plan(f"Here you go:\n```json\n{raw}\n```")
        self.assertFalse(plan["used_fallback"])
        self.assertEqual(plan["inventory"], ["sofa", "rug"])
        self.assertEqual(len(plan["prompts"]), 3)
        for prompt in plan["prompts"]:
            self.assertTrue(prompt.endswith(KEEP_IDENTICAL_SUFFIX.strip()))
            self.assertIn("camera is locked on a tripod", prompt)

    def test_parse_removal_plan_pads_short_answers_with_defaults(self):
        plan = parse_removal_plan(json.dumps({"prompts": ["only one"]}))
        self.assertTrue(plan["used_fallback"])
        self.assertEqual(len(plan["prompts"]), 3)
        self.assertEqual(plan["prompts"][0], "only one" + KEEP_IDENTICAL_SUFFIX)
        self.assertEqual(
            plan["prompts"][1], DEFAULT_REMOVAL_PROMPTS[1] + KEEP_IDENTICAL_SUFFIX
        )

    def test_parse_removal_plan_never_leaves_prose_unpadded(self):
        plan = parse_removal_plan("Sorry, I cannot help with that.")
        self.assertTrue(plan["used_fallback"])
        self.assertEqual(
            plan["prompts"],
            [text + KEEP_IDENTICAL_SUFFIX for text in DEFAULT_REMOVAL_PROMPTS],
        )

    def test_parse_removal_plan_does_not_double_the_suffix(self):
        prompt = "Remove the sofa." + KEEP_IDENTICAL_SUFFIX
        plan = parse_removal_plan(json.dumps({"prompts": [prompt, prompt, prompt]}))
        self.assertEqual(plan["prompts"][0].count("camera is locked on a tripod"), 1)


class RoomRevealImageChecksTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dir = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def _busy_room(self, name: str) -> Path:
        image = Image.new("RGB", (270, 480), (140, 140, 140))
        draw = ImageDraw.Draw(image)
        for index in range(12):
            left = 10 + (index % 4) * 62
            top = 20 + (index // 4) * 120
            draw.rectangle([left, top, left + 46, top + 96], fill=(60, 70, 80), outline=(255, 255, 255))
        path = self.dir / name
        image.save(path)
        return path

    def _bare_room(self, name: str) -> Path:
        path = self.dir / name
        Image.new("RGB", (270, 480), (140, 140, 140)).save(path)
        return path

    def test_edge_density_drops_when_the_room_empties(self):
        self.assertGreater(edge_density(self._busy_room("busy.png")), edge_density(self._bare_room("bare.png")))

    def test_removal_step_passes_when_room_is_kept_and_detail_drops(self):
        busy = self._busy_room("prev.png")
        bare = self._bare_room("next.png")
        ok, metrics = evaluate_removal_step(busy, bare)
        self.assertTrue(ok)
        self.assertGreaterEqual(metrics["similarity"], 0.72)
        self.assertGreater(metrics["prev_detail"], metrics["new_detail"])

    def test_removal_step_fails_when_the_camera_re_angled(self):
        busy = self._busy_room("prev.png")
        other = self.dir / "other.png"
        Image.new("RGB", (270, 480), (10, 10, 10)).save(other)
        self.assertLess(image_similarity(busy, other), 0.72)
        ok, _ = evaluate_removal_step(busy, other)
        self.assertFalse(ok)


class RoomRevealRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)
        self.common = importlib.import_module("routes.common")
        self.marketing_patch = patch.object(self.common, "MARKETING_DIR", self.workspace)
        self.overrides_patch = patch.object(
            self.common, "OVERRIDES_FILE", self.workspace / "output" / "config_overrides.json"
        )
        self.marketing_patch.start()
        self.overrides_patch.start()

        sys.modules.pop("routes.room_reveal_reel", None)
        self.module = importlib.import_module("routes.room_reveal_reel")
        self.app = Flask(__name__)
        self.app.register_blueprint(self.module.room_reveal_reel_bp)
        self.client = self.app.test_client()

    def tearDown(self):
        self.overrides_patch.stop()
        self.marketing_patch.stop()
        self.temp.cleanup()

    def test_foreign_key_prefix(self):
        self.assertEqual(resolve_table_prefix("tblRoomRevealReel", "Room Reveal Reel"), "RRV-REEL-SET")
        self.assertEqual(
            generate_foreign_key("tblRoomRevealReel", 7, "Room Reveal Reel"), "RRV-REEL-SET-7"
        )

    def test_phase_labels(self):
        self.assertEqual(TOTAL_PHASES, 7)
        self.assertEqual(sorted(PHASE_LABELS), [1, 2, 3, 4, 5, 6, 7])
        self.assertIn("Removal Plan", PHASE_LABELS[5])
        self.assertIn("Removals", PHASE_LABELS[6])
        self.assertIn("Build-Up Assembly", PHASE_LABELS[7])
        self.assertIn("Outro", PHASE_LABELS[7])

    def test_phase_detection_never_moves_backwards(self):
        state = {"current_phase": "", "current_phase_index": 0}
        update_phase_from_log(state, "[PHASE 3/7] Claude Blending Prompt")
        self.assertEqual(state["current_phase_index"], 3)
        update_phase_from_log(state, "[PHASE 2/7] something older")
        self.assertEqual(state["current_phase_index"], 3)

    def test_fixtures_endpoint(self):
        response = self.client.get("/api/room-reveal-reel/fixtures")
        self.assertEqual(response.status_code, 200)
        fixtures = response.get_json()["fixtures"]
        self.assertEqual(len(fixtures), 1)
        self.assertEqual(fixtures[0]["id"], "room-reveal")
        self.assertEqual(fixtures[0]["name"], "Room Reveal")

    def test_counts_endpoint(self):
        with patch("content_automation.airtable_client.fetch_status_breakdown", return_value={"P": 1, "C": 4, "D": 0, "FM": 0}):
            response = self.client.get("/api/room-reveal-reel/counts?refresh=true")
        self.assertEqual(response.status_code, 200)
        counts = response.get_json()["counts"]["room-reveal"]
        self.assertEqual(counts["completed"], 4)

    def test_status_endpoint(self):
        response = self.client.get("/api/room-reveal-reel/status")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "idle")
        self.assertEqual(data["total_phases"], 7)

    def test_moodboard_and_prompt_overrides_persist(self):
        overrides = self.workspace / "output" / "config_overrides.json"
        with patch.object(self.module, "is_authorized", return_value=True):
            moodboard = self.client.post(
                "/api/room-reveal-reel/moodboard", json={"moodboard_id": "de5f4ff8-518c-4d6b-b606-ce1d5dac51f3"}
            )
            prompt = self.client.post(
                "/api/room-reveal-reel/prompt", json={"prompt": "Generate me a modern bedroom"}
            )
        self.assertEqual(moodboard.status_code, 200)
        self.assertEqual(prompt.status_code, 200)
        saved = json.loads(overrides.read_text(encoding="utf-8"))
        self.assertEqual(saved["KREA_MOODBOARD_ID_ROOM_REVEAL_REEL"], "de5f4ff8-518c-4d6b-b606-ce1d5dac51f3")
        self.assertEqual(saved["PROMPT_ROOM_REVEAL_REEL"], "Generate me a modern bedroom")

    def test_blank_overrides_are_rejected(self):
        with patch.object(self.module, "is_authorized", return_value=True):
            self.assertEqual(self.client.post("/api/room-reveal-reel/moodboard", json={}).status_code, 400)
            self.assertEqual(self.client.post("/api/room-reveal-reel/prompt", json={"prompt": "  "}).status_code, 400)


class SfxBudgetTests(unittest.TestCase):
    def test_elevenlabs_attempt_is_time_bounded(self):
        seen: dict[str, object] = {}

        class WedgedFal:
            def generate_elevenlabs_sound_effect(self, prompt, *, duration=1.0, max_wait=None):
                seen["max_wait"] = max_wait
                raise ProviderTimeout("fal.ai request stuck in queue")

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)

            def fake_fallback(kind, destination):
                destination.write_bytes(b"RIFF")
                return destination

            with patch.object(build_up, "synthesize_fallback_sfx", side_effect=fake_fallback):
                sfx = build_up.ensure_sfx_assets(WedgedFal(), folder)

        self.assertEqual(seen["max_wait"], build_up.SFX_MAX_WAIT_SECONDS)
        self.assertLessEqual(build_up.SFX_MAX_WAIT_SECONDS, 120)
        self.assertTrue(sfx["pop"].name.endswith("_fallback.wav"))
        self.assertTrue(sfx["whoosh"].name.endswith("_fallback.wav"))


if __name__ == "__main__":
    unittest.main()
