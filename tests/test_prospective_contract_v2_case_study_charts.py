import copy
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

import build_prospective_contract_v2_case_study_charts as charts


class ProspectiveContractV2ChartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = charts.load_analysis()

    def test_committed_analysis_identity(self):
        self.assertEqual(
            self.document["schema_version"],
            "prospective_contract_validation_v2",
        )
        self.assertEqual(
            self.document["plan_sha256"],
            charts.PLAN_SHA256,
        )
        self.assertEqual(
            self.document["benchmark_sha256"],
            charts.BENCHMARK_SHA256,
        )
        self.assertEqual(
            self.document["contracts_sha256"],
            charts.CONTRACTS_SHA256,
        )

    def test_builds_exactly_four_named_charts(self):
        rendered = charts.build_charts(self.document)
        self.assertEqual(set(rendered), set(charts.OUTPUTS.values()))
        self.assertEqual(len(rendered), 4)

    def test_generation_is_deterministic(self):
        self.assertEqual(
            charts.build_charts(self.document),
            charts.build_charts(self.document),
        )

    def test_every_chart_is_valid_accessible_svg(self):
        for filename, content in charts.build_charts(self.document).items():
            with self.subTest(filename=filename):
                root = ET.fromstring(content)
                self.assertEqual(
                    root.tag,
                    "{http://www.w3.org/2000/svg}svg",
                )
                self.assertEqual(root.attrib["role"], "img")
                self.assertEqual(
                    root.attrib["aria-labelledby"],
                    "chart-title chart-description",
                )
                title = root.find("{http://www.w3.org/2000/svg}title")
                description = root.find("{http://www.w3.org/2000/svg}desc")
                self.assertIsNotNone(title)
                self.assertIsNotNone(description)
                self.assertTrue(title.text)
                self.assertTrue(description.text)

    def test_false_accept_chart_contains_frozen_model_counts(self):
        content = charts.render_false_accepts(self.document)
        for value in (
            "Gemma 3 270M",
            "Gemma 3 1B",
            "Gemma 3 4B",
            "87.5% caught",
            "75.4% caught",
            "83.3% caught",
        ):
            with self.subTest(value=value):
                self.assertIn(value, content)

    def test_contract_chart_contains_frozen_rates(self):
        content = charts.render_contract_types(self.document)
        for value in (
            "45/45 · 100.00%",
            "59/60 · 98.33%",
            "25/35 · 71.43%",
            "15/35 · 42.86%",
        ):
            with self.subTest(value=value):
                self.assertIn(value, content)

    def test_correctness_chart_contains_frozen_counts(self):
        content = charts.render_correctness(self.document)
        for value in ("10/100 · 10%", "25/100 · 25%", "70/100 · 70%"):
            with self.subTest(value=value):
                self.assertIn(value, content)

    def test_accepted_error_chart_contains_frozen_counts(self):
        content = charts.render_accepted_error(self.document)
        for value in (
            "63.9%",
            "23.8%",
            "175 wrong / 274 accepted",
            "31 wrong / 130 accepted",
        ):
            with self.subTest(value=value):
                self.assertIn(value, content)

    def test_chart_values_come_from_analysis_document(self):
        changed = copy.deepcopy(self.document)
        changed["primary"]["by_model"]["gemma3:1b"][
            "oracle_correct_count"
        ] = 12
        content = charts.render_correctness(changed)
        self.assertIn("12/100 · 12%", content)
        self.assertNotIn("25/100 · 25%", content)

    def test_wrong_analysis_hash_is_rejected(self):
        changed = copy.deepcopy(self.document)
        changed["contracts_sha256"] = "wrong"

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "analysis.json"
            path.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                charts.load_analysis(path)

    def test_writer_uses_lf_and_refuses_overwrite(self):
        rendered = charts.build_charts(self.document)
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory) / "assets"
            paths = charts.write_charts(rendered, output_dir)
            self.assertEqual(len(paths), 4)
            for path in paths:
                with self.subTest(path=path.name):
                    content = path.read_bytes()
                    self.assertNotIn(b"\r\n", content)
                    self.assertTrue(content.endswith(b"\n"))
            with self.assertRaises(FileExistsError):
                charts.write_charts(rendered, output_dir)

    def test_committed_assets_match_renderer(self):
        rendered = charts.build_charts(self.document)
        for filename, expected in rendered.items():
            with self.subTest(filename=filename):
                path = charts.OUTPUT_DIR / filename
                self.assertTrue(path.exists())
                self.assertEqual(
                    path.read_text(encoding="utf-8"),
                    expected,
                )

    def test_outputs_contain_no_generation_timestamp(self):
        for filename, content in charts.build_charts(
            self.document
        ).items():
            with self.subTest(filename=filename):
                self.assertNotIn("generated at", content.lower())
                self.assertNotIn("2026-09-01T", content)


if __name__ == "__main__":
    unittest.main()
