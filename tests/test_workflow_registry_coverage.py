"""Registry coverage: every WORKFLOWS key must resolve in WORKFLOW_CLASSES.

Regression test for the Floor Lamp Moodboard Story Studio crash:
`run_moodboard_story.py --target floor_lamps` forwarded
`--assignment floor_lamps_moodboard_story` to run_content_automation,
which raised `KeyError: 'floor_lamps_moodboard_story'` in
provider_requirements() because registry.py had no entry.
Pure dict assertions, no network calls.
"""

from __future__ import annotations

import unittest


class WorkflowRegistryCoverageTests(unittest.TestCase):
    def test_every_workflow_definition_resolves(self):
        from content_automation.config import WORKFLOWS
        from content_automation.workflows.registry import WORKFLOW_CLASSES

        missing = sorted(set(WORKFLOWS.keys()) - set(WORKFLOW_CLASSES.keys()))
        self.assertEqual(
            missing, [], f"WORKFLOWS keys missing from WORKFLOW_CLASSES: {missing}"
        )

    def test_floor_lamp_moodboard_story_creates_workflow(self):
        import tempfile
        from types import SimpleNamespace
        from pathlib import Path
        from content_automation.workflows.moodboard_story import MoodboardStoryWorkflow
        from content_automation.workflows.registry import create_workflow

        ctx = SimpleNamespace(workdir=Path(tempfile.gettempdir()))
        workflow = create_workflow("floor_lamps_moodboard_story", ctx)
        self.assertIsInstance(workflow, MoodboardStoryWorkflow)


if __name__ == "__main__":
    unittest.main()
