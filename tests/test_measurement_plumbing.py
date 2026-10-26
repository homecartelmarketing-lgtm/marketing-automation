import unittest
from unittest import mock

from content_automation.akeneo_client import (
    PRODUCT_DETAIL_ATTRIBUTES,
    PRODUCT_SEARCH_ATTRIBUTES,
    format_measurement,
    metadata_from_product,
)
from content_automation.scraping.airtable import ScrapeAirtableClient
from content_automation.scraping.furniture_item import FurnitureItemScrapeRunner
from content_automation.scraping.products import ProductItem


def _attr(value):
    return [{"data": value}]


class FormatMeasurementTests(unittest.TestCase):
    def test_capitalized_axis_attributes_are_read(self):
        product = {
            "values": {
                "Width": _attr({"amount": 60, "unit": "CENTIMETER"}),
                "Height": _attr({"amount": 80, "unit": "CENTIMETER"}),
            }
        }
        self.assertEqual(format_measurement(product), "W 60cm x H 80cm")

    def test_direct_measurement_wins_over_axes(self):
        product = {
            "values": {
                "Measurement": _attr("W 60cm x H 80cm"),
                "Width": _attr({"amount": 999, "unit": "CENTIMETER"}),
            }
        }
        self.assertEqual(format_measurement(product), "W 60cm x H 80cm")

    def test_falls_back_to_description_text(self):
        product = {
            "values": {
                "description": _attr("<p>Dimensions: W 25cm x H 48cm</p>"),
            }
        }
        self.assertIn("W 25cm x H 48cm", format_measurement(product))


class MetadataTests(unittest.TestCase):
    def test_metadata_includes_measurement(self):
        product = {
            "values": {
                "name": _attr("Nordora | Chandelier"),
                "Measurement": _attr("W 80cm x H 70cm"),
            }
        }
        metadata = metadata_from_product(product)
        self.assertEqual(metadata["Item Name"], "Nordora")
        self.assertEqual(metadata["Product Type"], "Chandelier")
        self.assertEqual(metadata["Measurement"], "W 80cm x H 70cm")

    def test_metadata_without_measurement_is_empty(self):
        product = {"values": {"name": _attr("Nordora | Pendant")}}
        self.assertEqual(metadata_from_product(product)["Measurement"], "")


class AttributeRequestTests(unittest.TestCase):
    def test_detail_attributes_request_measurement_and_description(self):
        self.assertIn("measurement", PRODUCT_DETAIL_ATTRIBUTES)
        self.assertIn("Measurement", PRODUCT_DETAIL_ATTRIBUTES)
        self.assertIn("description", PRODUCT_DETAIL_ATTRIBUTES)

    def test_search_attributes_request_capitalized_axes(self):
        for code in ("Width", "Height", "Length", "Diameter"):
            self.assertIn(code, PRODUCT_SEARCH_ATTRIBUTES)


class EnsureProductFieldsTests(unittest.TestCase):
    def _ensure(self, existing: set[str]) -> dict[str, str]:
        client = ScrapeAirtableClient("token", "base", "table")
        with mock.patch.object(client, "known_field_names", return_value=existing), \
                mock.patch.object(client, "ensure_fields") as ensure:
            client.ensure_product_fields(items_per_row=2)
        return ensure.call_args.args[0] if ensure.called else {}

    def test_measurement_slots_are_created_when_absent(self):
        required = self._ensure({"Furniture Item", "SKU", "Item Name"})
        self.assertEqual(required["Measurement"], "singleLineText")
        self.assertEqual(required["Measurement2"], "singleLineText")

    def test_unslotted_measurement_column_covers_every_slot(self):
        required = self._ensure({"Furniture Item", "SKU", "Item Name", "Measurement"})
        self.assertNotIn("Measurement", required)
        self.assertNotIn("Measurement2", required)


class UploadItemMeasurementTests(unittest.TestCase):
    def _run_upload(self, measurement_field: str | None) -> dict:
        airtable = mock.Mock()
        airtable.has_field.return_value = False
        airtable.find_field_name.return_value = None
        airtable.create_record.return_value = "rec1"
        akeneo = mock.Mock()
        downloaded = mock.Mock()
        akeneo.download_media.return_value = downloaded

        runner = FurnitureItemScrapeRunner(
            akeneo,
            airtable,
            category_code="chandeliers",
            style_code="modern",
            field_name="Furniture Item",
            item_name_field="Item Name",
            sku_field="SKU",
            measurement_field=measurement_field,
        )
        item = ProductItem(
            sku="SKU-1",
            item_name="Nordora",
            media_code="media-1",
            product_type="Chandelier",
            measurement="W 80cm x H 70cm",
        )
        self.assertTrue(runner._upload_item(item))
        return airtable.create_record.call_args.args[0]

    def test_measurement_is_written_when_configured(self):
        fields = self._run_upload("Measurement")
        self.assertEqual(fields["Measurement"], "W 80cm x H 70cm")

    def test_measurement_is_omitted_when_opted_out(self):
        fields = self._run_upload(None)
        self.assertNotIn("Measurement", fields)


if __name__ == "__main__":
    unittest.main()
