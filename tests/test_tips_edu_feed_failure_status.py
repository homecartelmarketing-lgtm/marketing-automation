"""A crashed Tips & Edu Feed phase must not leave the Airtable row on 'Processing'."""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import run_tips_and_edu_feed as feed


def _runner() -> feed.TipsAndEduFeedRunner:
    """Runner without network clients (the constructor loads settings and builds API clients)."""
    runner = feed.TipsAndEduFeedRunner.__new__(feed.TipsAndEduFeedRunner)
    runner.force_layouts = False
    runner.force_tips = False
    runner.logger = mock.Mock()
    runner.airtable = mock.Mock()
    return runner


class RunSinglePhaseCrashTests(unittest.TestCase):
    def test_crash_sets_for_manual_and_reraises(self):
        runner = _runner()
        with mock.patch.object(runner, "phase_2", side_effect=ValueError("krea exploded")), \
                mock.patch.object(runner, "_update_status") as update_status, \
                mock.patch.object(feed, "append_error_log"):
            with self.assertRaisesRegex(ValueError, "krea exploded"):
                runner._run_single_phase(2, "recTEST", execute=True)
        update_status.assert_called_once_with("recTEST", feed.STATUS_FOR_MANUAL)

    def test_failed_status_write_does_not_hide_original_error(self):
        runner = _runner()
        with mock.patch.object(runner, "phase_3", side_effect=ValueError("claude exploded")), \
                mock.patch.object(runner, "_update_status", side_effect=RuntimeError("airtable down")), \
                mock.patch.object(feed, "append_error_log"):
            with self.assertRaisesRegex(ValueError, "claude exploded"):
                runner._run_single_phase(3, "recTEST", execute=True)

    def test_dry_run_never_writes_a_status(self):
        runner = _runner()
        with mock.patch.object(runner, "phase_4", side_effect=ValueError("boom")), \
                mock.patch.object(runner, "_update_status") as update_status, \
                mock.patch.object(feed, "append_error_log"):
            with self.assertRaises(ValueError):
                runner._run_single_phase(4, "recTEST", execute=False)
        update_status.assert_not_called()

    def test_successful_phase_keeps_its_own_status(self):
        runner = _runner()
        with mock.patch.object(runner, "phase_5", return_value=True), \
                mock.patch.object(runner, "_update_status") as update_status:
            runner._run_single_phase(5, "recTEST", execute=True)
        update_status.assert_not_called()


class Phase6DownloadFailureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_download_failure_fails_the_slot_not_the_phase(self):
        runner = _runner()
        attachments = [
            {"url": f"https://example.invalid/tagged_{n}.jpg", "filename": f"tips_edu_feed_tagged_{n}_recTEST.jpg"}
            for n in (1, 2, 3)
        ]
        runner.airtable.known_field_names.return_value = {"Tips 1", "Tips 2", "Tips 3"}
        runner.airtable.get_record.return_value = {
            "fields": {
                feed.TAGGED_BLENDED_FIELD: attachments,
                "Tips 1": "tip one",
                "Tips 2": "tip two",
                "Tips 3": "tip three",
            }
        }
        with mock.patch.object(runner, "generate_tips_texts"), \
                mock.patch.object(runner, "_artifact_path", side_effect=lambda rec, name: self.tmp / name), \
                mock.patch.object(runner, "_download", side_effect=OSError("attachment url expired")), \
                mock.patch.object(runner, "_update_status") as update_status, \
                mock.patch.object(feed, "append_error_log"):
            result = runner.phase_6("recTEST", execute=True)

        self.assertFalse(result)
        runner.airtable.upload_attachment.assert_not_called()
        statuses = [call.args[1] for call in update_status.call_args_list]
        self.assertEqual(statuses[-1], feed.STATUS_FOR_MANUAL)
        self.assertNotIn(feed.STATUS_COMPLETE, statuses)


class PhaseSelectionTests(unittest.TestCase):
    """Phase 5 = YOLO tagging, Phase 6 = Pillow layout. Phase 6 must be selectable and chosen at the right time."""

    def _record(self, *, tagged: int = 0, finals: int = 0, status: str = "Already attached a room Interior") -> dict:
        att = lambda n: [{"url": f"https://example.invalid/{i}.jpg", "filename": f"f_{i + 1}_.jpg"} for i in range(n)]
        fields: dict = {
            feed.STATUS_FIELD: status,
            "Interior2": att(1),
            "Interior3": att(1),
            feed.BLENDED_FIELD: att(3),
            feed.THUMBNAIL_WITH_TEXT_FIELD: att(1),
            feed.TAGGED_BLENDED_FIELD: att(tagged),
            feed.FINAL_FEED_FIELD: att(finals),
        }
        for slot in feed.SLOTS:
            fields[slot.furniture_field] = att(1)
            fields[slot.prompt_field] = "a prompt"
            fields[slot.interior_field] = att(1)
        fields[feed.THUMBNAIL_FIELD] = att(1)
        return {"id": "recTEST", "fields": fields}

    def _phase(self, record: dict):
        runner = _runner()
        runner.thumbnail_field = feed.THUMBNAIL_FIELD
        return runner._phase_for_record(record)

    def test_phase_6_is_an_accepted_cli_choice(self):
        args = feed.parse_args(["--phase", "6", "--record-id", "recTEST"])
        self.assertEqual(args.phase, "6")

    def test_untagged_row_goes_to_phase_5_first(self):
        self.assertEqual(self._phase(self._record(tagged=0, finals=0)), 5)

    def test_tagged_row_without_feed_slides_goes_to_phase_6(self):
        self.assertEqual(self._phase(self._record(tagged=4, finals=0)), 6)

    def test_finished_row_has_no_next_phase(self):
        self.assertIsNone(self._phase(self._record(tagged=4, finals=3)))


if __name__ == "__main__":
    unittest.main()
