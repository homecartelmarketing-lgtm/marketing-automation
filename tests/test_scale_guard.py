import os
import unittest
from unittest import mock

from content_automation.scale_guard import (
    SCALE_AUDIT_FIELD,
    SCALE_CHECK_FIELD,
    SCALE_RETRY_FIELD,
    ScaleCheck,
    blend_with_scale_guard,
    build_lock_text,
    check_scale,
    compute_scale_target,
    ensure_scale_fields,
    format_scale_audit,
    merge_scale_fields,
    parse_json_object,
    scale_tolerance,
    write_scale_fields,
)


def _measure_reply(
    *,
    reference="dining table",
    cm=180,
    axis="horizontal",
    fraction=0.45,
    confidence="high",
):
    return (
        '{"reference": "%s", "reference_cm": %s, "axis": "%s", '
        '"reference_fraction": %s, "confidence": "%s", "reason": "visible beside the fixture"}'
        % (reference, cm, axis, fraction, confidence)
    )


def _check_reply(*, reference=0.40, fixture=0.18, confidence="high", visible=True):
    return (
        '{"reference_visible": %s, "fixture_visible": true, '
        '"reference_fraction": %s, "fixture_fraction": %s, '
        '"confidence": "%s", "reason": "measured against the table"}'
        % (str(visible).lower(), reference, fixture, confidence)
    )


class FakeFal:
    def __init__(self, replies):
        self.replies = list(replies)
        self.vision_prompts = []
        self.blend_prompts = []

    def generate_vision_prompt(self, image_urls, prompt, model=None):
        self.vision_prompts.append(prompt)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    def generate(self, prompt, image_urls, **kwargs):
        self.blend_prompts.append(prompt)
        return f"https://images.example/blend-{len(self.blend_prompts)}.jpg"


def _target(fal=None, *, measurement="W 80cm x H 60cm", product_type="chandelier"):
    fal = fal or FakeFal([_measure_reply()])
    return compute_scale_target(
        fal,
        room_url="https://images.example/room.jpg",
        product_url="https://images.example/product.jpg",
        product_type=product_type,
        measurement=measurement,
    )


class ParseJsonTests(unittest.TestCase):
    def test_plain_json(self):
        self.assertEqual(parse_json_object('{"a": 1}'), {"a": 1})

    def test_fenced_json(self):
        self.assertEqual(parse_json_object('```json\n{"a": 1}\n```'), {"a": 1})

    def test_prose_around_json(self):
        self.assertEqual(parse_json_object('Here: {"a": 1} done'), {"a": 1})

    def test_garbage_returns_none(self):
        self.assertIsNone(parse_json_object("no json here"))
        self.assertIsNone(parse_json_object(""))


class ToleranceTests(unittest.TestCase):
    def test_default(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertAlmostEqual(scale_tolerance(), 0.15)

    def test_bad_value_falls_back(self):
        with mock.patch.dict(os.environ, {"SCALE_GUARD_TOLERANCE": "abc"}):
            self.assertAlmostEqual(scale_tolerance(), 0.15)

    def test_clamped(self):
        with mock.patch.dict(os.environ, {"SCALE_GUARD_TOLERANCE": "0.01"}):
            self.assertAlmostEqual(scale_tolerance(), 0.05)
        with mock.patch.dict(os.environ, {"SCALE_GUARD_TOLERANCE": "5"}):
            self.assertAlmostEqual(scale_tolerance(), 0.50)


class ComputeTargetTests(unittest.TestCase):
    def test_supplier_width_drives_the_target(self):
        target = _target()
        self.assertIsNotNone(target)
        self.assertEqual(target.fixture_cm, 80.0)
        self.assertEqual(target.size_source, "supplier")
        self.assertEqual(target.axis, "horizontal")
        self.assertAlmostEqual(target.target_fraction, 0.45 * 80 / 180)
        self.assertIn("dining table", target.reference.name)

    def test_percentage_fraction_is_normalized(self):
        fal = FakeFal([_measure_reply(fraction=45)])
        target = _target(fal)
        self.assertAlmostEqual(target.reference.fraction, 0.45)
        self.assertAlmostEqual(target.target_fraction, 0.45 * 80 / 180)

    def test_pixels_only_when_image_size_known(self):
        fal = FakeFal([_measure_reply()])
        target = compute_scale_target(
            fal,
            room_url="https://images.example/room.jpg",
            product_url="https://images.example/product.jpg",
            product_type="chandelier",
            measurement="W 80cm x H 60cm",
            image_size=(1080, 1920),
        )
        self.assertEqual(target.target_px, round(target.target_fraction * 1080))

    def test_missing_measurement_uses_typical_range(self):
        target = _target(measurement="")
        self.assertEqual(target.size_source, "typical")
        self.assertEqual(target.fixture_cm, 80.0)  # chandelier width midpoint 60..100

    def test_hanging_height_is_treated_as_drop(self):
        fal = FakeFal([_measure_reply(axis="vertical", cm=260, fraction=0.9)])
        target = compute_scale_target(
            fal,
            room_url="https://images.example/room.jpg",
            product_url="https://images.example/product.jpg",
            product_type="chandelier",
            measurement="W 120cm x L 120cm x H 300cm",
        )
        self.assertEqual(target.size_source, "typical")
        self.assertLessEqual(target.fixture_cm, 90.0)

    def test_low_confidence_is_rejected(self):
        fal = FakeFal([_measure_reply(confidence="low")])
        self.assertIsNone(_target(fal))

    def test_null_reference_is_rejected(self):
        fal = FakeFal(['{"reference": null, "reference_cm": 0, "axis": "", "reference_fraction": 0}'])
        self.assertIsNone(_target(fal))

    def test_suspicious_fraction_is_rejected(self):
        fal = FakeFal([_measure_reply(fraction=0.01)])
        self.assertIsNone(_target(fal))

    def test_vision_failure_is_swallowed(self):
        fal = FakeFal([RuntimeError("boom")])
        self.assertIsNone(_target(fal))

    def test_unparseable_reply_is_swallowed(self):
        fal = FakeFal(["not json"])
        self.assertIsNone(_target(fal))

    def test_instruction_carries_the_supplier_size(self):
        fal = FakeFal([_measure_reply()])
        _target(fal)
        self.assertIn("80", fal.vision_prompts[0])
        self.assertIn("dining table", fal.vision_prompts[0])


class CheckTests(unittest.TestCase):
    def test_matching_size_passes(self):
        target = _target()
        fal = FakeFal([_check_reply(reference=0.40, fixture=0.18)])
        check = check_scale(
            fal, blended_url="https://images.example/blend.jpg", target=target
        )
        self.assertEqual(check.verdict, "Pass")
        self.assertTrue(check.ok)
        self.assertAlmostEqual(check.ratio, (0.18 / 0.40 * 180) / 80.0)

    def test_too_big_is_flagged(self):
        target = _target()
        fal = FakeFal([_check_reply(reference=0.40, fixture=0.40)])
        check = check_scale(
            fal, blended_url="https://images.example/blend.jpg", target=target
        )
        self.assertEqual(check.verdict, "Too Big")
        self.assertGreater(check.implied_cm, target.fixture_cm)

    def test_too_small_is_flagged(self):
        target = _target()
        fal = FakeFal([_check_reply(reference=0.80, fixture=0.20)])
        check = check_scale(
            fal, blended_url="https://images.example/blend.jpg", target=target
        )
        self.assertEqual(check.verdict, "Too Small")

    def test_tolerance_is_configurable(self):
        target = _target()
        fal = FakeFal([_check_reply(reference=0.40, fixture=0.21)])
        check = check_scale(
            fal,
            blended_url="https://images.example/blend.jpg",
            target=target,
            tolerance=0.30,
        )
        self.assertEqual(check.verdict, "Pass")

    def test_missing_reference(self):
        target = _target()
        fal = FakeFal([_check_reply(visible=False)])
        check = check_scale(
            fal, blended_url="https://images.example/blend.jpg", target=target
        )
        self.assertEqual(check.verdict, "No Reference")

    def test_vision_failure_is_error_verdict(self):
        target = _target()
        fal = FakeFal([RuntimeError("boom")])
        check = check_scale(
            fal, blended_url="https://images.example/blend.jpg", target=target
        )
        self.assertEqual(check.verdict, "Error")


class BlendLoopTests(unittest.TestCase):
    def _blend(self, fal, **kwargs):
        return blend_with_scale_guard(
            fal,
            prompt="Blend the fixture into the room.",
            room_url="https://images.example/room.jpg",
            product_url="https://images.example/product.jpg",
            product_type="chandelier",
            measurement="W 80cm x H 60cm",
            item_name="Nordora | Chandelier",
            **kwargs,
        )

    def test_disabled_skips_every_extra_call(self):
        fal = FakeFal([])
        with mock.patch.dict(os.environ, {"SCALE_GUARD_ENABLED": "0"}):
            result = self._blend(fal)
        self.assertEqual(result.first_check.verdict, "Skipped")
        self.assertEqual(result.attempts, 1)
        self.assertEqual(len(fal.vision_prompts), 0)
        self.assertEqual(len(fal.blend_prompts), 1)
        self.assertEqual(result.image_url, "https://images.example/blend-1.jpg")

    def test_no_target_falls_back_to_one_blend(self):
        fal = FakeFal([_measure_reply(confidence="low")])
        result = self._blend(fal)
        self.assertEqual(result.first_check.verdict, "No Reference")
        self.assertEqual(len(fal.blend_prompts), 1)

    def test_pass_keeps_the_first_blend(self):
        fal = FakeFal([_measure_reply(), _check_reply(reference=0.40, fixture=0.18)])
        result = self._blend(fal)
        self.assertEqual(result.check.verdict, "Pass")
        self.assertEqual(result.attempts, 1)
        self.assertEqual(len(fal.blend_prompts), 1)
        self.assertIn("MEASURED SCALE TARGET", fal.blend_prompts[0])

    def test_retry_passes_and_replaces_the_image(self):
        fal = FakeFal(
            [
                _measure_reply(),
                _check_reply(reference=0.40, fixture=0.40),
                _check_reply(reference=0.40, fixture=0.18),
            ]
        )
        result = self._blend(fal)
        self.assertEqual(result.check.verdict, "Pass After Retry")
        self.assertEqual(result.kept_attempt, 2)
        self.assertEqual(result.image_url, "https://images.example/blend-2.jpg")
        self.assertIn("SCALE CORRECTION", fal.blend_prompts[1])

    def test_keeps_the_better_attempt_when_retry_still_fails(self):
        fal = FakeFal(
            [
                _measure_reply(),
                _check_reply(reference=0.40, fixture=0.40),  # implied 180, ratio 2.25
                _check_reply(reference=0.40, fixture=0.28),  # implied 126, ratio 1.58
            ]
        )
        result = self._blend(fal)
        self.assertEqual(result.check.verdict, "Too Big")
        self.assertEqual(result.kept_attempt, 2)
        self.assertEqual(result.image_url, "https://images.example/blend-2.jpg")

    def test_keeps_the_first_attempt_when_the_retry_is_worse(self):
        fal = FakeFal(
            [
                _measure_reply(),
                _check_reply(reference=0.40, fixture=0.30),  # ratio 1.69
                _check_reply(reference=0.40, fixture=0.50),  # ratio 2.81
            ]
        )
        result = self._blend(fal)
        self.assertEqual(result.kept_attempt, 1)
        self.assertEqual(result.image_url, "https://images.example/blend-1.jpg")

    def test_failed_retry_blend_keeps_the_first(self):
        class ExplodingSecondBlend(FakeFal):
            def generate(self, prompt, image_urls, **kwargs):
                if self.blend_prompts:
                    raise RuntimeError("blend failed")
                return super().generate(prompt, image_urls, **kwargs)

        fal = ExplodingSecondBlend(
            [_measure_reply(), _check_reply(reference=0.40, fixture=0.40)]
        )
        result = self._blend(fal)
        self.assertEqual(result.retry, "Retry Failed")
        self.assertEqual(result.image_url, "https://images.example/blend-1.jpg")

    def test_missing_check_reference_skips_the_retry(self):
        fal = FakeFal([_measure_reply(), _check_reply(visible=False)])
        result = self._blend(fal)
        self.assertEqual(result.first_check.verdict, "No Reference")
        self.assertEqual(result.retry, "Not Needed")
        self.assertEqual(len(fal.blend_prompts), 1)


class AuditTests(unittest.TestCase):
    def _result(self, verdict, retry="Not Needed", kept=1):
        return blend_with_scale_guard(
            FakeFal(
                [
                    _measure_reply(),
                    _check_reply(reference=0.40, fixture=0.18)
                    if verdict == "Pass"
                    else _check_reply(reference=0.40, fixture=0.40),
                ]
            ),
            prompt="Blend.",
            room_url="https://images.example/room.jpg",
            product_url="https://images.example/product.jpg",
            product_type="chandelier",
            measurement="W 80cm x H 60cm",
        )

    def test_audit_reports_size_source_and_verdict(self):
        result = self._result("Pass")
        audit = format_scale_audit(result, slot=0, total=1)
        self.assertIn("slot 0 of 1", audit)
        self.assertIn("supplier W 80cm x H 60cm", audit)
        self.assertIn("dining table", audit)
        self.assertIn("attempt 1: 101% of target -> Pass", audit)

    def test_audit_without_target(self):
        result = blend_with_scale_guard(
            FakeFal([]),
            prompt="Blend.",
            room_url="https://images.example/room.jpg",
            product_url="https://images.example/product.jpg",
        )
        audit = format_scale_audit(result)
        self.assertIn("reference: none", audit)
        self.assertIn("attempt 1: No Reference", audit)

    def test_merge_picks_the_worst_verdict(self):
        good = mock.Mock(
            check=ScaleCheck(verdict="Pass"),
            retry="Not Needed",
            target=None,
            first_check=ScaleCheck(verdict="Pass"),
            retry_check=None,
            kept_attempt=1,
            note="",
        )
        bad = mock.Mock(
            check=ScaleCheck(verdict="Too Big", ratio=1.8),
            retry="Retried",
            target=None,
            first_check=ScaleCheck(verdict="Too Big", ratio=1.8),
            retry_check=None,
            kept_attempt=1,
            note="",
        )
        fields = merge_scale_fields([(0, good), (1, bad)])
        self.assertEqual(fields[SCALE_CHECK_FIELD], "Too Big")
        self.assertEqual(fields[SCALE_RETRY_FIELD], "Retried")
        self.assertIn("slot 0 of 2", fields[SCALE_AUDIT_FIELD])
        self.assertIn("slot 1 of 2", fields[SCALE_AUDIT_FIELD])

    def test_merge_accepts_bare_results(self):
        result = self._result("Pass")
        fields = merge_scale_fields([result])
        self.assertEqual(fields[SCALE_CHECK_FIELD], "Pass")
        self.assertEqual(fields[SCALE_RETRY_FIELD], "Not Needed")


class FieldSetupTests(unittest.TestCase):
    def test_ensure_uses_select_helper_when_available(self):
        airtable = mock.Mock()
        ensure_scale_fields(airtable)
        names = [call.args[0] for call in airtable.ensure_single_select_options.call_args_list]
        self.assertIn(SCALE_CHECK_FIELD, names)
        self.assertIn(SCALE_RETRY_FIELD, names)
        airtable.ensure_fields.assert_called_once_with({SCALE_AUDIT_FIELD: "multilineText"})

    def test_ensure_supports_clients_that_need_execute(self):
        airtable = mock.Mock(spec=["ensure_fields"])
        ensure_scale_fields(airtable)
        airtable.ensure_fields.assert_called_once()
        self.assertTrue(airtable.ensure_fields.call_args.kwargs.get("execute"))

    def test_write_retries_after_creating_fields(self):
        airtable = mock.Mock()
        airtable.update_records.side_effect = [RuntimeError("missing field"), None]
        result = AuditTests()._result("Pass")
        write_scale_fields(airtable, "rec1", [result])
        self.assertEqual(airtable.update_records.call_count, 2)

    def test_write_never_raises(self):
        airtable = mock.Mock()
        airtable.update_records.side_effect = RuntimeError("always")
        airtable.ensure_fields.side_effect = RuntimeError("still")
        result = AuditTests()._result("Pass")
        write_scale_fields(airtable, "rec1", [result])


class LockTextTests(unittest.TestCase):
    def test_lock_states_real_size_and_target(self):
        target = _target()
        text = build_lock_text(target)
        self.assertIn("80 cm", text)
        self.assertIn("180 cm", text)
        self.assertIn("dining table", text)
        self.assertIn("MEASURED SCALE TARGET", text)


if __name__ == "__main__":
    unittest.main()
