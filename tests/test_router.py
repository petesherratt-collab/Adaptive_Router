import json
from copy import deepcopy
import tempfile
import unittest
from pathlib import Path
from local import LocalResult
from remote import RemoteResult
from router import Router, classify

CONFIG = {"local":{"model":"x"}, "remote":{"model":"y"},
 "routing":{"minimum_available_ram_mb":2500,"active_swap_out_pages_threshold":0,"maximum_ttft_ms":8000,"minimum_generation_rate":1.5,"summarise_max_input_chars":12000},
 "shadow":{"enabled":False,"sample_rate":.05,"salt":"s"}, "probe":{"enabled":False,"iterations":1}}

class RouterTests(unittest.TestCase):
    def run_route(self, prompt, local_result=None, ram=5000, swap=0, swap_percent=0,
                  swap_out_pages=0, resident=False, minimum_ram=2500):
        calls = {"local":0,"remote":0}
        def local_fn(prompt, config): calls["local"] += 1; return local_result or LocalResult(True,"A concise improved sentence.",100,500,5,50)
        def remote_fn(prompt, config, key): calls["remote"] += 1; return RemoteResult(True,"remote",100,"y")
        metrics = lambda:{"available_ram_mb":ram,"swap_used_mb":swap,"cpu_percent":1,"load_average":[0,0,0],"ram_percent":10,"swap_percent":swap_percent,
                          "swap_activity_sample_seconds":.1,"swap_in_bytes":0,"swap_in_pages":0,"swap_out_bytes":swap_out_pages*4096,"swap_out_pages":swap_out_pages,"timestamp":"now"}
        residency = lambda config:{"resident":resident,"size_bytes":880000000 if resident else None}
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        log_path = Path(temp.name)/"runs.jsonl"
        config = deepcopy(CONFIG)
        config["routing"]["minimum_available_ram_mb"] = minimum_ram
        result = Router(config, log_path, local_fn, remote_fn, metrics, lambda n:0, residency, "key").route(prompt)
        record = json.loads(log_path.read_text().splitlines()[-1])
        return result, calls, record
    def test_healthy_valid_local(self): self.assertEqual(self.run_route("rewrite this sentence please")[0]["reason"], "LOCAL_ACCEPTED")
    def test_exact_failed_prompt_is_rewrite(self):
        prompt = "Rewrite: The weather was bad but I went outside anyway."
        self.assertEqual(classify(prompt, CONFIG), "rewrite")

    def test_rewrite_command_prefix_variants(self):
        for prompt in ("Rewrite: text", "rewrite: text", "REWRITE: text", " rewrite this... "):
            with self.subTest(prompt=prompt):
                self.assertEqual(classify(prompt, CONFIG), "rewrite")

    def test_remote_default(self):
        result,calls,_=self.run_route("write python code"); self.assertEqual(result["route"],"remote"); self.assertEqual(calls["local"],0)
    def test_low_ram(self):
        result,calls,_=self.run_route("rewrite this please",ram=100); self.assertEqual(result["reason"],"LOW_RAM"); self.assertEqual(calls["local"],0)
    def test_exact_failed_prompt_is_rejected_for_current_ram_threshold(self):
        prompt = "Rewrite: The weather was bad but I went outside anyway."
        result,calls,_=self.run_route(prompt,ram=1943)
        self.assertEqual(result["trigger"], "LOW_RAM")
        self.assertEqual(calls["local"], 0)

    def test_not_resident_above_ram_threshold_may_proceed(self):
        result,calls,record=self.run_route("rewrite this",ram=1900,resident=False,minimum_ram=1500)
        self.assertEqual(result["route"], "local")
        self.assertEqual(calls["local"], 1)
        self.assertFalse(record["local_model_resident"])

    def test_resident_below_ram_threshold_does_not_trigger_low_ram(self):
        result,calls,record=self.run_route("rewrite this",ram=1193,resident=True,minimum_ram=1500)
        self.assertEqual(result["route"], "local")
        self.assertEqual(calls["local"], 1)
        self.assertTrue(record["local_model_resident"])
        self.assertEqual(record["local_model_size_bytes"], 880000000)

    def test_occupied_swap_without_activity_does_not_reject(self):
        result,calls,record=self.run_route("rewrite this",ram=2177,swap=495,swap_percent=495/511*100,resident=False,minimum_ram=1500)
        self.assertEqual(result["route"], "local")
        self.assertEqual(record["system"]["swap_used_mb"], 495)
        self.assertEqual(record["system"]["swap_out_pages"], 0)
        self.assertEqual(calls["local"], 1)

    def test_active_swap_out_pressure_rejects(self):
        result,calls,record=self.run_route("rewrite this",ram=2177,swap=495,swap_percent=495/511*100,swap_out_pages=1,resident=False,minimum_ram=1500)
        self.assertEqual(result["trigger"], "ACTIVE_SWAP_PRESSURE")
        self.assertEqual(record["system"]["swap_out_pages"], 1)
        self.assertEqual(calls["local"], 0)

    def test_not_resident_below_ram_threshold_triggers_low_ram(self):
        result,calls,record=self.run_route("rewrite this",ram=1499,resident=False,minimum_ram=1500)
        self.assertEqual(result["trigger"], "LOW_RAM")
        self.assertEqual(calls["local"], 0)
    def test_local_error(self): self.assertEqual(self.run_route("rewrite this",LocalResult(False,error="boom"))[0]["reason"],"LOCAL_ERROR")
    def test_timeout(self): self.assertEqual(self.run_route("rewrite this",LocalResult(False,error="LOCAL_TIMEOUT"))[0]["decision"] if False else self.run_route("rewrite this",LocalResult(False,error="LOCAL_TIMEOUT"))[0]["reason"],"LOCAL_TIMEOUT")
    def test_high_ttft(self): self.assertEqual(self.run_route("rewrite this",LocalResult(True,"valid rewritten answer",9000,10000,5))[0]["reason"],"TTFT_EXCEEDED")
    def test_slow(self): self.assertEqual(self.run_route("rewrite this",LocalResult(True,"valid rewritten answer",100,1000,1))[0]["reason"],"GENERATION_TOO_SLOW")
    def test_validator_fail(self): self.assertEqual(self.run_route("rewrite this",LocalResult(True,"",100,1000,5))[0]["reason"],"VALIDATOR_FAILED")
    def test_na_accepts(self): self.assertEqual(self.run_route("format neatly",LocalResult(True,"mechanically unchanged",100,1000,5))[0]["reason"],"LOCAL_ACCEPTED")
