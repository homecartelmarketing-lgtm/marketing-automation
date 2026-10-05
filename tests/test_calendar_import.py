"""Tests for the Content Calendar month-sheet grid parser (Task 1)."""
import unittest


class TestParseMonthSlots(unittest.TestCase):
    def test_parse_month_slots_todo_only(self):
        from content_automation.calendar_import import parse_month_slots
        slots = parse_month_slots("tests/fixtures/mini_calendar.xlsx", "October")
        todos = [s for s in slots if s["status"] == "TO DO"]
        self.assertEqual(len(todos), 3)
        self.assertEqual(todos[0]["format"], "Feeds")
        self.assertTrue(todos[0]["date"].startswith("2026-10-"))


class TestResolveJob(unittest.TestCase):
    def test_known_ideas_resolve(self):
        from content_automation.calendar_import import resolve_job
        job = resolve_job("Feeds", "Product Showcase")
        self.assertEqual(job["pipeline_type"], "product-showcase-feed")
        self.assertTrue(job["run_endpoint"].startswith("/api/"))
        self.assertIsNone(resolve_job("Feeds", "Caption"))

    def test_skip_ideas_return_none(self):
        from content_automation.calendar_import import resolve_job
        self.assertIsNone(resolve_job("Reels", "House Tour"))
        self.assertIsNone(resolve_job("Reels", "NONE"))
        self.assertIsNone(resolve_job("Feeds", "No Such Idea"))

    def test_pipeline_types_match_frontend_union(self):
        from content_automation.calendar_import import resolve_job
        self.assertEqual(resolve_job("Stories", "CTA")["pipeline_type"], "cta")
        self.assertEqual(resolve_job("Stories", "Tips & Educational")["pipeline_type"], "tips-edu")
        self.assertEqual(resolve_job("Reels", "Sketch to Real")["pipeline_type"], "sketch-to-draw-reel")


class TestCollapseDayNight(unittest.TestCase):
    def test_collapse_day_night(self):
        from content_automation.calendar_import import collapse_day_night, resolve_job
        slots = [
            {"date": "2026-10-05", "format": "Stories", "idea": "Day (D&N)",
             "time": "", "status": "TO DO", "cell": "A1"},
            {"date": "2026-10-05", "format": "Stories", "idea": "Night (D&N)",
             "time": "", "status": "TO DO", "cell": "A2"},
        ]
        collapsed = collapse_day_night(slots)
        self.assertEqual(len(collapsed), 1)
        job = resolve_job(collapsed[0]["format"], collapsed[0]["idea"])
        self.assertIsNotNone(job)
        self.assertEqual(job["pipeline_type"], "day-night-story")

    def test_mixed_status_pairs_stay_uncollapsed(self):
        from content_automation.calendar_import import collapse_day_night
        day_todo_night_posted = [
            {"date": "2026-10-05", "format": "Stories", "idea": "Day (D&N)",
             "time": "", "status": "TO DO", "cell": "A1"},
            {"date": "2026-10-05", "format": "Stories", "idea": "Night (D&N)",
             "time": "", "status": "Posted", "cell": "A2"},
        ]
        out = collapse_day_night(day_todo_night_posted)
        self.assertEqual(len(out), 2)
        self.assertEqual(
            sorted(s["idea"] for s in out), ["Day (D&N)", "Night (D&N)"])
        day_posted_night_todo = [
            {"date": "2026-10-05", "format": "Stories", "idea": "Day (D&N)",
             "time": "", "status": "Posted", "cell": "A1"},
            {"date": "2026-10-05", "format": "Stories", "idea": "Night (D&N)",
             "time": "", "status": "TO DO", "cell": "A2"},
        ]
        out = collapse_day_night(day_posted_night_todo)
        self.assertEqual(len(out), 2)
        self.assertEqual(
            sorted(s["idea"] for s in out), ["Day (D&N)", "Night (D&N)"])


class TestPickFixture(unittest.TestCase):
    def test_round_robin_cycles(self):
        from content_automation.calendar_import import pick_fixture
        state = {}
        got = [pick_fixture("moodboard-story", state, ["chandelier", "pendant", "floor-lamp"]) for _ in range(4)]
        self.assertEqual(got, ["chandelier", "pendant", "floor-lamp", "chandelier"])

    def test_round_robin_state_and_independence(self):
        from content_automation.calendar_import import pick_fixture
        state = {}
        fixtures = ["chandelier", "pendant", "floor-lamp"]
        for _ in range(4):
            pick_fixture("moodboard-story", state, fixtures)
        self.assertEqual(state, {"moodboard-story": 4})
        state2 = {}
        self.assertEqual(pick_fixture("moodboard-story", state2, fixtures), "chandelier")
        self.assertEqual(pick_fixture("cta", state2, fixtures), "chandelier")
        self.assertEqual(pick_fixture("moodboard-story", state2, fixtures), "pendant")
        self.assertEqual(pick_fixture("cta", state2, fixtures), "pendant")


if __name__ == "__main__":
    unittest.main()
