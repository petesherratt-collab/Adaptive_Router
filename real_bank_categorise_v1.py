"""Real task V1: categorise the owner's bank transactions. Makes provider calls.

The owner's Monzo export (path given on the command line, never committed)
supplies the transactions and Monzo's own category for each, used as the
correct answer. Transactions before ``SPLIT`` train; the rest are tested in
date order. Arms, scored per test transaction against Monzo's category:

  E  code only: the most common training category for the merchant key, or
     ``general`` for a merchant not seen in training. No model.
  M  models only: the five-model race reads the merchant key and picks one of
     Monzo's categories; first usable answer wins. Raced once per distinct
     key and reused for every transaction with that key.
  H  hybrid (the router's way): the training table, with unseen keys sent to
     the race (M's answer).
  H2 hybrid that keeps learning: as H, but every test transaction's Monzo
     category joins the table once seen, as Monzo's own history would; only a
     key's first appearance goes to the race.

The merchant key is the statement title alone (subtitles are mostly varying
references). Per-key
detail (names included) goes to ``real_tasks/private/`` (git-ignored); the
summary written with ``--summary`` holds aggregate figures only.
"""

from __future__ import annotations

import argparse
import collections
import csv
import datetime
import json
import os
from pathlib import Path
import statistics
import time

from dotenv import load_dotenv

import fast_path

ROOT = Path(__file__).resolve().parent
SPLIT = datetime.datetime(2026, 3, 1)
CATEGORIES = ["eating_out", "entertainment", "transport", "groceries", "transfers", "general", "shopping",
              "savings", "bills", "holidays", "income", "personal_care", "cash"]
SPEC = ("Classify a UK bank transaction, given only the merchant or payee name as it appears on the "
        "statement, into exactly one of these Monzo spending "
        "categories: " + ", ".join(CATEGORIES) + ". Return the category id.")
SIGNATURE = "def solve(text: str) -> str:"


def load(path):
    rows = []
    with open(path, encoding="utf-8-sig") as handle:
        for r in csv.DictReader(handle):
            when = datetime.datetime.strptime(r["Created"], "%d/%m/%y, %H:%M")
            # The merchant title alone: subtitles are mostly varying references
            # that would split one merchant into many keys.
            key = r["Title"].strip()
            rows.append({"when": when, "key": key, "category": r["Categories"].strip(),
                         "amount": float(r["Amount"])})
    rows.sort(key=lambda r: r["when"])
    return rows


def table(rows):
    counts = collections.defaultdict(collections.Counter)
    for r in rows:
        counts[r["key"]][r["category"]] += 1
    return {key: c.most_common(1)[0][0] for key, c in counts.items()}


def race(router, keys):
    """Race every key once. Returns {key: {"answer", "ms", "answers"}}."""
    out = {}
    for key in keys:
        prompt = fast_path.build_answer_prompt(SPEC, SIGNATURE, [key])
        started = time.perf_counter()
        futures = router.start_prompt_race(prompt)
        model, value = fast_path.FastPathRouter._first_valid(futures)
        ms = (time.perf_counter() - started) * 1000
        answers = {futures[f]: (f.result()["value"] if f.result()["valid"] else None) for f in futures}
        out[key] = {"answer": value if value in CATEGORIES else None, "winner": model, "ms": ms,
                    "answers": answers}
    return out


def evaluate(train, test, raced):
    known = table(train)
    online = dict(known)
    arms = {arm: {"correct": 0, "model_calls_needed": 0, "ms": []} for arm in ("E", "M", "H", "H2")}
    for r in test:
        gold = r["category"]
        m = raced[r["key"]]
        picks = {
            "E": (known.get(r["key"], "general"), 0.0, False),
            "M": (m["answer"], m["ms"], True),
            "H": ((known[r["key"]], 0.0, False) if r["key"] in known else (m["answer"], m["ms"], True)),
            "H2": ((online[r["key"]], 0.0, False) if r["key"] in online else (m["answer"], m["ms"], True)),
        }
        for arm, (answer, ms, used_model) in picks.items():
            arms[arm]["correct"] += answer == gold
            arms[arm]["model_calls_needed"] += used_model
            arms[arm]["ms"].append(ms)
        online.setdefault(r["key"], gold)
    n = len(test)
    return {arm: {"correct": a["correct"], "of": n, "accuracy": a["correct"] / n,
                  "transactions_needing_a_model": a["model_calls_needed"],
                  "median_ms": statistics.median(a["ms"]), "mean_ms": statistics.fmean(a["ms"])}
            for arm, a in arms.items()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("export", help="Monzo CSV export (kept out of the repository)")
    parser.add_argument("--summary", required=True, help="aggregate summary JSON (must not exist)")
    parser.add_argument("--detail", default=str(ROOT / "real_tasks/private/bank_v1_detail.json"))
    args = parser.parse_args()
    if Path(args.summary).exists():
        parser.error("summary exists; evidence is never overwritten")
    load_dotenv(ROOT / ".env")
    rows = load(args.export)
    train = [r for r in rows if r["when"] < SPLIT]
    test = [r for r in rows if r["when"] >= SPLIT]
    keys = sorted({r["key"] for r in test})
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    settings = json.loads((ROOT / "config_fast_path.json").read_text(encoding="utf-8"))["fast_path"]
    router = fast_path.FastPathRouter({"remote": config["remote"], "fast_path": {**settings, "synthesis_enabled": False}},
                                      ROOT / "real_tasks/private/store", ROOT / "real_tasks/private/runs.jsonl",
                                      api_key=os.getenv("OPENROUTER_API_KEY"))
    raced = race(router, keys)
    router.close()
    result = evaluate(train, test, raced)
    known = table(train)
    agree = [len({v for v in r["answers"].values() if v}) == 1 for r in raced.values()]
    summary = {
        "label": "real_bank_v1", "split": SPLIT.date().isoformat(),
        "train_transactions": len(train), "test_transactions": len(test),
        "test_keys": len(keys), "test_keys_unseen_in_training": sum(k not in known for k in keys),
        "test_transactions_with_unseen_key": sum(r["key"] not in known for r in test),
        "race_calls": 5 * len(keys), "race_unanswered_keys": sum(r["answer"] is None for r in raced.values()),
        "keys_where_valid_racers_all_agreed": sum(agree),
        "race_median_ms": statistics.median(r["ms"] for r in raced.values()),
        "arms": result,
    }
    Path(args.detail).write_text(json.dumps({"raced": raced, "summary": summary}, indent=1, default=str),
                                 encoding="utf-8")
    Path(args.summary).write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
