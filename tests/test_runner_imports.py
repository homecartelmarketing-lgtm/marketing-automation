"""Import smoke test: every root runner / generator must at least import.

The Studio starts these scripts as subprocesses, so a broken import (for example a constant removed
from a generator but still imported by its runner) kills every run in the first second.
"""

from __future__ import annotations

import contextlib
import importlib
import io
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


def _module_names() -> list[str]:
    names = {p.stem for p in ROOT.glob("run_*.py")} | {p.stem for p in ROOT.glob("generate_*.py")}
    return sorted(names)


class RunnerImportTests(unittest.TestCase):
    def test_root_runners_and_generators_import(self):
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        failures: list[str] = []
        for name in _module_names():
            buffer = io.StringIO()
            try:
                with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
                    importlib.import_module(name)
            except BaseException as error:  # SystemExit from argparse-at-import also counts as broken
                failures.append(f"{name}: {type(error).__name__}: {str(error)[:160]}")
        self.assertEqual(failures, [], "modules that fail to import:\n" + "\n".join(failures))


if __name__ == "__main__":
    unittest.main()
