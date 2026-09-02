import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from remote import RemoteResult
from runtime_contracts import RuntimeRequest, validate_runtime_output
import analyze_runtime_v0_2_prospective_v1 as analyzer
import runtime_v0_2_prospective_v1 as pv
import run_runtime_v0_2_prospective_v1 as runner


class DesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document, cls.tasks, cls.inventory = pv.load_frozen_inputs()

    def test_frozen_hashes_and_counts(self):
        self.assertEqual(pv.file_sha256(pv.ROOT / pv.PLAN_NAME), pv.PLAN_SHA256)
        self.assertEqual(
            pv.file_sha256(pv.ROOT / pv.BENCHMARK_NAME), pv.BENCHMARK_SHA256
        )
        self.assertEqual(len(self.tasks), 40)
        self.assertEqual(
            [(task["task_id"], rep) for task in self.tasks for rep in range(1, 4)],
            pv.expected_keys(self.tasks),
        )

    def test_every_request_revalidates_without_oracle(self):
        for task in self.tasks:
            mapping = task["runtime_request"]
            self.assertNotIn("oracle", mapping)
            request = RuntimeRequest.from_mapping(mapping)
            self.assertEqual(request.prompt, mapping["prompt"])
            self.assertEqual(set(mapping), {
                "schema_version", "task_class", "prompt", "contract"
            })

    def test_duplicate_json_key_is_rejected(self):
        with self.assertRaisesRegex(pv.FrozenDesignError, "DUPLICATE_JSON_KEY"):
            pv.strict_json_loads('{"suite_id":"a","suite_id":"b"}')

    def test_mutated_order_and_counts_reject(self):
        changed = copy.deepcopy(self.document)
        changed["task_order"][0], changed["task_order"][1] = (
            changed["task_order"][1],
            changed["task_order"][0],
        )
        ordered, _ = pv.validate_benchmark(changed)
        self.assertEqual(ordered[0]["task_id"], changed["task_order"][0])
        changed = copy.deepcopy(self.document)
        changed["tasks"].pop()
        with self.assertRaises(pv.FrozenDesignError):
            pv.validate_benchmark(changed)

    def test_oracle_field_in_request_rejects(self):
        changed = copy.deepcopy(self.document)
        changed["tasks"][0]["runtime_request"]["oracle"] = {"expected": "leak"}
        with self.assertRaises(pv.FrozenDesignError):
            pv.validate_benchmark(changed)


class OracleIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.tasks, cls.inventory = pv.load_frozen_inputs()

    def test_json_shape_can_pass_while_oracle_fails(self):
        task = self.inventory["rtv02pv1_s_01"]
        raw = '{"vendor":"Wrong Vendor","invoice_count":99,"active":false}'
        check = validate_runtime_output(task["runtime_request"]["contract"], raw)
        self.assertEqual(check.status, "PASS")
        self.assertFalse(pv.oracle(task, raw).correct)

    def test_line_shape_can_pass_while_oracle_fails(self):
        task = self.inventory["rtv02pv1_f_01"]
        raw = "- wrong one\n- wrong two\n- wrong three"
        check = validate_runtime_output(task["runtime_request"]["contract"], raw)
        self.assertEqual(check.status, "PASS")
        self.assertFalse(pv.oracle(task, raw).correct)

    def test_wrong_permitted_label_passes_contract_not_oracle(self):
        task = self.inventory["rtv02pv1_c_01"]
        check = validate_runtime_output(
            task["runtime_request"]["contract"], "negative"
        )
        self.assertEqual(check.status, "PASS")
        self.assertFalse(pv.oracle(task, "negative").correct)

    def test_json_oracle_is_type_sensitive_and_allows_numeric_equivalence(self):
        task = self.inventory["rtv02pv1_s_01"]
        self.assertTrue(
            pv.oracle(
                task,
                '{"vendor":"Rowan Supply","invoice_count":6e0,"active":true}',
            ).correct
        )
        self.assertFalse(
            pv.oracle(
                task,
                '{"vendor":"Rowan Supply","invoice_count":true,"active":true}',
            ).correct
        )

    def test_all_deterministic_oracles_match_executor(self):
        for task in self.tasks:
            if task["cohort"] == "deterministic":
                output = runner._synthetic_text(task)
                self.assertTrue(pv.oracle(task, output).correct)


class BudgetAndStateTests(unittest.TestCase):
    def test_remote_attempt_headroom_is_fail_closed(self):
        budget = pv.EvidenceBudget(remote_http_attempts=179)
        with self.assertRaisesRegex(pv.BudgetExceeded, "REMOTE_HTTP_ATTEMPT_LIMIT"):
            budget.before_remote()

    def test_cost_crossing_is_retained_then_blocks_next(self):
        budget = pv.EvidenceBudget()
        budget.before_remote()
        budget.after_remote(
            RemoteResult(
                True, "x", attempt_count=1, cost=pv.MAX_REPORTED_REMOTE_COST_USD + 0.001
            )
        )
        self.assertEqual(budget.remote_logical_calls, 1)
        with self.assertRaisesRegex(pv.BudgetExceeded, "REMOTE_REPORTED_COST_LIMIT"):
            budget.before_remote()

    def test_invalid_attempt_count_rejects(self):
        budget = pv.EvidenceBudget()
        with self.assertRaisesRegex(
            pv.FrozenDesignError, "INVALID_REMOTE_ATTEMPT_COUNT"
        ):
            budget.after_remote(RemoteResult(True, "x", attempt_count=3))

    def test_existing_partial_or_canonical_rejects(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = pv.output_paths(root)["runs"]
            Path(str(path) + ".partial").write_text("partial", encoding="utf-8")
            with self.assertRaises(pv.StateError):
                pv.assert_empty_state(root)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pv.output_paths(root)["summary"].write_text("{}", encoding="utf-8")
            with self.assertRaises(pv.StateError):
                pv.assert_empty_state(root)

    def test_atomic_writer_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            pv.atomic_write_json(path, {"a": 1})
            with self.assertRaises(FileExistsError):
                pv.atomic_write_json(path, {"a": 2})


class DryRunTests(unittest.TestCase):
    def test_dry_run_makes_no_real_provider_call(self):
        with patch.object(
            runner.local, "generate", side_effect=AssertionError("local network")
        ), patch.object(
            runner.remote, "generate", side_effect=AssertionError("remote network")
        ), patch.object(
            runner, "fetch_installed_model_metadata",
            side_effect=AssertionError("metadata network"),
        ):
            result = runner.dry_run()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["provider_network_requests"], 0)
        self.assertEqual(result["repository_outputs_created"], 0)
        self.assertEqual(result["runtime_observations"], 120)
        self.assertEqual(result["synthetic_local_calls"], 90)
        self.assertEqual(result["synthetic_remote_calls"], 90)
        self.assertEqual(result["runtime_correct_count"], 120)
        self.assertEqual(result["bootstrap_draws"], 10_000)

    def test_dry_run_does_not_change_canonical_output_existence(self):
        before = {
            name: path.exists() for name, path in pv.output_paths().items()
        }
        runner.dry_run()
        after = {
            name: path.exists() for name, path in pv.output_paths().items()
        }
        self.assertEqual(before, after)

    def test_final_synthetic_evidence_has_complete_paired_arms(self):
        _, tasks, _ = pv.load_frozen_inputs()
        config = runner._config()
        prompts = {
            task["runtime_request"]["prompt"]: runner._synthetic_text(task)
            for task in tasks
        }
        seen_arguments = []

        def local_fake(prompt, provider_config):
            seen_arguments.append(("local", prompt, set(provider_config)))
            return runner.LocalResult(True, prompts[prompt], 1, 2, 50, 100)

        def remote_fake(prompt, provider_config, key):
            seen_arguments.append(("remote", prompt, set(provider_config)))
            return RemoteResult(
                True, prompts[prompt], 2, provider_config["model"],
                attempt_count=1, cost=0.0,
            )

        metrics = lambda: {
            "available_ram_mb": 5000, "swap_used_mb": 0, "cpu_percent": 1,
            "load_average": [0, 0, 0], "ram_percent": 10, "swap_percent": 0,
            "swap_activity_sample_seconds": 0.1, "swap_in_bytes": 0,
            "swap_in_pages": 0, "swap_out_bytes": 0, "swap_out_pages": 0,
            "timestamp": "synthetic",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = runner.execute_observations(
                tasks, config, "revision", pv.MODEL_SPEC, root,
                local_fake, remote_fake, metrics, lambda count: 0,
                lambda provider_config: {"resident": True, "size_bytes": 1},
                "key",
            )
            rows = [
                json.loads(line)
                for line in pv.output_paths(root)["runs"].read_text().splitlines()
            ]
        self.assertEqual(report["budget"]["local_logical_calls"], 90)
        self.assertEqual(report["budget"]["remote_logical_calls"], 90)
        self.assertEqual(len(rows), 120)
        self.assertNotIn("oracle", {key for _, _, keys in seen_arguments for key in keys})
        pv.validate_rows(rows, tasks, "revision")


class AnalysisTests(unittest.TestCase):
    def test_type7_percentile_fixture(self):
        self.assertEqual(analyzer.percentile_type7([0.0, 10.0], 0.025), 0.25)
        self.assertEqual(analyzer.percentile_type7([0.0, 10.0], 0.975), 9.75)

    def test_synthetic_analysis_reconciles(self):
        _, tasks, _ = pv.load_frozen_inputs()
        config = runner._config()
        prompts = {
            task["runtime_request"]["prompt"]: runner._synthetic_text(task)
            for task in tasks
        }

        def local_fake(prompt, provider_config):
            return runner.LocalResult(True, prompts[prompt], 1, 2, 50, 100)

        def remote_fake(prompt, provider_config, key):
            return RemoteResult(
                True, prompts[prompt], 2, provider_config["model"],
                attempt_count=1, cost=0.000001,
            )

        metrics = lambda: {
            "available_ram_mb": 5000, "swap_used_mb": 0, "cpu_percent": 1,
            "load_average": [0, 0, 0], "ram_percent": 10, "swap_percent": 0,
            "swap_activity_sample_seconds": 0.1, "swap_in_bytes": 0,
            "swap_in_pages": 0, "swap_out_bytes": 0, "swap_out_pages": 0,
            "timestamp": "synthetic",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner.execute_observations(
                tasks, config, "revision", pv.MODEL_SPEC, root,
                local_fake, remote_fake, metrics, lambda count: 0,
                lambda provider_config: {"resident": True, "size_bytes": 1},
                "key",
            )
            report = analyzer.write_analysis(root)
            self.assertTrue(pv.output_paths(root)["analysis_json"].exists())
            self.assertTrue(pv.output_paths(root)["analysis_csv"].exists())
        overall = report["generative"]["overall"]
        self.assertEqual(overall["observation_count"], 90)
        self.assertEqual(overall["runtime_correct_count"], 90)
        self.assertEqual(overall["actual_remote_logical_calls"], 30)
        self.assertEqual(overall["remote_calls_avoided_vs_always_remote"], 60)
        self.assertEqual(sum(overall["overlap"].values()), 90)
        self.assertEqual(report["deterministic"]["observation_count"], 30)
        self.assertEqual(report["deterministic"]["provider_call_count"], 0)


if __name__ == "__main__":
    unittest.main()
