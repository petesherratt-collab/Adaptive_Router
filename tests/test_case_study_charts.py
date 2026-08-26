import copy
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

import build_case_study_charts as charts


class CaseStudyChartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = charts.load_analysis()

    def test_committed_analysis_identity(self):
        self.assertEqual(
            self.document["analysis_id"],
            "oos_validation_v1_strict",
        )
        self.assertEqual(
            self.document["benchmark_sha256"],
            charts.BENCHMARK_SHA256,
        )

    def test_builds_exactly_three_named_charts(self):
        rendered = charts.build_charts(self.document)

        self.assertEqual(
            set(rendered),
            set(charts.OUTPUTS.values()),
        )
        self.assertEqual(len(rendered), 3)

    def test_generation_is_deterministic(self):
        first = charts.build_charts(self.document)
        second = charts.build_charts(self.document)

        self.assertEqual(first, second)

    def test_every_chart_is_valid_accessible_svg(self):
        rendered = charts.build_charts(self.document)

        for filename, content in rendered.items():
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

                title = root.find(
                    "{http://www.w3.org/2000/svg}title"
                )
                description = root.find(
                    "{http://www.w3.org/2000/svg}desc"
                )

                self.assertIsNotNone(title)
                self.assertIsNotNone(description)
                self.assertTrue(title.text)
                self.assertTrue(description.text)

    def test_policy_chart_contains_frozen_results(self):
        content = charts.render_policy_chart(self.document)

        for label in (
            "Always local",
            "Coarse class",
            "Fine capability",
            "Always remote",
            "39.0%",
            "78.5%",
            "85.5%",
            "100.0%",
        ):
            with self.subTest(label=label):
                self.assertIn(label, content)

    def test_family_chart_contains_all_families_and_rates(self):
        content = charts.render_family_chart(self.document)

        for label in charts.FAMILY_LABELS.values():
            with self.subTest(label=label):
                self.assertIn(label, content)

        for rate in (
            "80.0%",
            "40.0%",
            "84.0%",
            "28.0%",
            "0.0%",
            "100.0%",
        ):
            with self.subTest(rate=rate):
                self.assertIn(rate, content)

    def test_frontier_contains_all_policy_points(self):
        content = charts.render_frontier_chart(self.document)

        for label in (
            "Always local (39.0%)",
            "Coarse class (78.5%)",
            "Fine capability (85.5%)",
            "Always remote (100.0%)",
        ):
            with self.subTest(label=label):
                self.assertIn(label, content)

    def test_chart_values_come_from_analysis_document(self):
        changed = copy.deepcopy(self.document)

        for row in changed["policies"]:
            if row["policy"] == "fine_capability":
                row["selected_pass_rate"] = 0.123

        content = charts.render_policy_chart(changed)

        self.assertIn("12.3%", content)
        self.assertNotIn("85.5%", content)

    def test_wrong_benchmark_hash_is_rejected(self):
        changed = copy.deepcopy(self.document)
        changed["benchmark_sha256"] = "wrong"

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "analysis.json"
            path.write_text(
                json.dumps(changed),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ValueError,
                "SHA-256",
            ):
                charts.load_analysis(path)

    def test_wrong_policy_set_is_rejected(self):
        changed = copy.deepcopy(self.document)
        changed["policies"] = changed["policies"][:-1]

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "analysis.json"
            path.write_text(
                json.dumps(changed),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ValueError,
                "policy set",
            ):
                charts.load_analysis(path)

    def test_wrong_family_set_is_rejected(self):
        changed = copy.deepcopy(self.document)
        changed["per_family"].pop("sentiment")

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "analysis.json"
            path.write_text(
                json.dumps(changed),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ValueError,
                "family set",
            ):
                charts.load_analysis(path)

    def test_writer_uses_lf_and_refuses_overwrite(self):
        rendered = charts.build_charts(self.document)

        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory) / "assets"
            paths = charts.write_charts(
                rendered,
                output_dir,
            )

            self.assertEqual(len(paths), 3)

            for path in paths:
                with self.subTest(path=path.name):
                    content = path.read_bytes()
                    self.assertNotIn(b"\r\n", content)
                    self.assertTrue(content.endswith(b"\n"))

            with self.assertRaises(FileExistsError):
                charts.write_charts(
                    rendered,
                    output_dir,
                )

    def test_outputs_contain_no_generation_timestamp(self):
        rendered = charts.build_charts(self.document)

        for filename, content in rendered.items():
            with self.subTest(filename=filename):
                self.assertNotIn("generated at", content.lower())
                self.assertNotIn("2026-08-26T", content)


if __name__ == "__main__":
    unittest.main()
