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
import analyze_runtime_v0_3_shadow_json_1b_v1 as analyzer
import run_runtime_v0_3_shadow_json_1b_v1 as runner
import runtime_v0_3_shadow_json_1b_v1 as pv


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
        task = inventory["m1b_nested_10"]
        exact = '{"catalogue":"Dawn","groups":[{"name":"metals","items":["copper","tin"]},{"name":"fibres","items":["flax","hemp"]}]}'
        wrong_order = '{"catalogue":"Dawn","groups":[{"name":"fibres","items":["flax","hemp"]},{"name":"metals","items":["copper","tin"]}]}'
        wrong_type = '{"catalogue":"Dawn","groups":[{"name":"metals","items":["copper","tin"]},{"name":"fibres","items":["flax",7]}]}'
        self.assertTrue(pv.oracle(task, exact).correct)
        self.assertFalse(pv.oracle(task, wrong_order).correct)
        self.assertFalse(pv.oracle(task, wrong_type).correct)
        self.assertEqual(len(tasks), 40)

    def test_shape_can_pass_while_oracle_fails(self):
        _, _, inventory = pv.load_frozen_inputs(ROOT)
        task = inventory["m1b_flat_01"]
        raw = '{"crate":"wrong","steward":"wrong","seals":0,"inspected":false}'
        self.assertEqual(runner._contract_result(task, raw)["status"], "PASS")
        self.assertFalse(pv.oracle(task, raw).correct)

    def test_1b_tasks_do_not_reuse_prior_shadow_content(self):
        candidate, _, _ = pv.load_frozen_inputs(ROOT)
        for prior_name in (
            "benchmark_runtime_v0_3_shadow_json_v1.json",
            "benchmark_runtime_v0_3_shadow_json_v2.json",
        ):
            prior = json.loads((ROOT / prior_name).read_text(encoding="utf-8"))
            for selector in (
                lambda task: task["task_id"],
                lambda task: task["runtime_request"]["prompt"],
                lambda task: json.dumps(
                    task["oracle"]["expected_json"], sort_keys=True
                ),
            ):
                self.assertFalse(
                    {selector(task) for task in prior["tasks"]}
                    & {selector(task) for task in candidate["tasks"]}
                )


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

    def test_failed_remote_without_reported_cost_uses_frozen_reserve(self):
        budget = pv.EvidenceBudget()
        result = RemoteResult(
            False,
            total_ms=1.0,
            model="model",
            error="OPENROUTER_RESPONSE_INVALID",
            attempt_count=1,
            retry_count=0,
        )
        budget.after_remote(result)
        self.assertEqual(budget.unreported_remote_failure_count, 1)
        self.assertEqual(
            budget.reserved_unreported_failure_cost_usd,
            pv.UNREPORTED_FAILURE_COST_RESERVE_USD,
        )

    def test_successful_remote_requires_reported_cost(self):
        with self.assertRaisesRegex(
            pv.FrozenDesignError, "MISSING_SUCCESSFUL_REMOTE_COST"
        ):
            pv.EvidenceBudget().after_remote(
                RemoteResult(
                    True,
                    "{}",
                    1.0,
                    "model",
                    attempt_count=1,
                    retry_count=0,
                )
            )

    def test_remote_retry_count_must_match_attempt_count(self):
        with self.assertRaisesRegex(
            pv.FrozenDesignError, "INVALID_REMOTE_ATTEMPT_COUNT"
        ):
            pv.EvidenceBudget().after_remote(
                RemoteResult(
                    True,
                    "{}",
                    1.0,
                    "model",
                    cost=0.0,
                    attempt_count=2,
                    retry_count=0,
                )
            )

    def test_provider_latency_is_required(self):
        with self.assertRaisesRegex(
            pv.FrozenDesignError, "INVALID_PROVIDER_LATENCY"
        ):
            pv.validate_provider_result(
                LocalResult(True, "{}", total_ms=None), "local"
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


class ProviderOutcomeTests(unittest.TestCase):
    def execute_synthetic(self, directory, remote_failure=None, local_failure=None):
        _, tasks, _ = pv.load_frozen_inputs(ROOT)
        config = runner._config(ROOT)
        outputs = {
            task["runtime_request"]["prompt"]: json.dumps(
                task["oracle"]["expected_json"],
                ensure_ascii=False,
                separators=(",", ":"),
            )
            for task in tasks
        }
        calls = {"local": 0, "remote": 0}

        def local_fake(prompt, provider_config):
            calls["local"] += 1
            if calls["local"] == local_failure:
                return LocalResult(False, total_ms=4, error="LOCAL_TIMEOUT")
            return LocalResult(
                True, outputs[prompt], 0, 0, 50, 100, 4, 80_000_000
            )

        def remote_fake(prompt, provider_config, api_key):
            calls["remote"] += 1
            if calls["remote"] == remote_failure:
                return RemoteResult(
                    False,
                    total_ms=5,
                    model=provider_config["model"],
                    error="OPENROUTER_RESPONSE_INVALID",
                    status_code=200,
                    attempt_count=1,
                    retry_count=0,
                )
            return RemoteResult(
                True,
                outputs[prompt],
                3,
                provider_config["model"],
                status_code=200,
                cost=0.000001,
                attempt_count=1,
                retry_count=0,
            )

        report = runner.execute_observations(
            tasks,
            config,
            "synthetic-1b-v1-provider-outcomes",
            pv.MODEL_SPEC,
            Path(directory),
            local_fake,
            remote_fake,
            runner._healthy_metrics,
            lambda iterations: 0,
            lambda provider_config: {
                "resident": True,
                "size_bytes": 815319791,
            },
            "synthetic-key",
        )
        return report, tasks, calls

    def test_remote_failure_is_scored_and_collection_continues(self):
        with tempfile.TemporaryDirectory() as directory:
            report, _, calls = self.execute_synthetic(directory, remote_failure=2)
            self.assertEqual(report["observation_count"], 120)
            self.assertEqual(report["runtime_correct_count"], 119)
            self.assertEqual(report["remote_provider_success_count"], 119)
            self.assertEqual(
                report["remote_provider_errors"],
                {"OPENROUTER_RESPONSE_INVALID": 1},
            )
            self.assertEqual(report["budget"]["unreported_remote_failure_count"], 1)
            self.assertEqual(
                report["budget"]["reserved_unreported_failure_cost_usd"],
                pv.UNREPORTED_FAILURE_COST_RESERVE_USD,
            )
            self.assertEqual(calls, {"local": 120, "remote": 120})
            rows = analyzer._read_jsonl(pv.output_paths(directory)["runs"])
            failed = rows[1]
            self.assertFalse(failed["runtime_correct"])
            self.assertFalse(failed["remote"]["success"])
            self.assertTrue(failed["local_oracle"]["correct"])
            self.assertEqual(failed["actual_reason"], "REMOTE_ERROR")
            self.assertFalse(pv.output_paths(directory)["failure"].exists())
            analysis = analyzer.build_analysis(directory, frozen_root=ROOT)
            self.assertEqual(
                analysis["overall"]["remote_provider_error_count"], 1
            )

    def test_local_failure_is_scored_and_collection_continues(self):
        with tempfile.TemporaryDirectory() as directory:
            report, _, calls = self.execute_synthetic(directory, local_failure=2)
            self.assertEqual(report["runtime_correct_count"], 120)
            self.assertEqual(report["local_provider_success_count"], 119)
            self.assertEqual(report["local_provider_errors"], {"LOCAL_TIMEOUT": 1})
            self.assertEqual(calls, {"local": 120, "remote": 120})

    def test_uncaught_provider_exception_writes_failure_manifest(self):
        _, tasks, _ = pv.load_frozen_inputs(ROOT)
        config = runner._config(ROOT)

        def remote_broken(prompt, provider_config, api_key):
            raise RuntimeError("synthetic transport escape")

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "synthetic transport escape"):
                runner.execute_observations(
                    tasks,
                    config,
                    "synthetic-1b-v1-instrument-failure",
                    pv.MODEL_SPEC,
                    Path(directory),
                    lambda prompt, provider_config: LocalResult(
                        True, "{}", 0, 0, 1, 1, 1, 1
                    ),
                    remote_broken,
                    runner._healthy_metrics,
                    lambda iterations: 0,
                    lambda provider_config: {
                        "resident": True,
                        "size_bytes": 815319791,
                    },
                    "synthetic-key",
                )
            paths = pv.output_paths(directory)
            manifest = json.loads(paths["failure"].read_text(encoding="utf-8"))
            self.assertEqual(
                manifest["schema_version"],
                "runtime_v0_3_shadow_json_1b_failure_v1",
            )
            self.assertEqual(manifest["status"], "INCOMPLETE")
            self.assertEqual(manifest["failure_code"], "RuntimeError")
            self.assertNotIn("synthetic transport escape", json.dumps(manifest))
            self.assertTrue(manifest["promotion_blocked"])
            self.assertEqual(manifest["task_id"], "m1b_flat_01")
            self.assertEqual(manifest["repetition"], 1)
            self.assertEqual(manifest["completed_row_count"], 0)
            self.assertTrue(Path(str(paths["runs"]) + ".partial").exists())
            self.assertFalse(pv._contains_text(manifest))
            with self.assertRaisesRegex(
                pv.StateError, "FAILURE_MANIFEST_PRESENT"
            ):
                analyzer.build_analysis(directory, frozen_root=ROOT)


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
        self.assertEqual(analyzer._counterfactual(rejected), (False, True, 10))

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
                    "router_decision": {"total_ms": 10},
                    "local": {"success": True, "error": None, "total_ms": 2, "cost": None, "attempt_count": 0},
                    "remote": {"success": True, "error": None, "total_ms": 8, "cost": 0.0, "attempt_count": 1},
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
