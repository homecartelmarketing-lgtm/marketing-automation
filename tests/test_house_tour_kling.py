"""House Tour Reel Kling phase: pan pattern, motion prompts, failure status, assembly."""

from __future__ import annotations

import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


def _load():
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return importlib.import_module("generate_house_tour_reel_pipeline")


MODULE = _load()


class KlingPanPatternTests(unittest.TestCase):
    def test_pan_directions_alternate_left_right(self):
        self.assertEqual(
            MODULE.KLING_DIRECTIONS,
            {s: ("left" if s % 2 == 1 else "right") for s in MODULE.SLOTS},
        )

    def test_motion_prompt_encodes_direction_and_room(self):
        for slot, direction in MODULE.KLING_DIRECTIONS.items():
            with self.subTest(slot=slot):
                prompt = MODULE.kling_motion_prompt(slot)
                room_word = MODULE.SLOT_ROOMS[slot].split()[0].lower()
                if direction == "left":
                    self.assertIn("right to left", prompt)
                else:
                    self.assertIn("left to right", prompt)
                self.assertIn(room_word, prompt.lower())
                self.assertIn(MODULE.SLOT_LABELS[slot].lower(), prompt.lower())

    def test_caption_is_gone(self):
        self.assertFalse(hasattr(MODULE, "CAPTION_FIELD"))
        self.assertFalse(hasattr(MODULE, "CAPTION_DEFAULT"))


def _fake_clients(fal=None, airtable=None):
    return SimpleNamespace(
        fal=fal or Mock(),
        airtable=airtable or Mock(),
    )


def _fields_with_blends():
    return {
        MODULE.BLENDED_FIELDS[s]: [{"url": f"https://cdn.example/blend{s}.jpg"}]
        for s in MODULE.SLOTS
    }


class Phase5KlingTests(unittest.TestCase):
    def test_success_uploads_four_clips_and_marks_generated(self):
        clients = _fake_clients()
        clients.fal.generate_kling_video.return_value = "https://f.example/clip.mp4"
        clients.fal.upload_file.return_value = "https://fal.media/staged_blend.jpg"
        fake_resp = Mock()
        fake_resp.content = b"fakevideobytes"
        updates = []

        def record_update(calls):
            updates.extend(calls)

        clients.airtable.update_records.side_effect = record_update
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            with patch.object(MODULE.requests, "get", return_value=fake_resp):
                clips = MODULE.phase6_kling(clients, "rec1", _fields_with_blends(), workdir)
            self.assertIsNotNone(clips)
            assert clips is not None
            self.assertEqual(len(clips), len(MODULE.SLOTS))
            for clip in clips:
                self.assertTrue(clip.is_file())
        self.assertEqual(clients.fal.generate_kling_video.call_count, len(MODULE.SLOTS))
        # Slot 1 is an odd slot (pan left -> 'right to left'), 3 s duration,
        # and fal-storage URL (not the Airtable URL).
        all_calls = clients.fal.generate_kling_video.call_args_list
        slot1_call = next(
            c for c in all_calls if MODULE.SLOT_LABELS[1].lower() in c.kwargs["prompt"].lower()
        )
        self.assertIn("right to left", slot1_call.kwargs["prompt"])
        self.assertEqual(slot1_call.kwargs["duration"], 3)
        self.assertEqual(slot1_call.kwargs["image_url"], "https://fal.media/staged_blend.jpg")
        statuses = [u[1].get(MODULE.STATUS_FIELD) for u in updates]
        self.assertIn(MODULE.STATUS_KLING, statuses)
        self.assertNotIn(MODULE.STATUS_KLING_FAILED, statuses)

    def test_upload_failure_falls_back_to_airtable_url(self):
        clients = _fake_clients()
        clients.fal.generate_kling_video.return_value = "https://f.example/clip.mp4"
        clients.fal.upload_file.side_effect = Exception("storage down")
        fake_resp = Mock()
        fake_resp.content = b"fakevideobytes"
        fields = _fields_with_blends()
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(MODULE.requests, "get", return_value=fake_resp):
                clips = MODULE.phase6_kling(clients, "rec1", fields, Path(tmp))
        self.assertIsNotNone(clips)
        for call in clients.fal.generate_kling_video.call_args_list:
            self.assertTrue(call.kwargs["image_url"].startswith("https://cdn.example/"))

    def test_resume_merges_fresh_blend_urls_from_airtable(self):
        """Phase 5 recovers blends uploaded by an earlier Phase 4 attempt."""
        clients = _fake_clients()
        clients.fal.generate_kling_video.return_value = "https://f.example/clip.mp4"
        clients.fal.upload_file.return_value = "https://fal.media/staged.jpg"
        clients.airtable.record.return_value = {"fields": _fields_with_blends()}
        fake_resp = Mock()
        fake_resp.content = b"fakevideobytes"
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(MODULE.requests, "get", return_value=fake_resp):
                clips = MODULE.phase6_kling(clients, "rec1", {}, Path(tmp))
        self.assertIsNotNone(clips)
        assert clips is not None
        self.assertEqual(len(clips), len(MODULE.SLOTS))

    def test_failure_marks_generation_failed_via_kling(self):
        clients = _fake_clients()
        clients.fal.generate_kling_video.side_effect = Exception("kling down")
        updates = []
        clients.airtable.update_records.side_effect = lambda calls: updates.extend(calls)
        with tempfile.TemporaryDirectory() as tmp:
            clips = MODULE.phase6_kling(clients, "rec1", _fields_with_blends(), Path(tmp))
        self.assertIsNone(clips)
        statuses = [u[1].get(MODULE.STATUS_FIELD) for u in updates]
        self.assertIn(MODULE.STATUS_KLING_FAILED, statuses)


def _fields_with_inputs():
    fields = {}
    for s in MODULE.SLOTS:
        fields[MODULE.INTERIOR_FIELDS[s]] = [{"url": f"https://cdn.example/int{s}.jpg"}]
        fields[MODULE.FURNITURE_FIELDS[s]] = [{"url": f"https://cdn.example/furn{s}.jpg"}]
        fields[MODULE.PROMPT_FIELDS[s]] = f"blend prompt {s}"
        fields[MODULE.ITEM_NAME_FIELDS[s]] = f"Lamp {s} | Table Lamp"
    return fields


class Phase4ToPhase5HandoffTests(unittest.TestCase):
    """Regression test for the reported failure:
    'Kling image-to-video failed: slot 2 has no blended image'.

    Phase 4 must hand its fresh blend URLs into the shared ``fields`` dict
    that Phase 5 reads -- the row state was fetched before Phase 4 ran.
    """

    def test_phase4_hands_blend_urls_to_phase5(self):
        clients = _fake_clients()
        clients.fal.generate.return_value = "https://f.example/blend.jpg"
        clients.fal.generate_kling_video.return_value = "https://f.example/clip.mp4"
        clients.fal.upload_file.return_value = "https://fal.media/staged.jpg"
        fake_resp = Mock()
        fake_resp.content = b"fakeimagebytes"

        def fake_tag(*args, **kwargs):
            dest = Path(kwargs["destination"])
            dest.write_bytes(b"tagged")
            return None, None

        fields = _fields_with_inputs()
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            with patch.object(MODULE.requests, "get", return_value=fake_resp), patch(
                "content_automation.item_tagger.tag_blended_image", side_effect=fake_tag
            ):
                stills = MODULE.phase5_blends(clients, "rec1", fields, workdir)
                # THE assertion that fails on the old code: fresh blend URLs
                # must be visible in ``fields`` for Phase 5.
                for s in MODULE.SLOTS:
                    self.assertTrue(
                        MODULE._first_attachment_url(fields, MODULE.BLENDED_FIELDS[s]),
                        f"slot {s} blend URL missing from fields after Phase 4",
                    )
                clips = MODULE.phase6_kling(clients, "rec1", fields, workdir)
        self.assertEqual(len(stills), len(MODULE.SLOTS))
        self.assertIsNotNone(clips)
        assert clips is not None
        self.assertEqual(len(clips), len(MODULE.SLOTS))


class PreCraftedInteriorPromptTests(unittest.TestCase):
    def test_default_interior_prompts_covers_all_eleven_slots(self):
        self.assertEqual(len(MODULE.DEFAULT_INTERIOR_PROMPTS), 11)
        for slot in MODULE.SLOTS:
            prompt = MODULE.DEFAULT_INTERIOR_PROMPTS[slot]
            self.assertGreater(len(prompt), 100)
            self.assertIn("Japandi", prompt)
            self.assertIn("8k", prompt)

    def test_required_fields_cover_interior_prompts(self):
        for slot in MODULE.SLOTS:
            self.assertEqual(
                MODULE.REQUIRED_FIELDS[f"Interior Prompt{slot}"], "multilineText"
            )

    def test_resolve_slot_settings_uses_unified_moodboard(self):
        for slot in MODULE.SLOTS:
            mb_id, prompt = MODULE.resolve_slot_settings(slot)
            self.assertEqual(mb_id, "fda7090c-787b-4116-94cd-3feef613eaaa")
            self.assertEqual(prompt, MODULE.DEFAULT_INTERIOR_PROMPTS[slot])

    def test_resolve_slot_settings_respects_overrides(self):
        mb_id, prompt = MODULE.resolve_slot_settings(
            1,
            prompt_override="Custom living room prompt",
            moodboard_override="custom-mb-123",
        )
        self.assertEqual(mb_id, "custom-mb-123")
        self.assertEqual(prompt, "Custom living room prompt")

    def test_resolve_slot_settings_reads_from_fields(self):
        fields = {MODULE.INTERIOR_PROMPT_FIELDS[2]: "Prompt stored on Airtable row"}
        _mb_id, prompt = MODULE.resolve_slot_settings(2, fields=fields)
        self.assertEqual(prompt, "Prompt stored on Airtable row")


class Phase2InteriorsTests(unittest.TestCase):
    def test_phase2_interiors_generates_and_updates_status(self):
        clients = _fake_clients()
        clients.krea = Mock()
        clients.krea.generate_image.return_value = 'https://krea.ai/gen.jpg'
        fields = {
            MODULE.FURNITURE_FIELDS[s]: [{'url': f'https://cdn.example/prod{s}.jpg'}]
            for s in MODULE.SLOTS
        }
        updates = []
        clients.airtable.update_records.side_effect = lambda calls: updates.extend(calls)
        MODULE.phase2_interiors(clients, 'rec1', fields)
        self.assertEqual(clients.krea.generate_image.call_count, 11)
        for call in clients.krea.generate_image.call_args_list:
            self.assertEqual(call.kwargs['moodboard_id'], 'fda7090c-787b-4116-94cd-3feef613eaaa')
            self.assertEqual(call.kwargs['aspect_ratio'], '9:16')
        statuses = [u[1].get(MODULE.STATUS_FIELD) for u in updates if MODULE.STATUS_FIELD in u[1]]
        self.assertIn(MODULE.STATUS_INTERIOR, statuses)


class Phase2AnalyzeInteriorsTests(unittest.TestCase):
    def test_phase2_analyze_interiors_calls_claude_vision_and_marks_status(self):
        clients = _fake_clients()
        clients.fal.generate_vision_prompt.return_value = (
            "1. RECOMMENDED CATEGORY: table_lamps\n"
            "2. PHYSICAL PLACEMENT: On the nightstand table.\n"
            "3. DESIGN: Fluted ceramic with warm linen shade."
        )
        fields = {
            MODULE.INTERIOR_FIELDS[s]: [{'url': f'https://krea.ai/int{s}.jpg'}]
            for s in MODULE.SLOTS
        }
        updates = []
        clients.airtable.update_records.side_effect = lambda calls: updates.extend(calls)
        MODULE.phase2_analyze_interiors(clients, 'rec1', fields)
        self.assertEqual(clients.fal.generate_vision_prompt.call_count, 11)
        for call in clients.fal.generate_vision_prompt.call_args_list:
            self.assertEqual(call.kwargs['model'], 'anthropic/claude-sonnet-5')
            self.assertIn("RECOMMENDED CATEGORY", call.kwargs['prompt'])
        statuses = [u[1].get(MODULE.STATUS_FIELD) for u in updates if MODULE.STATUS_FIELD in u[1]]
        self.assertIn(MODULE.STATUS_INTERIOR_ANALYZED, statuses)
        # Verify fields updated with analysis
        for s in MODULE.SLOTS:
            self.assertIn(MODULE.INTERIOR_ANALYSIS_FIELDS[s], fields)

    def test_extract_category_from_analysis(self):
        cases = [
            ("RECOMMENDED CATEGORY: table_lamps", "table_lamps"),
            ("1. Recommended Category: pendant_lights\nPlacement: ceiling", "pendant_lights"),
            ("Suggesting a luxury chandelier centered above the lounge", "chandeliers"),
            ("A tall floor lamp standing in the corner beside sofa", "floor_lamps"),
            ("Wall sconce mounted at eye level beside mirror", "wall_sconces"),
            ("Flush-mounted ceiling light centered on ceiling", "ceiling_mounted"),
            ("Unrelated text with no recognized lighting", "default_val"),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                cat = MODULE.extract_category_from_analysis(text, "default_val")
                self.assertEqual(cat, expected)

    def test_extract_room_title_from_analysis(self):
        cases = [
            ("5. ROOM TITLE: living room lounge", 1, "living room lounge"),
            ("Room Title: 'primary suite'", 2, "primary suite"),
            ("Editorial Room Title: dining nook", 3, "dining nook"),
            ("A luxury space centered above the dining room table", 3, ""),
            ("Empty analysis string", 1, ""),
            ("", 2, ""),
        ]
        for text, slot, expected in cases:
            with self.subTest(text=text, slot=slot):
                title = MODULE.extract_room_title_from_analysis(text, slot)
                self.assertEqual(title, expected)

    def test_claude_instruction_includes_interior_analysis(self):
        inst_without = MODULE._claude_instruction(1)
        self.assertNotIn("Room Interior Analysis & Placement Guidance", inst_without)

        inst_with = MODULE._claude_instruction(1, analysis_notes="Place on left nightstand surface")
        self.assertIn("Room Interior Analysis & Placement Guidance", inst_with)
        self.assertIn("Place on left nightstand surface", inst_with)


class AssemblyFilterTests(unittest.TestCase):
    SLIDES = [
        ("Alejandro Deux", "Chandelier"),
        ("Kanogan", "Table Lamp"),
        ("Vasteras", "Pendant Light"),
        ("Blevins", "Floor Lamp"),
    ]

    def test_reference_pacing_twenty_two_seconds_snap_cuts(self):
        titles = ["mini home tour", "living room", "dining room"] + [""] * 3 + ["kitchen"] + [""] * 3 + ["guest bedroom"]
        filt, out_label, total = MODULE.build_house_tour_filter(
            self.SLIDES,
            with_outro=False,
            pacing="reference",
            cut_style="snap",
            overlay_style="reference",
            room_titles=titles,
        )
        self.assertAlmostEqual(total, 22.0, places=2)
        self.assertIn("concat=n=11:v=1:a=0", filt)
        self.assertNotIn("xfade", filt)
        self.assertIn("Poppins-Medium", filt)
        self.assertIn("mini home tour", filt)
        self.assertIn("living room", filt)
        self.assertIn("dining room", filt)
        self.assertIn("kitchen", filt)
        self.assertIn("guest bedroom", filt)
        self.assertIn("fontsize=44", filt)
        self.assertIn("y=480", filt)
        self.assertIn("x=(w-text_w)/2", filt)
        self.assertTrue(out_label.startswith("vt"))

    def test_reference_serif_milestone_windows(self):
        titles = ["mini home tour", "living room", "dining room"] + [""] * 3 + ["kitchen"] + [""] * 3 + ["guest bedroom"]
        filt, _out_label, _total = MODULE.build_house_tour_filter(
            with_outro=False,
            pacing="reference",
            cut_style="snap",
            overlay_style="reference",
            room_titles=titles,
        )
        import re

        windows = re.findall(r"between\(t,(\d+\.\d+),(\d+\.\d+)\)", filt)
        # 5 milestone rooms with titles have text
        self.assertEqual(len(windows), 5)
        # First window starts at t=0.00, ends at 2.00
        self.assertEqual(float(windows[0][0]), 0.0)
        self.assertEqual(float(windows[0][1]), 2.0)
        # Second window starts at t=2.00, ends at 4.00
        self.assertEqual(float(windows[1][0]), 2.0)
        self.assertEqual(float(windows[1][1]), 4.0)

    def test_zero_fallback_when_room_titles_empty(self):
        filt, _out_label, _total = MODULE.build_house_tour_filter(
            with_outro=False,
            pacing="reference",
            cut_style="snap",
            overlay_style="reference",
            room_titles=None,
        )
        self.assertNotIn("y=480", filt)
        self.assertNotIn("mini home tour", filt)
        self.assertNotIn("living room", filt)

    def test_animated_product_drawtext_filter(self):
        slides = [(f"Product {i}", "Light") for i in range(1, 12)]
        filt, out_label, _total = MODULE.build_house_tour_filter(
            slides,
            with_outro=False,
            pacing="reference",
            cut_style="snap",
            overlay_style="reference",
        )
        self.assertIn("product 1", filt)
        self.assertIn("product 11", filt)
        self.assertIn(f"fontsize={MODULE.PRODUCT_NAME_FONT_SIZE}", filt)
        self.assertIn("alpha=", filt)
        self.assertIn("1600 +", filt)
        self.assertTrue(out_label.endswith("prod"))

    def test_format_item_display_name(self):
        cases = [
            ("Kansa", "Table Lamp", "kansa table lamp"),
            ("Indus", "Modern LED Wall Light", "indus wall light"),
            ("Adela", "Modern Pendant Light", "adela pendant light"),
            ("Aria Pendant Light", "Pendant Light", "aria pendant light"),
            ("Kenia", "", "kenia chandelier"),
        ]
        for title, ptype, expected in cases:
            with self.subTest(title=title, ptype=ptype):
                res = MODULE.format_item_display_name(title, ptype, fallback_label="Chandelier")
                self.assertEqual(res, expected)

    def test_custom_room_titles_render_in_filter(self):
        titles = [f"room {i}" for i in range(1, 12)]
        filt, _out_label, _total = MODULE.build_house_tour_filter(
            slide_texts=None,
            room_titles=titles,
            with_outro=False,
            pacing="reference",
            cut_style="snap",
            overlay_style="reference",
        )
        for t in titles:
            self.assertIn(t, filt)

    def test_reference_assemble_runs_ffmpeg(self):
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            clips = []
            for s in MODULE.SLOTS:
                p = workdir / f"clip{s}.mp4"
                p.write_bytes(b"fakevideo")
                clips.append(p)
            captured = {}

            def fake_run(cmd, **kwargs):
                captured["cmd"] = cmd
                Path(cmd[-1]).write_bytes(b"finalvideo")
                return SimpleNamespace(returncode=0, stderr="")

            with patch.object(MODULE.subprocess, "run", side_effect=fake_run):
                out = MODULE.phase8_assemble(
                    clips,
                    workdir,
                    slide_texts=self.SLIDES,
                    outro=None,
                    audio=None,
                    pacing="reference",
                    cut_style="snap",
                    overlay_style="reference",
                    with_outro=False,
                )
            self.assertTrue(out.is_file())
            cmd = captured["cmd"]
            self.assertIn("-filter_complex", cmd)
            filt = cmd[cmd.index("-filter_complex") + 1]
            self.assertIn("concat=n=11", filt)
            self.assertIn("Poppins-Medium", filt)
            self.assertIn("-an", cmd)

    def test_reference_pacing_twenty_four_point_five_seconds_with_outro(self):
        titles = ["mini home tour", "living room"] + [""] * 9
        filt, out_label, total = MODULE.build_house_tour_filter(
            self.SLIDES,
            with_outro=True,
            pacing="reference",
            cut_style="snap",
            overlay_style="reference",
            room_titles=titles,
        )
        self.assertAlmostEqual(total, 24.5, places=2)
        self.assertIn("concat=n=11:v=1:a=0", filt)
        self.assertIn("xfade=transition=fade:duration=0.50:offset=21.50", filt)
        self.assertIn("settb=1/30", filt)

    def test_reference_assemble_includes_outro_by_default_when_outro_file_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            clips = []
            for s in MODULE.SLOTS:
                p = workdir / f"clip{s}.mp4"
                p.write_bytes(b"fakevideo")
                clips.append(p)
            outro = workdir / "outro.jpg"
            outro.write_bytes(b"fakeoutro")
            captured = {}

            def fake_run(cmd, **kwargs):
                captured["cmd"] = cmd
                Path(cmd[-1]).write_bytes(b"finalvideo")
                return SimpleNamespace(returncode=0, stderr="")

            with patch.object(MODULE.subprocess, "run", side_effect=fake_run):
                out = MODULE.phase8_assemble(
                    clips,
                    workdir,
                    slide_texts=self.SLIDES,
                    outro=outro,
                    audio=None,
                    pacing="reference",
                    cut_style="snap",
                    overlay_style="reference",
                    with_outro=None,  # Default: should auto-include because outro exists
                )
            self.assertTrue(out.is_file())
            cmd = captured["cmd"]
            self.assertIn("-loop", cmd)
            self.assertIn("-t", cmd)
            self.assertIn(str(outro), cmd)
            filt = cmd[cmd.index("-filter_complex") + 1]
            self.assertIn("xfade=transition=fade", filt)

    def test_legacy_relaxed_filter_has_xfades_plus_outro(self):
        filt, out_label, total = MODULE.build_house_tour_filter(
            self.SLIDES,
            with_outro=True,
            pacing="relaxed",
            cut_style="dissolve",
            overlay_style="tag",
        )
        # 11 clips -> 10 clip joins + 1 outro join.
        self.assertEqual(filt.count("xfade"), 11)
        # 2 lines per slide: Bold 18 item name + Regular 18 product type.
        self.assertEqual(filt.count("drawtext"), 8)
        self.assertNotIn("borderw", filt)
        self.assertNotIn("alpha=", filt)
        self.assertIn("fontsize=18", filt)
        self.assertIn("Poppins-Bold", filt)
        self.assertIn("Poppins-Regular", filt)
        self.assertIn("offset=2.0", filt)
        self.assertIn("offset=22.0", filt)
        self.assertAlmostEqual(total, 24.5)
        self.assertTrue(out_label.startswith("vt"))

    def test_legacy_title_windows_never_overlap(self):
        import re

        filt, _out_label, _total = MODULE.build_house_tour_filter(
            self.SLIDES,
            with_outro=True,
            pacing="relaxed",
            cut_style="dissolve",
            overlay_style="tag",
        )
        windows = [
            (float(a), float(b))
            for a, b in re.findall(r"between\(t,(\d+\.\d+),(\d+\.\d+)\)", filt)
        ]
        self.assertEqual(len(windows), 8)
        for i in range(0, len(windows), 2):
            self.assertEqual(windows[i], windows[i + 1])
            if i + 2 < len(windows):
                self.assertLessEqual(windows[i][1], windows[i + 2][0])

    def test_legacy_type_line_sits_below_title_line(self):
        import re

        filt, _out_label, _total = MODULE.build_house_tour_filter(
            [("Solo Name", "Solo Type"), ("", ""), ("", ""), ("", "")],
            with_outro=False,
            pacing="relaxed",
            cut_style="dissolve",
            overlay_style="tag",
        )
        self.assertEqual(filt.count("drawtext"), 2)
        ys = [int(y) for y in re.findall(r":y=(\d+):", filt)]
        self.assertEqual(len(ys), 2)
        self.assertGreater(ys[1], ys[0])

    def test_tag_position_stays_inside_canvas(self):
        x, y_title, y_type = MODULE.tag_reel_position(
            "Alejandro Deux", "Modern Chandelier"
        )
        self.assertGreaterEqual(x, 0)
        self.assertGreaterEqual(y_title, 0)
        self.assertGreater(y_type, y_title)
        self.assertLess(x, MODULE.VIDEO_WIDTH)
        self.assertLess(y_type, MODULE.VIDEO_HEIGHT)

    def test_legacy_filter_without_outro_is_twenty_three_seconds(self):
        filt, _out_label, total = MODULE.build_house_tour_filter(
            self.SLIDES,
            with_outro=False,
            pacing="relaxed",
            cut_style="dissolve",
            overlay_style="tag",
        )
        self.assertEqual(filt.count("xfade"), 10)
        self.assertAlmostEqual(total, 23.0)


if __name__ == "__main__":
    unittest.main()
