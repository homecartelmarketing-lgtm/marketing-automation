from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable

from PIL import Image

from .errors import AssetValidationError
from .models import AssetRequirement

MAX_PROMPT_LENGTH = 4900


class AssetCatalog:
    def __init__(
        self,
        workspace: Path,
        extra_roots: Iterable[Path] | None = None,
    ):
        self.workspace = workspace
        roots = [workspace, workspace / "JSON Prompts"]
        configured = os.getenv("CONTENT_AUTOMATION_ASSET_ROOT", "").strip()
        if configured:
            roots.append(Path(configured))
        if len(workspace.parents) >= 2:
            roots.append(workspace.parents[1] / "JSON Prompts")
        roots.extend(extra_roots or [])
        self.roots: list[Path] = []
        for root in roots:
            resolved = root.resolve()
            if resolved not in self.roots and resolved.is_dir():
                self.roots.append(resolved)

    def path(self, relative_path: str) -> Path:
        relative = Path(relative_path)
        for root in self.roots:
            direct = root / relative
            if direct.exists():
                return direct
        direct = self.workspace / relative
        if relative.parent != Path("."):
            return direct
        matches = [
            path
            for root in self.roots
            for path in root.rglob(relative_path)
            if ".automation_cache" not in path.parts
            and "output" not in path.parts
            and "build" not in path.parts
            and "dist" not in path.parts
        ]
        return matches[0] if matches else direct

    def read_prompt(self, relative_path: str, values: dict[str, str] | None = None) -> str:
        path = self.path(relative_path)
        if not path.is_file():
            raise AssetValidationError(f"Missing prompt asset: {path}")
        if path.suffix.lower() == ".json":
            try:
                data = json.loads(path.read_text(encoding="utf-8-sig"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise AssetValidationError(f"Invalid JSON prompt {path}: {error}") from error
            prompt = json.dumps(data, ensure_ascii=False)
        for key, value in (values or {}).items():
            prompt = prompt.replace(f"{{{{{key}}}}}", value)
        if len(prompt) > MAX_PROMPT_LENGTH:
            prompt = prompt[:MAX_PROMPT_LENGTH]
        return prompt


    def validate(self, requirements: Iterable[AssetRequirement]) -> list[str]:
        errors: list[str] = []
        for requirement in requirements:
            path = self.path(requirement.relative_path)
            if not path.is_file():
                errors.append(f"missing {requirement.kind}: {requirement.relative_path}")
                continue
            try:
                if requirement.kind == "json":
                    json.loads(path.read_text(encoding="utf-8-sig"))
                elif requirement.kind == "image":
                    with Image.open(path) as image:
                        width, height = image.size
                        image.verify()
                    if requirement.aspect_ratio:
                        left, right = (
                            int(value)
                            for value in requirement.aspect_ratio.split(":", 1)
                        )
                        actual_ratio = width / height
                        expected_ratio = left / right
                        if abs(actual_ratio - expected_ratio) / expected_ratio > 0.005:
                            errors.append(
                                f"invalid aspect ratio: {requirement.relative_path} "
                                f"(expected {requirement.aspect_ratio}, found "
                                f"{width}:{height})"
                            )
            except Exception as error:
                errors.append(f"invalid {requirement.kind}: {requirement.relative_path} ({error})")
        return errors

    def require(self, requirements: Iterable[AssetRequirement]) -> None:
        errors = self.validate(requirements)
        if errors:
            raise AssetValidationError("; ".join(errors))
