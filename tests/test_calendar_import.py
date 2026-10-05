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


if __name__ == "__main__":
    unittest.main()
