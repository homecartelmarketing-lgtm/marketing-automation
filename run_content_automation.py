from __future__ import annotations

import argparse
import os
import sys
import uuid
from collections import defaultdict

from content_automation.airtable_client import AirtableClient
from content_automation.assets import AssetCatalog
from content_automation.config import (
    TABLES,
    WORKFLOWS,
    load_settings,
    workflows_for_phase,
)
from content_automation.errors import AutomationError
from content_automation.fal_client import FalClient
from content_automation.kie_client import KieClient
from content_automation.krea_client import KreaClient
from content_automation.models import CallEstimate
from content_automation.qwen_client import QwenClient
from content_automation.state import StateManager
from content_automation.workflows import WORKFLOW_CLASSES, create_workflow
from content_automation.workflows.base import WorkflowContext


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Dry-run-first HomeCartel feed and story content automation."
    )
    parser.add_argument(
        "--phase",
        choices=("feeds", "stories", "reels"),
        required=True,
    )
    parser.add_argument(
        "--assignment",
        action="append",
        choices=sorted(WORKFLOWS),
        help="Run only this workflow key. Repeatable.",
    )
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--record-id", action="append", default=[])
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--category",
        "--table",
        dest="category",
        help="Target a specific table (e.g., floor_lamp, chandelier, pendant_lights, table_lamps, wall_lights, cluster_chandelier).",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Allow Airtable mutations and paid provider calls.",
    )
    return parser.parse_args(argv)


def attachment_fields_for(workflow_key: str) -> list[str]:
    definition = WORKFLOWS[workflow_key]
    workflow_class = WORKFLOW_CLASSES[workflow_key]
    return [definition.final_field, *workflow_class.attachment_fields]


def select_definitions(args) -> list:
    definitions = workflows_for_phase(args.phase)
    if args.assignment:
        requested = set(args.assignment)
        wrong_phase = [
            key for key in requested if WORKFLOWS[key].phase != args.phase
        ]
        if wrong_phase:
            raise AutomationError(
                f"Assignments do not belong to phase {args.phase}: "
                + ", ".join(sorted(wrong_phase))
            )
        definitions = [item for item in definitions if item.key in requested]

    if args.category:
        cat = args.category.lower().strip()
        matched_table = None
        # 1. Exact match
        for code in TABLES:
            if code == cat:
                matched_table = code
                break
        # 2. Prefer _this_or_that table if this_or_that_story is assigned
        if not matched_table and any("this_or_that" in a for a in (args.assignment or [])):
            suffix_candidate = f"{cat}_this_or_that"
            for code in TABLES:
                if code == suffix_candidate or (cat in code and "this_or_that" in code):
                    matched_table = code
                    break
        # 2b. Prefer _product_description_story table if product_description_story is assigned
        if not matched_table and any("product_description" in a for a in (args.assignment or [])):
            for suffix_candidate in (f"{cat}_product_description_story", f"{cat}s_product_description_story"):
                if suffix_candidate in TABLES:
                    matched_table = suffix_candidate
                    break
        # 3. Substring match
        if not matched_table:
            for code in TABLES:
                if code.startswith(cat) or cat in code:
                    matched_table = code
                    break

        if not matched_table:
            valid_tables = ", ".join(sorted(TABLES.keys()))
            raise AutomationError(
                f"Unknown table or category '{args.category}'. Valid tables: {valid_tables}"
            )

        from dataclasses import replace
        definitions = [replace(d, table_code=matched_table) for d in definitions]

    return definitions


def workflow_environment_errors(definition) -> list[str]:
    workflow_class = WORKFLOW_CLASSES[definition.key]
    errors: list[str] = []
    if workflow_class.estimate.krea:
        moodboard_env = TABLES[definition.table_code].moodboard_env
        if not os.getenv(moodboard_env, "").strip():
            errors.append(moodboard_env)
    if workflow_class.estimate.fal:
        if not os.getenv("FAL_KEY", "").strip() and not os.getenv("FAL_API_KEY", "").strip():
            errors.append("FAL_KEY")
    return errors


def missing_required_columns(definition, client) -> list[str]:
    """Airtable columns a workflow reads but cannot create for itself.

    ``Status`` is a single select and ``Prompt`` is authored by hand, so
    ``ensure_automation_schema`` deliberately leaves them alone. Without this
    check a missing column just means no record ever matches, which reads as
    "nothing to do" instead of a misconfigured table.
    """
    required = WORKFLOW_CLASSES[definition.key].required_columns
    if not required:
        return []
    try:
        existing = client.schema()
    except Exception as error:
        return [f"schema lookup failed: {error}"]
    missing = []
    for name in required:
        if name == "Interior" and ("Interior" in existing or "Interior1" in existing):
            continue
        if name == "Myth Layout" and ("Myth Layout" in existing or "Myth Emoticon " in existing or "Myth Emoticon" in existing):
            continue
        if name == "Fact Layout" and ("Fact Layout" in existing or "Fact Emoticon" in existing or "Fact Emoticon " in existing):
            continue
        if name == "Debunk Myth Thumbnail" and ("Debunk Myth Thumbnail" in existing or "Debunk Myth Thumbnail Generated Interior" in existing):
            continue
        if name == "Outro Thumbnail" and ("Outro Thumbnail" in existing or "Outro Photo Generated" in existing):
            continue
        if name == "Outro" and ("Outro" in existing or "Outro Layout" in existing):
            continue
        if name not in existing:
            missing.append(name)
    return missing


def provider_requirements(definitions) -> set[str]:
    providers = set()
    if any(WORKFLOW_CLASSES[item.key].estimate.kie for item in definitions):
        providers.add("kie")
    if any(WORKFLOW_CLASSES[item.key].estimate.fal for item in definitions):
        providers.add("fal")
    if any(WORKFLOW_CLASSES[item.key].estimate.krea for item in definitions):
        providers.add("krea")
    if any(WORKFLOW_CLASSES[item.key].estimate.qwen for item in definitions):
        providers.add("qwen")
    return providers


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.batch_size < 1:
        raise SystemExit("--batch-size must be at least 1")
    if args.force and (not args.record_id or not args.assignment or len(args.assignment) != 1):
        raise SystemExit("--force requires --record-id and exactly one --assignment")
    if args.record_id and (not args.assignment or len(args.assignment) != 1):
        raise SystemExit("--record-id requires exactly one --assignment")

    settings = load_settings()
    settings.require({"airtable"})
    definitions = select_definitions(args)
    required_providers = provider_requirements(definitions)
    assets = AssetCatalog(settings.workspace)
    run_id = uuid.uuid4().hex
    mode = "EXECUTE" if args.execute else "DRY RUN"
    print(f"[{mode}] phase={args.phase} run_id={run_id}")

    if args.execute:
        settings.require(required_providers)
    elif missing_providers := settings.missing(required_providers):
        print(
            "[EXECUTION BLOCKER] Live --execute still requires: "
            + ", ".join(missing_providers)
        )

    grouped_fields: dict[str, set[str]] = defaultdict(set)
    grouped_schema_fields: dict[str, dict[str, str]] = defaultdict(dict)
    for definition in definitions:
        grouped_fields[definition.table_code].update(
            attachment_fields_for(definition.key)
        )
        grouped_schema_fields[definition.table_code].update(
            WORKFLOW_CLASSES[definition.key].schema_fields
        )

    clients: dict[str, AirtableClient] = {}
    schema_blocked: set[str] = set()
    errors = 0
    total_planned = 0
    total_completed = 0
    total_failed = 0
    total_blocked = 0
    dry_run_consumed: dict[str, set[str]] = defaultdict(set)
    for table_code, fields in grouped_fields.items():
        client = AirtableClient(
            settings.airtable_token,
            settings.airtable_base_id,
            TABLES[table_code],
        )
        clients[table_code] = client
        try:
            missing = client.ensure_automation_schema(fields, execute=args.execute)
            missing.extend(
                client.ensure_fields(
                    grouped_schema_fields[table_code],
                    execute=args.execute,
                )
            )
            if missing:
                verb = "created" if args.execute else "would create"
                print(
                    f"[SCHEMA] {TABLES[table_code].label}: "
                    f"{verb} {', '.join(dict.fromkeys(missing))}"
                )
        except Exception as error:
            errors += 1
            schema_blocked.add(table_code)
            print(f"[ERROR] {TABLES[table_code].label} schema: {error}")

    krea = KreaClient(settings.krea_token, settings.krea_base_url)
    qwen = QwenClient(
        settings.qwen_api_key,
        settings.qwen_base_url,
        settings.qwen_model,
    )
    kie = KieClient(
        settings.kie_api_key,
        settings.kie_api_base,
        settings.kie_upload_base,
        settings.callback_url,
    )
    fal = FalClient(api_key=settings.fal_key)

    for definition in definitions:
        print(f"\n[{definition.key}] {definition.label} -> {definition.final_field}")
        workflow_class = WORKFLOW_CLASSES[definition.key]
        asset_errors = assets.validate(workflow_class.requirements)
        if asset_errors:
            errors += 1
            total_blocked += 1
            print("[BLOCKED] Required assets:")
            for error in asset_errors:
                print(f"  - {error}")
            continue
        missing_environment = workflow_environment_errors(definition)
        if missing_environment:
            errors += 1
            total_blocked += 1
            print(
                "[BLOCKED] Missing workflow environment values: "
                + ", ".join(missing_environment)
            )
            continue

        client = clients.get(definition.table_code)
        if client is None or definition.table_code in schema_blocked:
            errors += 1
            total_blocked += 1
            print("[BLOCKED] Airtable schema preflight failed for this table.")
            continue
        missing_columns = missing_required_columns(definition, client)
        if missing_columns:
            errors += 1
            total_blocked += 1
            print(
                f"[BLOCKED] {TABLES[definition.table_code].label} is missing "
                "columns this workflow reads: " + ", ".join(missing_columns)
            )
            continue
        state = StateManager(client)
        try:
            plan = state.select(
                definition,
                batch_size=args.batch_size,
                execute=args.execute,
                record_ids=args.record_id,
                force=args.force,
                run_id=run_id,
                exclude_ids=(
                    dry_run_consumed[definition.table_code]
                    if not args.execute
                    else None
                ),
            )
        except Exception as error:
            errors += 1
            print(f"[ERROR] Reservation: {error}")
            continue
        if plan.skipped_metadata:
            for record_id, missing in plan.skipped_metadata:
                print(f"[SKIP] {record_id}: missing {', '.join(missing)}")
        if not plan.reservations:
            print(
                f"[INFO] No new anchors required or eligible "
                f"(completed={plan.completed_count}, target={args.batch_size})."
            )
            continue
        count = len(plan.reservations)
        estimate = CallEstimate()
        for reservation in plan.reservations:
            estimate += workflow_class.estimate_for(reservation)
        total_planned += count
        print(
            f"[PLAN] completed={plan.completed_count}/{args.batch_size}; "
            f"reserved-or-new={count}; calls: "
            f"Krea={estimate.krea}, "
            f"Qwen={estimate.qwen}, "
            f"Kie={estimate.kie}, "
            f"Fal={estimate.fal}"
        )
        print(
            "[OUTPUTS] "
            + ", ".join(
                f"{name} ({ratio})"
                for name, ratio in zip(
                    workflow_class.final_filenames,
                    workflow_class.final_aspect_ratios,
                )
            )
        )
        for reservation in plan.reservations:
            partners = ", ".join(item.record_id for item in reservation.partners) or "none"
            print(f"  - anchor={reservation.anchor.record_id}; partners={partners}")
        if not args.execute:
            for reservation in plan.reservations:
                dry_run_consumed[definition.table_code].add(
                    reservation.anchor.record_id
                )
                dry_run_consumed[definition.table_code].update(
                    partner.record_id for partner in reservation.partners
                )
            continue

        for reservation in plan.reservations:
            context = WorkflowContext(
                settings=settings,
                reservation=reservation,
                airtable=client,
                assets=assets,
                krea=krea,
                qwen=qwen,
                kie=kie,
                fal=fal,
            )
            workflow = create_workflow(definition.key, context)
            try:
                workflow.preflight()
                state.mark_running(reservation)
                result = workflow.execute()
                state.mark_complete(reservation, result.filenames)
                total_completed += 1
                print(
                    f"[OK] {reservation.anchor.record_id}: "
                    + ", ".join(result.filenames)
                )
            except KeyboardInterrupt:
                print("[STOP] Interrupted; reserved state is retained for resume.")
                return 130
            except Exception as error:
                errors += 1
                total_failed += 1
                state.mark_failed(reservation, error)
                print(f"[ERROR] {reservation.anchor.record_id}: {error}")

    if not args.execute:
        print("\n[DRY RUN] No Airtable records were changed and no paid calls were made.")
    print(
        f"[SUMMARY] planned={total_planned}, completed_now={total_completed}, "
        f"failed={total_failed}, blocked_workflows={total_blocked}"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutomationError as error:
        print(f"[FATAL] {error}", file=sys.stderr)
        raise SystemExit(2)
