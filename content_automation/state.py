from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Iterable

from .airtable_client import AirtableClient
from .errors import AutomationError, MetadataError
from .models import ProductRecord, Reservation, WorkflowDefinition


ACTIVE_STATUSES = {"Reserved", "Running", "Failed"}
CONSUMED_STATUSES = {"Reserved", "Running", "Failed", "Completed"}


def parse_state(value: object) -> dict:
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    try:
        result = json.loads(str(value))
    except json.JSONDecodeError:
        return {}
    return result if isinstance(result, dict) else {}


def dump_state(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def missing_metadata(product: ProductRecord, fields: Iterable[str]) -> list[str]:
    return [name for name in fields if not str(getattr(product, name, "") or "").strip()]


@dataclass
class ReservationPlan:
    reservations: list[Reservation]
    skipped_metadata: list[tuple[str, list[str]]]
    completed_count: int = 0


class StateManager:
    def __init__(self, airtable: AirtableClient):
        self.airtable = airtable

    def select(
        self,
        workflow: WorkflowDefinition,
        *,
        batch_size: int,
        execute: bool,
        record_ids: list[str] | None = None,
        force: bool = False,
        run_id: str | None = None,
        exclude_ids: set[str] | None = None,
    ) -> ReservationPlan:
        run_id = run_id or uuid.uuid4().hex
        exclude_ids = exclude_ids or set()
        products = self.airtable.list_products()
        by_id = {product.record_id: product for product in products}
        if record_ids:
            unknown = [record_id for record_id in record_ids if record_id not in by_id]
            if unknown:
                raise AutomationError(
                    f"Unknown or product-less record IDs in {workflow.table_code}: "
                    + ", ".join(unknown)
                )

        def needs_output_recovery(product: ProductRecord) -> bool:
            checkpoint = workflow.recovery_attachment_field
            expected = workflow.recovery_attachment_count
            if not checkpoint or expected < 1:
                return False
            fields = product.fields
            assignment = str(fields.get("Content Assignment") or "")

            checkpoint_candidates = [
                checkpoint,
                "Story Collection Categ Blended",
                "Collection Category Blended",
                "Collection Category Blended Image1",
                "CTA Blended Image",
                "CTA Blended",
            ]
            checkpoint_count = max(len(fields.get(cp) or []) for cp in checkpoint_candidates)
            if checkpoint_count < expected:
                return False
            if not all(
                fields.get(name)
                for name in workflow.recovery_input_fields
            ):
                return False

            from .workflows.registry import WORKFLOW_CLASSES
            workflow_cls = WORKFLOW_CLASSES.get(workflow.key)
            if workflow_cls:
                expected_final = len(getattr(workflow_cls, "final_filenames", ()))
                final_candidates = [
                    workflow.final_field,
                    "Collection Category Converted",
                    "STORY - Collection Category (1)",
                    "CTA Converted Image",
                    "CTA Converted Blended",
                ]
                final_count = max(len(fields.get(f) or []) for f in final_candidates)
                if final_count < expected_final:
                    return (
                        str(fields.get("Status") or "") in {"Complete", "Processing", "Standby"}
                        and assignment in {"", workflow.key}
                    )

            final_candidates = [
                workflow.final_field,
                "Collection Category Converted",
                "STORY - Collection Category (1)",
                "CTA Converted Image",
                "CTA Converted Blended",
            ]
            final_count = max(len(fields.get(f) or []) for f in final_candidates)
            return (
                str(fields.get("Status") or "") == "Complete"
                and final_count < 1
                and assignment in {"", workflow.key}
            )

        completed = [
            product
            for product in products
            if product.fields.get("Content Assignment") == workflow.key
            and str(product.fields.get("Content Role") or "") == "anchor"
            and str(product.fields.get("Content Status") or "") == "Completed"
            and not needs_output_recovery(product)
        ]
        completed.sort(key=lambda product: product.record_id)

        resumed = [
            product
            for product in products
            if product.fields.get("Content Assignment") == workflow.key
            and str(product.fields.get("Content Role") or "") == "anchor"
            and str(product.fields.get("Content Status") or "") in ACTIVE_STATUSES
        ]
        resumed.sort(key=lambda product: product.record_id)
        if record_ids:
            resumed = [product for product in resumed if product.record_id in record_ids]
        if force:
            # --force means a fresh run for every explicitly selected anchor,
            # including failed/reserved anchors that would otherwise resume.
            resumed = []

        target_count = (
            batch_size
            if record_ids
            else max(0, batch_size - len(completed))
        )
        if target_count == 0:
            return ReservationPlan([], [], len(completed))

        reservations: list[Reservation] = []
        used_ids: set[str] = set()

        if force:
            for anchor in sorted(
                (
                    product
                    for product in products
                    if product.record_id in set(record_ids or [])
                    and (
                        product.fields.get("Content Assignment")
                        or product.fields.get("Content Status")
                    )
                ),
                key=lambda product: product.record_id,
            ):
                assignment = str(
                    anchor.fields.get("Content Assignment") or ""
                )
                role = str(anchor.fields.get("Content Role") or "")
                if assignment != workflow.key or role != "anchor":
                    raise AutomationError(
                        f"Cannot force {anchor.record_id}: it is consumed by "
                        f"{assignment or 'another assignment'} as "
                        f"{role or 'an unknown role'}"
                    )
                state = parse_state(anchor.fields.get("Content State"))
                partner_ids = [
                    str(item) for item in state.get("partner_ids", [])
                ]
                partners = [
                    by_id[item] for item in partner_ids if item in by_id
                ]
                if len(partners) != workflow.partner_count:
                    raise AutomationError(
                        f"Incomplete saved reservation for anchor "
                        f"{anchor.record_id}: expected {workflow.partner_count} "
                        f"partners, found {len(partners)}"
                    )
                invalid_partners = [
                    partner.record_id
                    for partner in partners
                    if (
                        str(
                            partner.fields.get("Content Assignment") or ""
                        )
                        != workflow.key
                        or str(partner.fields.get("Content Role") or "")
                        != "partner"
                    )
                ]
                if invalid_partners:
                    raise AutomationError(
                        f"Cannot force {anchor.record_id}: saved partners no "
                        f"longer belong to this reservation: "
                        + ", ".join(invalid_partners)
                    )
                reservation = Reservation(
                    workflow=workflow,
                    run_id=run_id,
                    anchor=anchor,
                    partners=partners,
                )
                reservations.append(reservation)
                used_ids.add(anchor.record_id)
                used_ids.update(
                    partner.record_id for partner in partners
                )
                if execute:
                    self.reserve(reservation)
                if len(reservations) >= target_count:
                    return ReservationPlan(
                        reservations,
                        [],
                        len(completed),
                    )

        recovery_candidates = sorted(
            (
                product
                for product in products
                if needs_output_recovery(product)
                and (
                    not record_ids
                    or product.record_id in set(record_ids)
                )
                and product.record_id not in used_ids
                and product.record_id not in exclude_ids
            ),
            key=lambda product: product.record_id,
        )
        for anchor in recovery_candidates:
            reservation = Reservation(
                workflow=workflow,
                run_id=run_id,
                anchor=anchor,
                partners=[],
            )
            reservations.append(reservation)
            used_ids.add(anchor.record_id)
            if execute:
                self.reserve(reservation)
            if len(reservations) >= target_count:
                return ReservationPlan(
                    reservations,
                    [],
                    len(completed),
                )

        for anchor in resumed:
            state = parse_state(anchor.fields.get("Content State"))
            partner_ids = [str(item) for item in state.get("partner_ids", [])]
            partners = [by_id[item] for item in partner_ids if item in by_id]
            if len(partners) != workflow.partner_count:
                raise AutomationError(
                    f"Incomplete saved reservation for anchor {anchor.record_id}: "
                    f"expected {workflow.partner_count} partners, found {len(partners)}"
                )
            reservations.append(
                Reservation(
                    workflow=workflow,
                    run_id=str(anchor.fields.get("Content Run ID") or run_id),
                    anchor=anchor,
                    partners=partners,
                )
            )
            used_ids.add(anchor.record_id)
            used_ids.update(partner.record_id for partner in partners)
            if len(reservations) >= target_count:
                return ReservationPlan(reservations, [], len(completed))

        explicit = set(record_ids or [])

        def is_available(
            product: ProductRecord,
            *,
            allow_forced_anchor: bool = False,
        ) -> bool:
            if product.record_id in used_ids or product.record_id in exclude_ids:
                return False
            status = str(product.fields.get("Content Status") or "")
            assignment = str(product.fields.get("Content Assignment") or "")
            if allow_forced_anchor and force and product.record_id in explicit:
                return True
            if workflow.select_status:
                # Airtable's own Status column is the queue for these workflows:
                # a record leaves the pool the moment it turns Processing, so a
                # second run cannot pick up work that is already under way.
                if (
                    str(product.fields.get("Status") or "")
                    != workflow.select_status
                ):
                    return False
            if not all(
                product.fields.get(name)
                for name in workflow.required_input_fields
            ):
                return False
            return not status and not assignment

        skipped: list[tuple[str, list[str]]] = []

        if explicit:
            anchor_candidates = sorted(
                (
                    product
                    for product in products
                    if product.record_id in explicit
                    and is_available(product, allow_forced_anchor=True)
                ),
                key=lambda product: product.record_id,
            )
            # Explicit record IDs identify anchors. Partner workflows still draw
            # their partners from the normal unconsumed table pool.
            partner_candidates = sorted(
                (
                    product
                    for product in products
                    if product.record_id not in explicit and is_available(product)
                ),
                key=lambda product: product.record_id,
            )
        else:
            anchor_candidates = sorted(
                (product for product in products if is_available(product)),
                key=lambda product: product.record_id,
            )
            partner_candidates = anchor_candidates

        while len(reservations) < target_count and anchor_candidates:
            anchor = anchor_candidates.pop(0)
            missing = missing_metadata(anchor, workflow.metadata_fields)
            if missing:
                skipped.append((anchor.record_id, missing))
                continue

            if not explicit:
                partner_candidates = anchor_candidates
            partners: list[ProductRecord] = []
            while (
                len(partners) < workflow.partner_count
                and partner_candidates
            ):
                candidate = partner_candidates.pop(0)
                partner_missing = missing_metadata(candidate, workflow.metadata_fields)
                if partner_missing:
                    skipped.append((candidate.record_id, partner_missing))
                    continue
                partners.append(candidate)
            if len(partners) < workflow.partner_count:
                break
            consumed_here = {
                anchor.record_id,
                *(partner.record_id for partner in partners),
            }
            if explicit:
                anchor_candidates = [
                    candidate
                    for candidate in anchor_candidates
                    if candidate.record_id not in consumed_here
                ]
            reservation = Reservation(
                workflow=workflow,
                run_id=run_id,
                anchor=anchor,
                partners=partners,
            )
            reservations.append(reservation)
            used_ids.update(consumed_here)
            if execute:
                self.reserve(reservation)

        return ReservationPlan(reservations, skipped, len(completed))

    def reserve(self, reservation: Reservation) -> None:
        workflow = reservation.workflow
        partner_ids = [partner.record_id for partner in reservation.partners]
        anchor_state = {
            "schema": 1,
            "workflow": workflow.key,
            "partner_ids": partner_ids,
            "outputs": {},
        }
        common = {
            "Content Assignment": workflow.key,
            "Content Status": "Reserved",
            "Content Run ID": reservation.run_id,
            "Content Error": "",
        }
        updates: list[tuple[str, dict]] = [
            (
                reservation.anchor.record_id,
                {
                    **common,
                    "Content Role": "anchor",
                    "Content State": dump_state(anchor_state),
                },
            )
        ]
        for partner in reservation.partners:
            updates.append(
                (
                    partner.record_id,
                {
                    **common,
                    "Content Role": "partner",
                    "Content State": dump_state(
                        {
                            "schema": 1,
                            "workflow": workflow.key,
                            "anchor_id": reservation.anchor.record_id,
                        }
                    ),
                },
                )
            )
        self._batch_update(updates)

    def mark_running(self, reservation: Reservation) -> None:
        self._update_group(reservation, "Running", "", extra={"Status": "Processing"})

    def mark_complete(self, reservation: Reservation, filenames: list[str]) -> None:
        state = parse_state(reservation.anchor.fields.get("Content State"))
        state.update(
            {
                "schema": 1,
                "workflow": reservation.workflow.key,
                "partner_ids": [item.record_id for item in reservation.partners],
                "final_filenames": filenames,
            }
        )
        updates: list[tuple[str, dict]] = [
            (
                reservation.anchor.record_id,
                {
                    "Content Status": "Completed",
                    "Content Error": "",
                    "Content State": dump_state(state),
                    "Status": "Complete",
                },
            )
        ]
        for partner in reservation.partners:
            updates.append(
                (
                    partner.record_id,
                    {
                        "Content Status": "Completed", 
                        "Content Error": "",
                        "Status": "Complete",
                    },
                )
            )
        self._batch_update(updates)

    def mark_failed(self, reservation: Reservation, error: Exception) -> None:
        # Status-gated workflows must hand the record back to the queue,
        # otherwise a failure leaves it stranded on "Processing" forever.
        select_status = reservation.workflow.select_status
        self._update_group(
            reservation,
            "Failed",
            str(error)[:10000],
            extra={"Status": select_status} if select_status else None,
        )

    def _update_group(
        self,
        reservation: Reservation,
        status: str,
        error: str,
        extra: dict | None = None,
    ) -> None:
        self._batch_update(
            [
                (
                    product.record_id,
                    {"Content Status": status, "Content Error": error, **(extra or {})},
                )
                for product in [reservation.anchor, *reservation.partners]
            ]
        )

    def _batch_update(self, updates: list[tuple[str, dict]]) -> None:
        schema = set()
        if hasattr(self.airtable, "schema"):
            try:
                schema = set(self.airtable.schema().keys())
            except Exception:
                pass
        filtered_updates = []
        for record_id, fields in updates:
            clean_fields = {
                k: v for k, v in fields.items()
                if not schema or k in schema
            }
            if clean_fields:
                filtered_updates.append((record_id, clean_fields))
        if not filtered_updates:
            return
        if hasattr(self.airtable, "update_records"):
            try:
                self.airtable.update_records(filtered_updates)
                return
            except Exception as error:
                if "INVALID_MULTIPLE_CHOICE_OPTIONS" in str(error):
                    fallback_updates = [
                        (record_id, {k: v for k, v in fields.items() if k != "Status"})
                        for record_id, fields in filtered_updates
                    ]
                    self.airtable.update_records(fallback_updates)
                    return
                raise
        for record_id, fields in filtered_updates:
            try:
                self.airtable.update_record(record_id, fields)
            except Exception as error:
                if "INVALID_MULTIPLE_CHOICE_OPTIONS" in str(error) and "Status" in fields:
                    clean = {k: v for k, v in fields.items() if k != "Status"}
                    self.airtable.update_record(record_id, clean)
                else:
                    raise
