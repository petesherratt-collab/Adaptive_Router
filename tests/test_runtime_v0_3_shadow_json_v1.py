import copy
import json
import math
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from local import LocalResult
from remote import RemoteResult
import analyze_runtime_v0_3_shadow_json_v1 as analyzer
import run_runtime_v0_3_shadow_json_v1 as runner
import runtime_v0_3_shadow_json_v1 as pv


ROOT = Path(__file__).resolve().parents[1]


def frozen_root(directory):
    root = Path(directory)
    for name in (pv.PLAN_NAME, pv.BENCHMARK_NAME, pv.CONFIG_NAME):
        shutil.copyfile(ROOT / name, root / name)
    return root


class FrozenDesignTests(unittest.TestCase):
    def test_frozen_hashes_counts_and_strata(self):
        document, tasks, inventory = pv.load_frozen_inputs(ROOT)
        self.assertEqual(pv.file_sha256(ROOT / pv.PLAN_NAME), pv.PLAN_SHA256)
        self.assertEqual(
            pv.file_sha256(ROOT / pv.BENCHMARK_NAME), pv.BENCHMARK_SHA256
        )
        self.assertEqual(len(tasks), 40)
        self.assertEqual(len(inventory), 40)
        self.assertEqual(document["observation_count"], 120)

    def test_duplicate_json_key_rejects(self):
        with self.assertRaisesRegex(pv.FrozenDesignError, "DUPLICATE_JSON_KEY"):
            pv.strict_json_loads('{"a":1,"a":2}')

    def test_unknown_benchmark_field_rejects(self):
        document, _, _ = pv.load_frozen_inputs(ROOT)
        document["extra"] = True
        with self.assertRaisesRegex(
            pv.FrozenDesignError, "BENCHMARK_FIELDS_MISMATCH"
        ):
            pv.validate_benchmark(document)

    def test_oracle_key_is_absent_from_every_runtime_request(self):
        _, tasks, _ = pv.load_frozen_inputs(ROOT)
        for task in tasks:
            self.assertNotIn(
                '"oracle"', json.dumps(task["runtime_request"], sort_keys=True)
            )

    def test_json_oracle_is_recursive_and_type_sensitive(self):
        _, tasks, inventory = pv.load_frozen_inputs(ROOT)
        task = inventory["nested_10"]
        exact = '{"packet":"P-8","values":["alpha",3,null],"flags":{"urgent":false,"reviewed":true}}'
        wrong_order = '{"packet":"P-8","values":[3,"alpha",null],"flags":{"urgent":false,"reviewed":true}}'
        wrong_type = '{"packet":"P-8","values":["alpha","3",null],"flags":{"urgent":false,"reviewed":true}}'
        self.assertTrue(pv.oracle(task, exact).correct)
        self.assertFalse(pv.oracle(task, wrong_order).correct)
        self.assertFalse(pv.oracle(task, wrong_type).correct)
        self.assertEqual(len(tasks), 40)

    def test_shape_can_pass_while_oracle_fails(self):
        _, _, inventory = pv.load_frozen_inputs(ROOT)
        task = inventory["flat_01"]
        raw = '{"batch":"wrong","owner":"wrong","units":0,"ready":false}'
        self.assertEqual(runner._contract_result(task, raw)["status"], "PASS")
        self.assertFalse(pv.oracle(task, raw).correct)


class BudgetAndStateTests(unittest.TestCase):
    def test_remote_attempt_headroom_is_fail_closed(self):
        budget = pv.EvidenceBudget(remote_http_attempts=239)
        with self.assertRaisesRegex(
            pv.BudgetExceeded, "REMOTE_HTTP_ATTEMPT_LIMIT"
        ):
            budget.before_remote()

    def test_cost_crossing_is_retained_then_blocks_next(self):
        budget = pv.EvidenceBudget()
        result = RemoteResult(
            True, "{}", 1.0, "model", cost=0.031, attempt_count=1
        )
        budget.before_remote()
        budget.after_remote(result)
        self.assertEqual(budget.remote_logical_calls, 1)
        with self.assertRaisesRegex(
            pv.BudgetExceeded, "REMOTE_REPORTED_COST_LIMIT"
        ):
            budget.before_remote()

    def test_invalid_attempt_count_rejects(self):
        budget = pv.EvidenceBudget()
        with self.assertRaisesRegex(
            pv.FrozenDesignError, "INVALID_REMOTE_ATTEMPT_COUNT"
        ):
            budget.after_remote(
                RemoteResult(True, "{}", 1.0, "model", attempt_count=3)
            )

    def test_atomic_writer_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            pv.atomic_write_json(path, {"a": 1})
            with self.assertRaises(FileExistsError):
                pv.atomic_write_json(path, {"a": 2})

    def test_existing_partial_rejects(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = pv.output_paths(root)["runs"]
            Path(str(path) + ".partial").write_text("", encoding="utf-8")
            with self.assertRaisesRegex(pv.StateError, "OUTPUT_STATE_NOT_EMPTY"):
                pv.assert_empty_state(root)


class DryRunTests(unittest.TestCase):
    def test_dry_run_uses_only_injected_synthetic_providers(self):
        with patch.object(
            runner.local, "generate", side_effect=AssertionError("local network")
        ), patch.object(
            runner.remote, "generate", side_effect=AssertionError("remote network")
        ):
            result = runner.dry_run(ROOT)
        self.assertEqual(result["provider_network_requests"], 0)
        self.assertEqual(result["synthetic_local_calls"], 120)
        self.assertEqual(result["synthetic_remote_calls"], 120)

    def test_dry_run_does_not_change_repository_output_state(self):
        before = {name: path.exists() for name, path in pv.output_paths(ROOT).items()}
        runner.dry_run(ROOT)
        after = {name: path.exists() for name, path in pv.output_paths(ROOT).items()}
        self.assertEqual(before, after)

    def test_preflight_metadata_makes_no_generation_request(self):
        with tempfile.TemporaryDirectory() as directory:
            root = frozen_root(directory)
            with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test"}, clear=False):
                with patch.object(
                    pv, "implementation_revision", return_value="revision"
                ), patch.object(
                    runner,
                    "fetch_installed_model_metadata",
                    return_value=pv.MODEL_SPEC,
                ), patch.object(
                    runner.local,
                    "generate",
                    side_effect=AssertionError("generation called"),
                ), patch.object(
                    runner.remote,
                    "generate",
                    side_effect=AssertionError("generation called"),
                ):
                    report = runner.preflight_report(root)
        self.assertEqual(report["provider_generation_requests"], 0)
        self.assertEqual(report["runtime_observations"], 120)


class AnalysisTests(unittest.TestCase):
    def test_type7_percentile_fixture(self):
        self.assertEqual(analyzer.percentile_type7([1, 2, 3, 4, 5], 0.25), 2)

    def test_clopper_pearson_zero_error_bound(self):
        expected = 1.0 - 0.05 ** (1.0 / 60)
        self.assertTrue(
            math.isclose(
                analyzer.clopper_pearson_upper(0, 60), expected,
                rel_tol=0, abs_tol=1e-15,
            )
        )
        self.assertLessEqual(analyzer.clopper_pearson_upper(0, 60), 0.05)
        self.assertGreater(analyzer.clopper_pearson_upper(0, 58), 0.05)

    def test_counterfactual_uses_local_only_on_contract_pass(self):
        passing = {
            "local_contract": {"status": "PASS"},
            "local_oracle": {"correct": False},
            "remote_oracle": {"correct": True},
            "local": {"total_ms": 2},
            "remote": {"total_ms": 8},
        }
        rejected = copy.deepcopy(passing)
        rejected["local_contract"]["status"] = "FAIL"
        self.assertEqual(analyzer._counterfactual(passing), (True, False, 2))
        self.assertEqual(analyzer._counterfactual(rejected), (False, True, 8))

    def test_synthetic_analysis_reconciles_and_promotes(self):
        result = runner.dry_run(ROOT)
        self.assertEqual(result["runtime_correct_count"], 120)
        self.assertEqual(result["bootstrap_draws"], 10_000)
        self.assertEqual(result["promotion_decision"], "PROMOTION_CANDIDATE")

    def test_promotion_fails_on_one_local_accepted_error(self):
        _, tasks, _ = pv.load_frozen_inputs(ROOT)
        rows = []
        for task in tasks:
            for repetition in range(1, 4):
                expected = json.dumps(
                    task["oracle"]["expected_json"],
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                contract = runner._contract_result(task, expected)
                rows.append({
                    "task_id": task["task_id"],
                    "repetition": repetition,
                    "stratum": task["stratum"],
                    "runtime_correct": True,
                    "actual_route": "remote",
                    "actual_reason": "SAFE_REMOTE_POLICY",
                    "local": {"total_ms": 2, "cost": None, "attempt_count": 0},
                    "remote": {"total_ms": 8, "cost": 0.0, "attempt_count": 1},
                    "local_contract": contract,
                    "remote_contract": contract,
                    "local_oracle": {"correct": True},
                    "remote_oracle": {"correct": True},
                })
        rows[0]["local_oracle"]["correct"] = False
        scope = analyzer._scope(rows)
        self.assertEqual(scope["local_accepted_error_count"], 1)
        self.assertLess(scope["counterfactual_correct_count"], scope["remote_correct_count"])


if __name__ == "__main__":
    unittest.main()
