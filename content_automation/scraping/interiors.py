"""Generating Krea room-interior photos for scraped product rows."""

from __future__ import annotations

from typing import Any

from ..fields import (
    DEFAULT_ITEMS_PER_ROW,
    furniture_field,
    interior_field,
    sku_field,
)
from ..krea_client import KreaClient
from .airtable import ScrapeAirtableClient


INTERIOR_ASPECT_RATIO = "16:9"
INTERIOR_RESOLUTION = "1K"


def interior_prompt(subject: str) -> str:
    """The house style for a generated room shot without competing lamps."""
    return (
        "Modern Room Interior, curvilinear modern furniture, warm neutral palette, "
        "tactile boucle textures, organic minimalist interior, soft ambient natural daylight, "
        "sculptural decor, balanced negative space, clean uncluttered background, "
        "NO existing lamps, NO secondary floor lamps, NO table lamps, NO pre-existing light fixtures, "
        "empty floor space ready for product integration, photorealistic 8k"
    )


def interior_schema(slot_count: int = DEFAULT_ITEMS_PER_ROW) -> dict[str, str]:
    """Columns the interior pass reads from and writes to."""
    required: dict[str, str] = {}
    for slot in range(slot_count):
        required[furniture_field(slot)] = "multipleAttachments"
        required[sku_field(slot)] = "multilineText"
        required[interior_field(slot)] = "multipleAttachments"
    return required


def ensure_interior_fields(
    airtable: ScrapeAirtableClient,
    slot_count: int = DEFAULT_ITEMS_PER_ROW,
) -> None:
    """Ensure the matching product/interior columns exist for every slot."""
    airtable.ensure_fields(interior_schema(slot_count))


def interior_records(
    airtable: ScrapeAirtableClient,
    slot_count: int = DEFAULT_ITEMS_PER_ROW,
) -> list[dict[str, Any]]:
    """Records carrying the SKU, product photo and interior fields."""
    fields = [
        name
        for slot in range(slot_count)
        for name in (sku_field(slot), furniture_field(slot), interior_field(slot))
    ]
    return airtable.list_records(fields)


class InteriorRunner:
    """Fills every empty Interior slot with a freshly generated room shot."""

    def __init__(
        self,
        krea: KreaClient,
        airtable: ScrapeAirtableClient,
        moodboard_id: str = "",
        slot_count: int = DEFAULT_ITEMS_PER_ROW,
    ):
        self.krea = krea
        self.airtable = airtable
        self.moodboard_id = moodboard_id
        self.slot_count = slot_count

    def _generate_into_slot(self, record_id: str, slot: int, subject: str) -> bool:
        field_name = interior_field(slot)
        downloaded = None
        try:
            image_url = self.krea.generate(
                interior_prompt(subject),
                aspect_ratio=INTERIOR_ASPECT_RATIO,
                resolution=INTERIOR_RESOLUTION,
                moodboard_id=self.moodboard_id,
            )
            downloaded = self.krea.download_image(image_url)
            filename = f"Interior_{slot + 1}_{record_id}.jpg"
            self.airtable.upload_attachment(
                record_id, field_name, downloaded, filename
            )
            print(f"[OK] Attached Krea image to {field_name} on record {record_id}")
            return True
        except Exception as error:
            print(
                f"[ERROR] Failed generating/uploading interior photo for "
                f"{field_name}: {error}"
            )
            return False
        finally:
            if downloaded:
                downloaded.cleanup()

    def generate_for_records(self, limit_records: int | None = None) -> bool:
        ensure_interior_fields(self.airtable, self.slot_count)
        records = interior_records(self.airtable, self.slot_count)
        if not records:
            print("[OK] No records found in Airtable to populate interior photos.")
            return True
        if limit_records:
            records = records[:limit_records]

        succeeded = 0
        failed = 0
        for position, record in enumerate(records, start=1):
            record_id = record["id"]
            fields = record.get("fields", {})
            print(
                f"[INFO] Processing Airtable record {position}/{len(records)} "
                f"({record_id})..."
            )

            for slot in range(self.slot_count):
                subject = str(fields.get(sku_field(slot)) or "").strip()
                if not subject:
                    continue

                if fields.get(interior_field(slot)):
                    print(
                        f"[SKIP] {interior_field(slot)} already has an attachment "
                        f"in record {record_id}"
                    )
                    continue

                print(
                    f"[INFO] Generating photo {slot + 1}/{self.slot_count} "
                    f"({interior_field(slot)}) with Krea AI..."
                )
                if self._generate_into_slot(record_id, slot, subject):
                    succeeded += 1
                else:
                    failed += 1

        print(
            f"[INFO] Interior photo generation complete: {succeeded} succeeded, "
            f"{failed} failed."
        )
        return failed == 0
