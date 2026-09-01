import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from local import LocalResult
import prospective_contract_validation_v2 as pcv
import run_prospective_contract_validation_v2 as runner


class V2Fixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.suite, cls.tasks, cls.contracts = pcv.load_frozen_inputs()
        cls.revision = "synthetic-v2-revision"

    def task(self, task_id):
        return self.tasks[task_id]

    def contract(self, task_id):
        return self.contracts[task_id]


class DesignTests(V2Fixture):
    def test_frozen_inventory_and_hashes(self):
        self.assertEqual(len(self.tasks), 40)
        self.assertEqual(len(self.contracts), 40)
        self.assertEqual(list(self.tasks), [c["task_id"] for c in json.loads(Path(pcv.CONTRACTS_PATH).read_text())["contracts"]])
        self.assertEqual(pcv.file_sha256(pcv.PLAN_PATH), pcv.PLAN_SHA256)
        self.assertEqual(pcv.file_sha256(pcv.SUITE_PATH), pcv.SUITE_SHA256)
        self.assertEqual(pcv.file_sha256(pcv.CONTRACTS_PATH), pcv.CONTRACTS_SHA256)

    def test_contract_document_rejects_oracle_field(self):
        document = json.loads(Path(pcv.CONTRACTS_PATH).read_text())
        document["contracts"][0]["oracle"] = "leak"
        with self.assertRaises(pcv.ContractSchemaError):
            pcv.validate_contract_document(document, self.tasks)


class IsolationTests(V2Fixture):
    def test_a_shape_accepts_wrong_values_oracle_rejects(self):
        task = self.task("pcv2_a_schema_01")
        raw = '{"glider_code":"wrong","flight_minutes":99,"cleared":false}'
        self.assertTrue(pcv.contract_validate(self.contract(task["task_id"]), raw).accepted)
        self.assertFalse(pcv.oracle_correct(task, raw, self.contract(task["task_id"]))[1])

    def test_b_shape_accepts_wrong_content_oracle_rejects(self):
        task = self.task("pcv2_b_format_09")
        raw = "```list\n- unrelated\n- replacement\n- substitute\n```"
        self.assertTrue(pcv.contract_validate(self.contract(task["task_id"]), raw).accepted)
        self.assertFalse(pcv.oracle_correct(task, raw, self.contract(task["task_id"]))[1])

    def test_c_wrong_permitted_label_is_accepted_but_oracle_incorrect(self):
        task = self.task("pcv2_c_label_01")
        contract = self.contract(task["task_id"])
        self.assertTrue(pcv.contract_validate(contract, "negative").accepted)
        self.assertFalse(pcv.oracle_correct(task, "negative", contract)[1])


class NormalizationTests(V2Fixture):
    def test_json_numbers_and_boolean_types(self):
        task = self.task("pcv2_a_schema_01")
        contract = self.contract(task["task_id"])
        for number in ("7", "7.0", "7e0"):
            raw = '{"glider_code":"Kestrel-8","flight_minutes":' + number + ',"cleared":true}'
            self.assertTrue(pcv.contract_validate(contract, raw).accepted)
        self.assertFalse(pcv.contract_validate(contract, '{"glider_code":"Kestrel-8","flight_minutes":"7","cleared":true}').accepted)
        self.assertFalse(pcv.contract_validate(contract, '{"glider_code":"Kestrel-8","flight_minutes":true,"cleared":true}').accepted)
        self.assertTrue(pcv.oracle_correct(task, '{"glider_code":"Kestrel-8","flight_minutes":7e0,"cleared":true}', contract)[1] is False)

    def test_duplicate_nonfinite_and_fence_fail(self):
        contract = self.contract("pcv2_a_schema_01")
        self.assertFalse(pcv.contract_validate(contract, '{"glider_code":"a","glider_code":"b","flight_minutes":1,"cleared":true}').accepted)
        self.assertFalse(pcv.contract_validate(contract, '{"glider_code":"a","flight_minutes":1e999,"cleared":true}').accepted)
        good = '```json\n{"glider_code":"Kestrel-8","flight_minutes":14,"cleared":true}\n```\n'
        self.assertTrue(pcv.contract_validate(contract, good).accepted)
        self.assertFalse(pcv.contract_validate(contract, "prose\n" + good).accepted)

    def test_line_endings_extra_lines_fences_and_separators(self):
        bullet = self.contract("pcv2_b_format_01")
        self.assertTrue(pcv.contract_validate(bullet, "- one\r\n- two\r\n- three\r\n").accepted)
        self.assertFalse(pcv.contract_validate(bullet, "- one\n- two\n- three\n\n").accepted)
        self.assertFalse(pcv.contract_validate(bullet, "```text\n- one\n- two\n- three\n```").accepted)
        label = self.contract("pcv2_b_format_03")
        self.assertTrue(pcv.contract_validate(label, "a | b\nb | c\nc | d").accepted)
        self.assertFalse(pcv.contract_validate(label, "a | b | c\nb | c\nc | d").accepted)

    def test_classification_case_whitespace_and_extra_lines(self):
        contract = self.contract("pcv2_c_label_01")
        self.assertTrue(pcv.contract_validate(contract, "  PoSiTiVe\t\n").accepted)
        self.assertFalse(pcv.contract_validate(contract, "positive\nextra").accepted)
        self.assertFalse(pcv.contract_validate(contract, "positive!").accepted)


class ExecutorAndBaselineTests(V2Fixture):
    EXPECTED = {
        "pcv2_d_exec_01":"anternl", "pcv2_d_exec_02":"resapphi", "pcv2_d_exec_03":"sq", "pcv2_d_exec_04":"v7lv7t", "pcv2_d_exec_05":"cinder quay", "pcv2_d_exec_06":"rILL7zONE", "pcv2_d_exec_07":"northstar5", "pcv2_d_exec_08":"4Aab", "pcv2_d_exec_09":"plumm", "pcv2_d_exec_10":"alpha zeta",
    }

    def test_all_d_operations(self):
        for task_id, expected in self.EXPECTED.items():
            self.assertTrue(pcv.execute_deterministic(self.contract(task_id), expected).accepted)
            self.assertEqual(self.task(task_id)["expected"], expected)

    def test_legacy_not_applicable_and_failure_order(self):
        task = self.task("pcv2_c_label_01")
        base = {"success":True,"ttft_ms":10,"tokens_per_second":10,"raw_output":"positive"}
        self.assertTrue(pcv.legacy_baseline_gate(base, task).survived)
        self.assertEqual(pcv.legacy_baseline_gate({**base,"success":False,"ttft_ms":9001,"tokens_per_second":1}, task).reason, "GENERATION_FAILED")
        self.assertEqual(pcv.legacy_baseline_gate({**base,"ttft_ms":8000.1}, task).reason, "TTFT_EXCEEDED")
        self.assertEqual(pcv.legacy_baseline_gate({**base,"tokens_per_second":1.4}, task).reason, "GENERATION_TOO_SLOW")
        self.assertTrue(pcv.legacy_baseline_gate({**base,"raw_output":"positive\nextra"}, task).survived)
        supported_task = self.task("pcv2_a_schema_01")
        self.assertEqual(
            pcv.legacy_baseline_gate(
                {**base, "raw_output":"not-json"}, supported_task
            ).reason,
            "VALIDATOR_FAILED",
        )


def synthetic_rows(tasks, model, revision, prior=None):
    rows=[]
    for task in tasks.values():
        for rep in range(1, 6):
            rows.append({"schema_version":pcv.SCHEMA_VERSION,"suite_id":pcv.SUITE_ID,"plan_sha256":pcv.PLAN_SHA256,"benchmark_sha256":pcv.SUITE_SHA256,"contracts_sha256":pcv.CONTRACTS_SHA256,"implementation_revision":revision,"requested_model":model,"returned_model":model,"model_identity":pcv.public_identity(model),"prior_stratum_sha256":dict(prior or {}),"task_id":task["task_id"],"rep":rep,"task_class":task["task_class"],"cohort":task["cohort"],"contract_type":task["contract_type"],"raw_output":"synthetic","normalized_output":"synthetic","oracle_correct":True,"executor_accept":True,"contract_accept":True,"baseline_gate_survived":True,"counterfactual_gate_survived":True,"success":True,"task_success":True,"ttft_ms":1.0,"total_ms":2.0,"tokens_per_second":10.0,"model_residency":{"resident":True},"error":None})
    return rows


def write_synthetic_stratum(root, model, tasks, revision, prior=None):
    paths=pcv.v2_paths(root); rows=synthetic_rows(tasks,model,revision,prior)
    pcv.atomic_write_text(paths["evidence"][model], "".join(json.dumps(row,separators=(",", ":"))+"\n" for row in rows))
    summary={"schema_version":pcv.SCHEMA_VERSION,"suite_id":pcv.SUITE_ID,"model":model,"model_identity":pcv.public_identity(model),"implementation_revision":revision,"plan_sha256":pcv.PLAN_SHA256,"benchmark_sha256":pcv.SUITE_SHA256,"contracts_sha256":pcv.CONTRACTS_SHA256,"observation_count":200,"task_success_count":200,"oracle_correct_count":200,"prior_stratum_sha256":dict(prior or {}),"evidence_sha256":pcv.file_sha256(paths["evidence"][model])}
    summary["summary_payload_sha256"]=pcv._summary_payload_hash(summary)
    pcv.atomic_write_json(paths["summaries"][model],summary)


class StateMachineTests(V2Fixture):
    def test_empty_only_allows_270m(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            self.assertEqual(pcv.detect_state(root), "EMPTY")
            self.assertEqual(pcv.preflight_stratum("gemma3:270m",self.tasks,root,self.revision)["state"], "EMPTY")
            for model in ("gemma3:1b","gemma3:4b"):
                with self.assertRaises(pcv.StateMachineError): pcv.preflight_stratum(model,self.tasks,root,self.revision)

    def test_completed_270_allows_1b_but_not_rerun_or_4b(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); write_synthetic_stratum(root,"gemma3:270m",self.tasks,self.revision)
            self.assertEqual(pcv.preflight_stratum("gemma3:1b",self.tasks,root,self.revision)["state"],"270M_COMPLETE")
            with self.assertRaises(pcv.StateMachineError): pcv.preflight_stratum("gemma3:270m",self.tasks,root,self.revision)
            with self.assertRaises(pcv.StateMachineError): pcv.preflight_stratum("gemma3:4b",self.tasks,root,self.revision)

    def test_malformed_truncated_and_forged_prior_reject(self):
        for mode in ("malformed", "truncated", "forged"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root=Path(directory); paths=pcv.v2_paths(root)
                content="not-json\n" if mode=="malformed" else "{}\n" if mode=="truncated" else json.dumps({"task_id":"fake"})+"\n"
                pcv.atomic_write_text(paths["evidence"]["gemma3:270m"],content)
                summary={"schema_version":pcv.SCHEMA_VERSION,"suite_id":pcv.SUITE_ID,"model":"gemma3:270m","implementation_revision":self.revision,"plan_sha256":pcv.PLAN_SHA256,"benchmark_sha256":pcv.SUITE_SHA256,"contracts_sha256":pcv.CONTRACTS_SHA256,"observation_count":200,"prior_stratum_sha256":{},"evidence_sha256":pcv.file_sha256(paths["evidence"]["gemma3:270m"]) }
                summary["summary_payload_sha256"]=pcv._summary_payload_hash(summary); pcv.atomic_write_json(paths["summaries"]["gemma3:270m"],summary)
                with self.assertRaises(pcv.FrozenDesignError): pcv.preflight_stratum("gemma3:1b",self.tasks,root,self.revision)

    def test_unexpected_future_output_and_partial_reject(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); write_synthetic_stratum(root,"gemma3:270m",self.tasks,self.revision)
            paths=pcv.v2_paths(root); pcv.atomic_write_text(paths["evidence"]["gemma3:4b"],"partial")
            with self.assertRaises(pcv.StateMachineError): pcv.preflight_stratum("gemma3:1b",self.tasks,root,self.revision)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); paths=pcv.v2_paths(root); Path(str(paths["evidence"]["gemma3:270m"])+".partial").write_text("x")
            with self.assertRaises(pcv.StateMachineError): pcv.preflight_stratum("gemma3:270m",self.tasks,root,self.revision)

    def test_270_plus_1b_allows_4b_and_270_only_rejects_4b(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); write_synthetic_stratum(root,"gemma3:270m",self.tasks,self.revision)
            prior=pcv.preflight_stratum("gemma3:1b",self.tasks,root,self.revision)["prior_stratum_sha256"]
            write_synthetic_stratum(root,"gemma3:1b",self.tasks,self.revision,prior)
            self.assertEqual(pcv.preflight_stratum("gemma3:4b",self.tasks,root,self.revision)["state"],"1B_COMPLETE")
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); write_synthetic_stratum(root,"gemma3:270m",self.tasks,self.revision)
            with self.assertRaises(pcv.StateMachineError): pcv.preflight_stratum("gemma3:4b",self.tasks,root,self.revision)

    def test_all_three_analysis_and_fewer_or_existing_reject(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); write_synthetic_stratum(root,"gemma3:270m",self.tasks,self.revision)
            prior=pcv.preflight_stratum("gemma3:1b",self.tasks,root,self.revision)["prior_stratum_sha256"]; write_synthetic_stratum(root,"gemma3:1b",self.tasks,self.revision,prior)
            prior=pcv.preflight_stratum("gemma3:4b",self.tasks,root,self.revision)["prior_stratum_sha256"]; write_synthetic_stratum(root,"gemma3:4b",self.tasks,self.revision,prior)
            self.assertEqual(len(pcv.preflight_analysis(self.tasks,root,self.revision)["rows"]),600)
            with self.assertRaises(pcv.StateMachineError): pcv.preflight_stratum("gemma3:4b",self.tasks,root,self.revision)
            paths=pcv.v2_paths(root); pcv.atomic_write_json(paths["analysis_json"],{"synthetic":True})
            with self.assertRaises(pcv.StateMachineError): pcv.preflight_analysis(self.tasks,root,self.revision)

    def test_changed_prior_and_preflight_nonmutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); write_synthetic_stratum(root,"gemma3:270m",self.tasks,self.revision); paths=pcv.v2_paths(root)
            before=pcv.file_sha256(paths["evidence"]["gemma3:270m"]); prior=pcv.preflight_stratum("gemma3:1b",self.tasks,root,self.revision)["prior_stratum_sha256"]
            self.assertEqual(before,prior["gemma3:270m"]["evidence"])
            self.assertEqual(before,pcv.file_sha256(paths["evidence"]["gemma3:270m"]))
            with paths["evidence"]["gemma3:270m"].open("a") as handle: handle.write("\n")
            with self.assertRaises(pcv.FrozenDesignError): pcv.preflight_stratum("gemma3:1b",self.tasks,root,self.revision)

    def test_v1_named_files_do_not_affect_v2_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); (root/"benchmark_prospective_contract_v1_gemma3_270m.jsonl").write_text("sealed")
            (root/"benchmark_prospective_contract_v1_gemma3_270m_summary.json").write_text("sealed")
            self.assertEqual(pcv.detect_state(root),"EMPTY")


class MetricsTests(V2Fixture):
    def test_metrics_bootstrap_and_analyzer_totals(self):
        rows=[]
        for model in pcv.MODEL_ORDER: rows.extend(synthetic_rows(self.tasks,model,self.revision))
        report=pcv.analyze_rows(rows,self.tasks,self.contracts,self.revision)
        self.assertEqual(report["primary"]["overall"]["observation_count"],300)
        self.assertEqual(report["label_conformance"]["overall"]["observation_count"],150)
        self.assertEqual(report["deterministic_executor"]["overall"]["observation_count"],150)
        self.assertEqual(report["primary"]["bootstrap"]["undefined_draw_count"],10000)
        digest=hashlib.sha256(b"prospective_contract_validation_v2|20260901|0|0").digest()
        self.assertEqual(int.from_bytes(digest[:8],"big")%20, 2)


class SafetyAndDryRunTests(V2Fixture):
    def test_identity_family_is_diagnostic_and_other_fields_fail(self):
        actual=pcv.public_identity("gemma3:1b"); actual["family"]="diagnostic"
        self.assertEqual(pcv.verify_model_identity(actual,"gemma3:1b")["family"],"diagnostic")
        actual["digest"]="wrong"
        with self.assertRaises(pcv.FrozenDesignError): pcv.verify_model_identity(actual,"gemma3:1b")

    def test_atomic_write_and_interrupted_partial(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"output.jsonl"; pcv.atomic_write_text(path,"done\n")
            with self.assertRaises(FileExistsError): pcv.atomic_write_text(path,"again\n")
            other=Path(directory)/"interrupted.jsonl"
            with patch.object(pcv.os,"fsync",side_effect=OSError("interrupt")):
                with self.assertRaises(OSError): pcv.atomic_write_text(other,"partial\n")
            self.assertFalse(other.exists()); self.assertTrue(Path(str(other)+".partial").exists())
            with self.assertRaises(FileExistsError): pcv.atomic_write_text(other,"resume\n")

    def test_dry_run_has_no_generation_or_repo_outputs(self):
        with patch.object(runner,"generate_one",side_effect=AssertionError("generation called")):
            result=runner.dry_run()
        self.assertEqual(result["status"],"PASS"); self.assertEqual(result["model_generation_requests"],0); self.assertEqual(result["canonical_outputs_created"],0)
