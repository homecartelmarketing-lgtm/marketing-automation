from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TableConfig:
    code: str
    label: str
    table_id: str
    moodboard_env: str
    # Env var that overrides `table_id`. Kept so callers can re-read it live
    # rather than relying on the value captured when this module was imported.
    table_env: str = ""


@dataclass
class Attachment:
    id: str = ""
    filename: str = ""
    url: str = ""
    content_type: str = ""

    @classmethod
    def from_airtable(cls, value: dict[str, Any]) -> "Attachment":
        return cls(
            id=str(value.get("id") or ""),
            filename=str(value.get("filename") or ""),
            url=str(value.get("url") or ""),
            content_type=str(value.get("type") or ""),
        )


@dataclass
class ProductRecord:
    table: TableConfig
    record_id: str
    sku: str
    item_name: str
    product_type: str
    measurement: str
    furniture: Attachment
    fields: dict[str, Any] = field(default_factory=dict)

    @property
    def display_label(self) -> str:
        if self.product_type:
            return f"{self.item_name} | {self.product_type}"
        return self.item_name or self.sku or self.record_id


@dataclass(frozen=True)
class LocalImage:
    path: Path
    filename: str
    content_type: str = "image/jpeg"


@dataclass(frozen=True)
class AssetRequirement:
    relative_path: str
    kind: str = "image"
    aspect_ratio: str = ""


@dataclass(frozen=True)
class WorkflowDefinition:
    key: str
    phase: str
    table_code: str
    label: str
    final_field: str
    anchor_count: int = 10
    partner_count: int = 0
    metadata_fields: tuple[str, ...] = ()
    # When set, only records whose Airtable "Status" equals this value are
    # eligible. Blank keeps the historical behaviour of drawing from every
    # unconsumed record in the table.
    select_status: str = ""
    # Optional checkpoint-only recovery for a Complete row whose final
    # attachment is missing.
    recovery_attachment_field: str = ""
    recovery_attachment_count: int = 0
    # Fields that must contain values before a normal run can select a row.
    required_input_fields: tuple[str, ...] = ()
    # Inputs still required when checkpoint recovery skips the first stage.
    recovery_input_fields: tuple[str, ...] = ()


@dataclass
class Reservation:
    workflow: WorkflowDefinition
    run_id: str
    anchor: ProductRecord
    partners: list[ProductRecord] = field(default_factory=list)


@dataclass
class CallEstimate:
    krea: int = 0
    qwen: int = 0
    kie: int = 0
    fal: int = 0

    def __add__(self, other: "CallEstimate") -> "CallEstimate":
        return CallEstimate(
            self.krea + other.krea,
            self.qwen + other.qwen,
            self.kie + other.kie,
            self.fal + other.fal,
        )


@dataclass
class WorkflowResult:
    record_id: str
    workflow_key: str
    status: str
    filenames: list[str] = field(default_factory=list)
    error: str = ""
