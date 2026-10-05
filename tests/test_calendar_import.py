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


if __name__ == "__main__":
    unittest.main()
