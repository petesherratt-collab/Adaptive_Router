import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from local import LocalResult
import analyze_prospective_contract_validation as analyzer
import prospective_contract_validation as pcv
import run_prospective_contract_validation as runner


class ProspectiveFixtureMixin:
    @classmethod
    def setUpClass(cls):
        suite, tasks, contracts = pcv.load_frozen_inputs()
        cls.suite = suite
        cls.tasks = tasks
        cls.contracts = contracts

    def task(self, task_id):
        return self.tasks[task_id]

    def contract(self, task_id):
        return self.contracts[task_id]


class FrozenDesignTests(ProspectiveFixtureMixin, unittest.TestCase):
    def test_frozen_hashes_and_inventory(self):
        self.assertEqual(len(self.tasks), 40)
        self.assertEqual(len(self.contracts), 40)
        self.assertEqual(list(self.tasks), [c["task_id"] for c in json.loads(Path(pcv.CONTRACTS_PATH).read_text())["contracts"]])
        self.assertEqual(list(self.tasks), [f"pcv1_a_schema_{i:02d}" for i in range(1, 11)] + [f"pcv1_b_format_{i:02d}" for i in range(1, 11)] + [f"pcv1_c_label_{i:02d}" for i in range(1, 11)] + [f"pcv1_d_exec_{i:02d}" for i in range(1, 11)])
        self.assertEqual(pcv.file_sha256(pcv.PLAN_PATH), pcv.PLAN_SHA256)
        self.assertEqual(pcv.file_sha256(pcv.SUITE_PATH), pcv.SUITE_SHA256)
        self.assertEqual(pcv.file_sha256(pcv.CONTRACTS_PATH), pcv.CONTRACTS_SHA256)

    def test_contract_document_rejects_forbidden_nested_name(self):
        document = json.loads(Path(pcv.CONTRACTS_PATH).read_text())
        document["contracts"][0]["extension"] = {"oracle_value": "leak"}
        with self.assertRaises(pcv.ContractSchemaError):
            pcv.validate_contract_document(document, self.tasks)


class ContractIsolationTests(ProspectiveFixtureMixin, unittest.TestCase):
    def test_structural_schema_accepts_wrong_values_but_oracle_rejects(self):
        task = self.task("pcv1_a_schema_01")
        contract = self.contract(task["task_id"])
        raw = '{"instrument":"wrong","pulse_count":999,"mode":"other"}'
        self.assertTrue(pcv.contract_validate(contract, raw).accepted)
        _, correct = pcv.oracle_correct(task, raw, contract)
        self.assertFalse(correct)

    def test_format_shape_accepts_wrong_content_but_oracle_rejects(self):
        task = self.task("pcv1_b_format_05")
        contract = self.contract(task["task_id"])
        raw = "```text\n+ unrelated\n+ replacement\n```"
        self.assertTrue(pcv.contract_validate(contract, raw).accepted)
        _, correct = pcv.oracle_correct(task, raw, contract)
        self.assertFalse(correct)

    def test_classification_accepts_wrong_permitted_label_but_oracle_rejects(self):
        task = self.task("pcv1_c_label_01")
        contract = self.contract(task["task_id"])
        self.assertTrue(pcv.contract_validate(contract, "negative").accepted)
        _, correct = pcv.oracle_correct(task, "negative", contract)
        self.assertFalse(correct)


class NormalizationTests(ProspectiveFixtureMixin, unittest.TestCase):
    def test_json_numbers_are_mathematical_and_types_are_strict(self):
        task = self.task("pcv1_a_schema_01")
        contract = self.contract(task["task_id"])
        for number in ("7", "7.0", "7e0"):
            raw = '{"instrument":"Helio-6","pulse_count":' + number + ',"mode":"quiet"}'
            self.assertTrue(pcv.contract_validate(contract, raw).accepted)
            self.assertTrue(pcv.oracle_correct(task, raw, contract)[1])
        wrong_string = '{"instrument":"Helio-6","pulse_count":"7","mode":"quiet"}'
        wrong_bool = '{"instrument":"Helio-6","pulse_count":true,"mode":"quiet"}'
        self.assertFalse(pcv.contract_validate(contract, wrong_string).accepted)
        self.assertFalse(pcv.contract_validate(contract, wrong_bool).accepted)

    def test_json_rejects_duplicate_and_nonfinite_values(self):
        contract = self.contract("pcv1_a_schema_01")
        self.assertFalse(pcv.contract_validate(contract, '{"instrument":"a","instrument":"b","pulse_count":7,"mode":"quiet"}').accepted)
        self.assertFalse(pcv.contract_validate(contract, '{"instrument":"a","pulse_count":1e999,"mode":"quiet"}').accepted)

    def test_complete_outer_fence_crlf_and_one_terminal_lf(self):
        contract = self.contract("pcv1_a_schema_01")
        raw = '```json\r\n{"instrument":"Helio-6","pulse_count":7,"mode":"quiet"}\r\n```\r\n'
        self.assertTrue(pcv.contract_validate(contract, raw).accepted)
        self.assertFalse(pcv.contract_validate(contract, "prose\n" + raw).accepted)

    def test_format_line_count_fence_and_terminal_newline_rules(self):
        contract = self.contract("pcv1_b_format_01")
        self.assertTrue(pcv.contract_validate(contract, "* x\r\n* y\r\n* z\r\n").accepted)
        self.assertFalse(pcv.contract_validate(contract, "* x\n* y\n* z\n\n").accepted)
        fenced = self.contract("pcv1_b_format_05")
        self.assertTrue(pcv.contract_validate(fenced, "```text\n+ x\n+ y\n```\n").accepted)
        self.assertFalse(pcv.contract_validate(fenced, "```text\n+ x\n+ y\n```\n\n").accepted)

    def test_classification_ascii_case_and_whitespace_are_frozen(self):
        contract = self.contract("pcv1_c_label_01")
        self.assertTrue(pcv.contract_validate(contract, "  PoSiTiVe\t\n").accepted)
        self.assertFalse(pcv.contract_validate(contract, "positive\nextra").accepted)
        self.assertFalse(pcv.contract_validate(contract, "positive!").accepted)


class DeterministicExecutorTests(ProspectiveFixtureMixin, unittest.TestCase):
    EXPECTED = {
        "pcv1_d_exec_01": "uartzq",
        "pcv1_d_exec_02": "lemarb",
        "pcv1_d_exec_03": "ln",
        "pcv1_d_exec_04": "cind7r",
        "pcv1_d_exec_05": "opal grove",
        "pcv1_d_exec_06": "mixEDcASE",
        "pcv1_d_exec_07": "fjordecho",
        "pcv1_d_exec_08": "7abclot",
        "pcv1_d_exec_09": "ravenn",
        "pcv1_d_exec_10": "amber violet",
    }

    def test_all_ten_operations_and_executor_alias(self):
        for task_id, expected in self.EXPECTED.items():
            result = pcv.contract_validate(self.contract(task_id), expected)
            self.assertTrue(result.accepted, task_id)
            self.assertEqual(pcv._operation(self.contract(task_id)["source_literal"], self.contract(task_id)["operation"]), expected)

    def test_does_not_call_d_a_validator(self):
        with patch("prospective_contract_validation.validators.validate", side_effect=AssertionError("not a contract input")):
            result = pcv.contract_validate(self.contract("pcv1_d_exec_01"), "uartzq")
        self.assertTrue(result.accepted)


class GateAndRowTests(ProspectiveFixtureMixin, unittest.TestCase):
    def base_record(self, **updates):
        record = {"success": True, "ttft_ms": 10.0, "tokens_per_second": 10.0, "raw_output": "wrong"}
        record.update(updates)
        return record

    def test_legacy_baseline_failure_order_and_not_applicable(self):
        task = self.task("pcv1_c_label_01")
        self.assertEqual(pcv.legacy_baseline_gate(self.base_record(success=False, ttft_ms=9001, tokens_per_second=1), task).reason, "GENERATION_FAILED")
        self.assertEqual(pcv.legacy_baseline_gate(self.base_record(ttft_ms=8000.01), task).reason, "TTFT_EXCEEDED")
        self.assertEqual(pcv.legacy_baseline_gate(self.base_record(tokens_per_second=1.499), task).reason, "GENERATION_TOO_SLOW")
        self.assertTrue(pcv.legacy_baseline_gate(self.base_record(), task).survived)

    def test_failed_result_row_has_task_success_and_all_false_decisions(self):
        task = self.task("pcv1_d_exec_01")
        result = LocalResult(False, total_ms=3.0, error="LOCAL_TIMEOUT")
        row = pcv.make_result_row(task | {"_rep": 1}, self.contract(task["task_id"]), None, result, "gemma3:270m", "gemma3:270m", pcv.public_identity("gemma3:270m"), "revision", {"resident": False, "size_bytes": None})
        self.assertFalse(row["success"])
        self.assertFalse(row["task_success"])
        self.assertFalse(row["oracle_correct"])
        self.assertFalse(row["executor_accept"])
        self.assertFalse(row["contract_accept"])
        self.assertEqual(row["error"]["kind"], "LOCAL_TIMEOUT")
        self.assertIsInstance(row["error"]["message"], str)


def synthetic_row(task_id, model, baseline=True, cf=True, correct=True, contract=True, executor=True, rep=1):
    task = TEST_TASKS[task_id]
    return {
        "task_id": task_id,
        "rep": rep,
        "requested_model": model,
        "returned_model": model,
        "model_identity_source_sha256": dict(pcv.MODEL_IDENTITY_SOURCE_SHA256),
        "cohort": task["cohort"],
        "contract_type": task["contract_type"],
        "task_success": True,
        "oracle_correct": correct,
        "baseline_gate_survived": baseline,
        "counterfactual_gate_survived": cf,
        "contract_accept": contract,
        "executor_accept": executor,
    }


TEST_TASKS = {}


class MetricsAndBootstrapTests(ProspectiveFixtureMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        global TEST_TASKS
        TEST_TASKS = cls.tasks

    def test_transition_metrics_and_hard_invariants(self):
        task_id = "pcv1_c_label_01"
        rows = [synthetic_row(task_id, "gemma3:270m", baseline=True, cf=True, correct=False, contract=True)]
        metrics = pcv.metrics_for_rows(rows, "test")
        self.assertEqual(metrics["baseline_false_accept_count"], 1)
        self.assertEqual(metrics["false_accepts_remaining_count"], 1)
        self.assertEqual(metrics["false_accepts_caught_count"], 0)
        self.assertEqual(sum(metrics["transition_counts"].values()), 1)

    def test_bootstrap_sampler_and_type7_are_reproducible(self):
        rows = []
        for task_id in list(self.tasks)[:20]:
            rows.append(synthetic_row(task_id, "gemma3:270m", baseline=True, cf=False, correct=False, contract=False, rep=1))
            rows.append(synthetic_row(task_id, "gemma3:1b", baseline=True, cf=False, correct=False, contract=False, rep=1))
            rows.append(synthetic_row(task_id, "gemma3:4b", baseline=True, cf=False, correct=False, contract=False, rep=1))
        first = pcv.bootstrap_primary(rows)
        second = pcv.bootstrap_primary(rows)
        self.assertEqual(first, second)
        self.assertEqual(first["draw_count"], 10000)
        self.assertEqual(first["undefined_draw_count"], 0)
        self.assertEqual(first["interval_95"], {"lower": 1.0, "upper": 1.0})
        digest = hashlib.sha256(b"prospective_contract_validation_v1|20260831|0|0").digest()
        self.assertEqual(int.from_bytes(digest[:8], "big") % 20, 4)

    def test_analyzer_synthetic_fixture_has_all_scope_totals(self):
        rows = []
        for model in pcv.MODEL_ORDER:
            for task_id in self.tasks:
                for rep in range(1, 6):
                    rows.append(synthetic_row(task_id, model, rep=rep))
        report = pcv.analyze_rows(rows, self.tasks, self.contracts, "revision")
        self.assertEqual(report["primary"]["overall"]["observation_count"], 300)
        self.assertEqual(report["label_conformance"]["overall"]["observation_count"], 150)
        self.assertEqual(report["deterministic_executor"]["overall"]["observation_count"], 150)
        self.assertEqual(report["primary"]["bootstrap"]["undefined_draw_count"], 10000)


class SafetyAndAuthenticationTests(ProspectiveFixtureMixin, unittest.TestCase):
    def test_identity_authentication_accepts_nested_metadata_and_rejects_mismatch(self):
        spec = pcv.public_identity("gemma3:1b")
        actual = {"name": spec["name"], "digest": spec["digest"], "size": spec["package_size_bytes"], "details": {k: spec[k] for k in ("parameter_size", "quantization_level", "format", "family")}}
        self.assertEqual(pcv.verify_model_identity(actual, "gemma3:1b"), spec)
        actual["details"]["family"] = "diagnostic-difference"
        self.assertEqual(pcv.verify_model_identity(actual, "gemma3:1b")["family"], "diagnostic-difference")
        actual["digest"] = "bad"
        with self.assertRaises(pcv.FrozenDesignError):
            pcv.verify_model_identity(actual, "gemma3:1b")

    def test_model_identity_source_hashes_are_authenticated(self):
        self.assertEqual(pcv.authenticate_model_identity_sources(), pcv.MODEL_IDENTITY_SOURCE_SHA256)

    def test_each_generation_response_model_tag_is_checked(self):
        class Response:
            def raise_for_status(self):
                return None

            def iter_lines(self):
                return [
                    json.dumps({"model": "gemma3:270m", "response": "x"}).encode(),
                    json.dumps({"model": "gemma3:1b", "response": "y", "done": True}).encode(),
                ]

        class Session:
            def post(self, *args, **kwargs):
                return Response()

        result, returned = runner.generate_one("prompt", "gemma3:270m", "http://unused", session=Session())
        self.assertFalse(result.success)
        self.assertEqual(result.error, "RETURNED_MODEL_IDENTITY_MISMATCH")
        self.assertEqual(returned, "gemma3:1b")

    def test_atomic_write_refuses_overwrite_and_partial(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.jsonl"
            pcv.atomic_write_text(path, "complete\n")
            self.assertEqual(path.read_text(), "complete\n")
            with self.assertRaises(FileExistsError):
                pcv.atomic_write_text(path, "changed\n")
            other = Path(directory) / "other.jsonl"
            Path(str(other) + ".partial").write_text("interrupted\n")
            with self.assertRaises(FileExistsError):
                pcv.atomic_write_text(other, "new\n")

    def test_interrupted_write_leaves_quarantined_partial_and_blocks_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "interrupted.jsonl"
            with patch.object(pcv.os, "fsync", side_effect=OSError("simulated interruption")):
                with self.assertRaises(OSError):
                    pcv.atomic_write_text(path, "partial\n")
            self.assertFalse(path.exists())
            self.assertTrue(Path(str(path) + ".partial").exists())
            with self.assertRaises(FileExistsError):
                pcv.atomic_write_text(path, "resume\n")

    def test_exact_row_count_and_truncated_evidence_are_rejected(self):
        with self.assertRaises(ValueError):
            pcv.validate_result_rows([], self.tasks, "gemma3:270m")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "truncated.jsonl"
            path.write_text("{}\n")
            with self.assertRaises(ValueError):
                analyzer.load_rows(path, "gemma3:270m", self.tasks)


class DryRunTests(unittest.TestCase):
    def test_v1_dry_run_is_blocked_by_its_own_sealed_evidence(self):
        """The frozen V1 preflight is unsatisfiable after sealing its 270M run."""
        with patch.object(
            runner,
            "generate_one",
            side_effect=AssertionError("generation called"),
        ) as generation:
            with self.assertRaises(FileExistsError) as raised:
                runner.dry_run()

        message = str(raised.exception)
        self.assertIn(
            "benchmark_prospective_contract_v1_gemma3_270m.jsonl",
            message,
        )
        self.assertIn(
            "benchmark_prospective_contract_v1_gemma3_270m_summary.json",
            message,
        )
        generation.assert_not_called()
