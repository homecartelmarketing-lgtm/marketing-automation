"""Sketch to Real Reel fixture-removal regression tests (no network calls)."""

import unittest

import generate_sketch_to_real_reel_pipeline as pipe


class FixtureRemovalPhaseTests(unittest.TestCase):
    def test_removal_prompt_strips_lights_and_keeps_room(self):
        prompt = pipe.FIXTURE_REMOVAL_PROMPT.lower()
        for keyword in ("chandelier", "pendant", "sconce", "table lamp", "floor lamp"):
            self.assertIn(keyword, prompt)
        self.assertIn("keep the camera angle", prompt)
        self.assertIn("no text, no people", prompt)

    def test_removal_model_matches_room_build_up_engine(self):
        self.assertEqual(pipe.FIXTURE_REMOVAL_MODEL, "fal-ai/nano-banana-pro/edit")
        self.assertEqual(pipe.FIXTURE_REMOVAL_ASPECT_RATIO, "9:16")
        self.assertEqual(pipe.FIXTURE_REMOVAL_RESOLUTION, "1K")

    def test_clean_interior_fields_wired(self):
        self.assertEqual(pipe.FIELD_CLEAN_INTERIOR, "Clean Interior")
        self.assertEqual(pipe.FIELD_REMOVAL_PROMPT, "Removal Prompt")
        self.assertEqual(pipe.FIXTURE_REMOVAL_STATUS, "Fixture Removed")


if __name__ == "__main__":
    unittest.main()
