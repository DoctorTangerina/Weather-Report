"""Discovery respects selected geography and requested calendar months."""

import io
import json
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from data.data_gathering import datasets

TEST_BOX = (-74.0, -34.0, -34.0, 6.0)


def entry(identifier, short_name="M2TMNXSLV"):
    return {
        "id": identifier,
        "short_name": short_name,
        "title": "Monthly temperature",
        "version_id": "5.12.4",
        "time_start": "2000-01-01T00:00:00Z",
    }


class DatasetSearchTests(unittest.TestCase):
    def setUp(self):
        themes = patch.object(datasets, "load_themes", return_value={"temperature": {"keyword": "temperature"}})
        themes.start()
        self.addCleanup(themes.stop)

    def test_period_includes_last_day_of_leap_february(self):
        self.assertEqual(
            datasets.temporal_range("2024-01", "2024-02"),
            "2024-01-01T00:00:00Z,2024-02-29T23:59:59Z",
        )
        with self.assertRaises(ValueError):
            datasets.temporal_range("2024-03", "2024-02")

    def test_invalid_bbox_is_rejected(self):
        with self.assertRaises(ValueError):
            datasets.SearchArea("invalid", (10, -20, -10, 20))

    def test_box_comes_from_config_and_catalog_regions_still_work(self):
        with patch("data.data_gathering.config.load_config", return_value={"BBOX": [0, -10, 20, 10]}):
            self.assertEqual(datasets.default_area().bbox, (0, -10, 20, 10))
            self.assertEqual(datasets.default_area().name, "box")
        amazon = datasets.region_area("amazon-basin", datasets.ROOT / "data/stub/catalog.json")
        self.assertEqual(amazon.bbox, (-70, -10, -50, 2))

    def test_only_datasets_overlapping_every_selected_region_are_listed(self):
        areas = [datasets.SearchArea("first", (-70, -10, -50, 2)),
                 datasets.SearchArea("second", (74, 18, 84, 26))]
        with patch.object(datasets, "cmr_entries", side_effect=[
            [entry("shared"), entry("first-only")], [entry("shared")]
        ]):
            result = datasets.search("temperature", areas, "2000-01", "2024-12")
        self.assertEqual([item["collection_id"] for item in result], ["shared"])

    def test_daily_and_hourly_datasets_are_not_filtered_out(self):
        daily = {**entry("daily"), "title": "Daily temperature"}
        hourly = {**entry("hourly"), "title": "3-hourly air temperature"}
        with patch.object(datasets, "cmr_entries", return_value=[daily, hourly]):
            result = datasets.search("temperature", [datasets.SearchArea("box", TEST_BOX)], "2000-01", "2024-12")
        self.assertEqual({item["cadence"] for item in result}, {"Daily", "3-hourly"})

    def test_exact_dates_are_supported(self):
        self.assertEqual(datasets.temporal_range("2024-02-12", "2024-02-15"),
                         "2024-02-12T00:00:00Z,2024-02-15T23:59:59Z")

    def test_custom_keyword_is_passed_without_theme_rewriting(self):
        with patch.object(datasets, "cmr_entries", return_value=[entry("match")]) as query:
            datasets.search("temperature", [datasets.SearchArea("box", TEST_BOX)],
                            "2024-01", "2024-03", keyword="heat waves")
        parameters = query.call_args.args[1]
        self.assertEqual(parameters["keyword"], "heat waves")
        self.assertFalse(any(key.startswith("science_keywords") for key in parameters))

    def test_selection_filters_cmr_search(self):
        with patch.object(datasets, "cmr_entries", return_value=[entry("chosen")]) as query:
            datasets.search("", [datasets.SearchArea("box", TEST_BOX)],
                            "2024-01", "2024-03", keyword="temperature", selected=["chosen"])
        self.assertEqual(query.call_args.args[1]["concept_id[]"], ["chosen"])

    def test_download_link_excludes_inherited_and_external_links(self):
        granule = {"id": "example", "links": [
            {"rel": "http://esipfed.org/ns/fedsearch/1.1/data#", "href": "https://example.com/file.nc4"},
            {"rel": "http://esipfed.org/ns/fedsearch/1.1/data#", "href": "https://data.gesdisc.earthdata.nasa.gov/unrelated.nc4", "inherited": True},
            {"rel": "http://esipfed.org/ns/fedsearch/1.1/data#", "href": "https://data.gesdisc.earthdata.nasa.gov/real.nc4"},
        ]}
        self.assertEqual(datasets.file_url(granule), "https://data.gesdisc.earthdata.nasa.gov/real.nc4")

    def test_size_estimate_uses_file_count_and_labels_sampling(self):
        areas = [datasets.SearchArea("box", TEST_BOX)]
        with patch.object(datasets, "cmr_page", return_value=(
            [{"granule_size": "1"}, {"granule_size": "3"}], 100
        )) as page:
            result = datasets.estimate_size("collection", areas, "2000-01", "2024-12")
        self.assertEqual(result["bytes"], 200 * 1024**2)
        self.assertFalse(result["exact"])
        self.assertIn("estimate", datasets.size_label(result))
        self.assertEqual(page.call_args.args[1]["options[bounding_box][or]"], "true")

    def test_missing_size_is_unknown_rather_than_zero(self):
        with patch.object(datasets, "cmr_page", return_value=([{"id": "unknown"}], 1)):
            result = datasets.estimate_size("collection", [datasets.SearchArea("box", TEST_BOX)], "2000-01", "2024-12")
        self.assertIsNone(result["bytes"])
        self.assertIn("unknown", datasets.size_label(result))

    def test_complete_size_metadata_is_summed(self):
        with patch.object(datasets, "cmr_page", return_value=([
            {"granule_size": "1"}, {"granule_size": "3"}
        ], 2)):
            result = datasets.estimate_size("collection", [datasets.SearchArea("box", TEST_BOX)], "2000-01", "2024-12")
        self.assertEqual(result["bytes"], 4 * 1024**2)
        self.assertTrue(result["exact"])

    def test_pagination_does_not_drop_results_or_send_credentials(self):
        first = io.StringIO(json.dumps({"feed": {"entry": [entry(str(i)) for i in range(100)]}}))
        second = io.StringIO(json.dumps({"feed": {"entry": [entry("last")]}}))
        first.headers = {"CMR-Hits": "101"}
        second.headers = {"CMR-Hits": "101"}
        with patch.object(datasets, "urlopen", side_effect=[first, second]) as opened:
            result = list(datasets.cmr_entries("collections", {"provider[]": ["GES_DISC", "LPCLOUD"]}))
        self.assertEqual(len(result), 101)
        request = opened.call_args_list[1].args[0]
        self.assertIsNone(request.get_header("Authorization"))
        query = parse_qs(urlsplit(request.full_url).query)
        self.assertEqual(query["page_num"], ["2"])
        self.assertEqual(query["provider[]"], ["GES_DISC", "LPCLOUD"])


if __name__ == "__main__":
    unittest.main()
