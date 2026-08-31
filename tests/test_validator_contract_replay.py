import copy
import csv
import io
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import replay_validator_contracts as replay
from validator_contracts import (
    contract_validate,
    validate_contract_document,
)


ROOT = Path(__file__).resolve().parents[1]


def contract(task_id):
    document = json.loads(
        (ROOT / "validator_contracts_oos_v1.json").read_text(encoding="utf-8")
    )
    return next(item for item in document["contracts"] if item["task_id"] == task_id)


def synthetic_record(
    task_id="task",
    task_class="classification",
    family="sentiment",
    raw_output="Positive",
    oracle_correct=False,
    **answer_fields,
):
    record = dict(
        task_id=task_id,
        rep=1,
        task_class=task_class,
        capability_family=family,
        raw_output=raw_output,
        success=True,
        ttft_ms=10.0,
        tokens_per_second=20.0,
        oracle_correct=oracle_correct,
        expected="unused",
        normalized_output="unused",
        validator={"status": "PASS"},
        validator_status="PASS",
    )
    record.update(answer_fields)
    return SimpleNamespace(**record)


def synthetic_task(task_id="task", task_class="classification", family="sentiment"):
    return {
        "task_id": task_id,
        "task_class": task_class,
        "capability_family": family,
        "prompt": "Classify this item.",
    }


class AuthenticationAndLoadingTests(unittest.TestCase):
    def test_hashes_and_contract_task_inventory_are_authenticated(self):
        self.assertEqual(
            replay.authenticate_plan(),
            "ac7cb2ee4b47ee07c4a0a63b122d56ce47d49dffb88ff82e19fd9a32d638edf0",
        )
        self.assertEqual(replay.file_sha256(replay.CONTRACT_PATH), replay.CONTRACT_SHA256)
        inventory = replay.load_benchmark_inventory()
        contracts = replay.load_contracts(task_inventory=inventory)
        self.assertEqual(set(inventory), set(contracts))
        self.assertEqual(len(contracts), 40)

    def test_frozen_evidence_has_exact_200_keys_per_model(self):
        inventory = replay.load_benchmark_inventory()
        key_sets = []
        for model in replay.EVIDENCE_SHA256:
            records = replay.load_evidence(model, inventory)
            keys = {(record.task_id, record.rep) for record in records}
            self.assertEqual(len(records), 200)
            self.assertEqual(len(keys), 200)
            key_sets.append(keys)
        self.assertEqual(key_sets[0], key_sets[1])
        self.assertEqual(key_sets[1], key_sets[2])

    def test_evidence_removal_addition_and_duplication_fail_closed(self):
        inventory = replay.load_benchmark_inventory()
        source = replay._read_evidence_lines(replay.EVIDENCE_PATHS["gemma3:270m"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evidence.jsonl"
            variants = [source[:-1], source + [copy.deepcopy(source[0])]]
            duplicate = copy.deepcopy(source)
            duplicate[1]["task_id"] = duplicate[0]["task_id"]
            duplicate[1]["rep"] = duplicate[0]["rep"]
            variants.append(duplicate)
            for records in variants:
                path.write_text(
                    "".join(json.dumps(record) + "\n" for record in records),
                    encoding="utf-8",
                )
                with patch.object(
                    replay,
                    "file_sha256",
                    return_value=replay.EVIDENCE_SHA256["gemma3:270m"],
                ):
                    with self.assertRaises(ValueError):
                        replay.load_evidence("gemma3:270m", inventory, path)


class BoundaryAndGateTests(unittest.TestCase):
    def test_signature_is_exactly_two_arguments(self):
        import inspect

        self.assertEqual(
            tuple(inspect.signature(contract_validate).parameters),
            ("contract", "raw_output"),
        )

    def test_different_answer_fields_do_not_reach_instrumented_validator(self):
        task = synthetic_task()
        contract = {
            "task_id": "task",
            "task_class": "classification",
            "capability_family": "sentiment",
            "contract_type": "classification",
            "permitted_labels": ["Positive", "Negative"],
        }
        first = synthetic_record(
            expected="Negative",
            normalized_output="Negative",
            validator={"status": "FAIL", "detail": "x"},
            validator_status="FAIL",
            oracle_correct=False,
        )
        second = synthetic_record(
            expected="Positive",
            normalized_output="Positive",
            validator={"status": "PASS"},
            validator_status="PASS",
            oracle_correct=True,
        )
        calls = []

        def instrumented(contract_arg, raw_output):
            calls.append((copy.deepcopy(contract_arg), raw_output))
            self.assertEqual(raw_output, "Positive")
            self.assertNotIn("expected", json.dumps(contract_arg))
            self.assertNotIn("oracle_correct", json.dumps(contract_arg))
            self.assertNotIn("normalized_output", json.dumps(contract_arg))
            self.assertNotIn("validator", json.dumps(contract_arg))
            return contract_validate(contract_arg, raw_output)

        with patch.object(replay, "contract_validate", instrumented):
            rows = replay.replay_records(
                {"synthetic": [first, second]},
                {"task": contract},
                {"task": task},
            )
        self.assertEqual(len(calls), 2)
        self.assertEqual(
            [(row.contract_accepted, row.contract_reason) for row in rows],
            [(True, "ACCEPTED"), (True, "ACCEPTED")],
        )
        self.assertEqual([row.oracle_correct for row in rows], [False, True])

    def test_recorded_validator_fields_are_not_baseline_gate_inputs(self):
        task = synthetic_task()
        record = synthetic_record()
        first = replay.baseline_gate(record, task)
        record.validator = {"status": "FAIL"}
        record.validator_status = "FAIL"
        second = replay.baseline_gate(record, task)
        self.assertEqual(first, second)
        self.assertTrue(second[0])

    def test_baseline_false_accept_regression_totals_are_98_100_42(self):
        inventory = replay.load_benchmark_inventory()
        expected = {"gemma3:270m": 98, "gemma3:1b": 100, "gemma3:4b": 42}
        for model, expected_count in expected.items():
            records = replay.load_evidence(model, inventory)
            observed = sum(
                (not record.oracle_correct)
                and replay.baseline_gate(record, inventory[record.task_id])[0]
                for record in records
            )
            self.assertEqual(observed, expected_count)

    def test_ttft_rejection_is_not_a_contract_catch(self):
        row = replay.ReplayObservation(
            "synthetic", "task", "sentiment", "classification", False,
            "LABEL_NOT_PERMITTED", False, "TTFT_EXCEEDED", False, False, False,
        )
        metrics = replay._metrics([row])
        self.assertEqual(metrics["false_accept_count_before_replay"], 0)
        self.assertEqual(metrics["false_accept_caught_count"], 0)
        self.assertEqual(metrics["contract_reject_count"], 1)

    def test_legacy_rejected_wrong_output_is_newly_admitted(self):
        task = synthetic_task()
        record = synthetic_record(oracle_correct=False)
        contract = {
            "task_id": "task",
            "task_class": "classification",
            "capability_family": "sentiment",
            "contract_type": "classification",
            "permitted_labels": ["Positive", "Negative"],
        }
        failing = SimpleNamespace(status="FAIL")
        with patch.object(replay.validators, "validate", return_value=failing):
            rows = replay.replay_records(
                {"synthetic": [record]}, {"task": contract}, {"task": task}
            )
        metrics = replay._metrics(rows)
        self.assertEqual(metrics["newly_admitted_incorrect_count"], 1)
        self.assertEqual(metrics["false_accept_remaining_count"], 0)
        self.assertEqual(metrics["counterfactual_false_accept_count"], 1)


class MetricsAndGroupingTests(unittest.TestCase):
    def test_all_transition_cells_and_both_conservation_identities(self):
        rows = []
        for baseline in (True, False):
            for counterfactual in (True, False):
                for oracle in (True, False):
                    rows.append(replay.ReplayObservation(
                        "synthetic", f"task-{len(rows)}", "sentiment", "classification",
                        counterfactual, "ACCEPTED" if counterfactual else "LABEL_NOT_PERMITTED",
                        baseline, "SURVIVED" if baseline else "VALIDATOR_FAILED", True,
                        counterfactual, oracle,
                    ))
        metrics = replay._metrics(rows)
        self.assertEqual(set(metrics["paired_transition_counts"]), set(replay.TRANSITION_KEYS))
        self.assertEqual(metrics["transition_count_sum"], 8)
        self.assertTrue(metrics["identity_false_accept_before"])
        self.assertTrue(metrics["identity_counterfactual_false_accept"])

    def test_grouped_report_is_complete_per_model_and_csv_uses_model_names(self):
        report = replay.run(write=False)
        metric_keys = set(report["models"]["gemma3:4b"])
        for model in replay.EVIDENCE_SHA256:
            dimensions = report["grouped_by_model"][model]
            for dimension in ("capability_family", "task_id", "contract_type"):
                groups = dimensions[dimension]
                self.assertEqual(sum(group["observation_count"] for group in groups.values()), 200)
                for group in groups.values():
                    self.assertEqual(set(group), metric_keys)
                    self.assertEqual(group["transition_count_sum"], group["observation_count"])
                    self.assertTrue(group["identity_false_accept_before"])
                    self.assertTrue(group["identity_counterfactual_false_accept"])
        rows = list(csv.DictReader(io.StringIO(replay._csv_text(report))))
        for model in replay.EVIDENCE_SHA256:
            for scope in ("capability_family_by_model", "task_id_by_model", "contract_type_by_model"):
                self.assertTrue(any(row["model"] == model and row["scope"] == scope for row in rows))


class OutputModeTests(unittest.TestCase):
    def test_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            json_path = Path(directory) / "result.json"
            csv_path = Path(directory) / "result.csv"
            replay.run(write=False, json_path=json_path, csv_path=csv_path)
            self.assertFalse(json_path.exists())
            self.assertFalse(csv_path.exists())

    def test_existing_target_fails_before_loaders(self):
        for existing in ("result.json", "result.csv"):
            with self.subTest(existing=existing), tempfile.TemporaryDirectory() as directory:
                json_path = Path(directory) / "result.json"
                csv_path = Path(directory) / "result.csv"
                (Path(directory) / existing).write_text("existing", encoding="utf-8")
                with patch.object(replay, "load_evidence") as loader, patch.object(replay, "authenticate_plan") as auth:
                    with self.assertRaises(FileExistsError):
                        replay.run(write=True, json_path=json_path, csv_path=csv_path)
                loader.assert_not_called()
                auth.assert_not_called()

    def test_write_no_overwrite_uses_synthetic_text_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.txt"
            path.write_text("original", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                replay._write_no_overwrite(path, "replacement")
            self.assertEqual(path.read_text(encoding="utf-8"), "original")
            new_path = Path(directory) / "new.txt"
            replay._write_no_overwrite(new_path, "synthetic")
            self.assertEqual(new_path.read_text(encoding="utf-8"), "synthetic")


if __name__ == "__main__":
    unittest.main()
