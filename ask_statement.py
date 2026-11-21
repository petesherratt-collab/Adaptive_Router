"""Ask questions about a bank statement in plain English.

    python ask_statement.py --csv statement.csv "How much did I spend at Morrisons each month?"
    python ask_statement.py --csv statement.csv          # interactive: one question per line

A model works out what the question means and which merchants count, and
writes a short Python function; the function runs locally, in the project's
sandbox, over every transaction. The model never does the arithmetic. Its
assumptions are printed with the answer so they can be checked.

A question asked before (same words, ignoring case and spacing) reuses its
saved function and needs no model call: the project's write-once idea in
small. The cache and anything derived from the data live in
``real_tasks/private/`` (git-ignored); the statement itself is never copied
into the repository.

Reads Monzo's "search" export (ID, Created, Title, Subtitle, Amount, Currency,
Categories), Monzo's full export (Transaction ID, Date, Time, Name,
Category, Amount, ...), and the combined table from ``combine_statements.py``
(main account plus Monzo, with ``account`` and ``internal`` columns).
"""

from __future__ import annotations

import argparse
import collections
import csv
import datetime
import hashlib
import json
import os
from pathlib import Path
import time

from dotenv import load_dotenv

import fast_path
import remote
import sandbox

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "real_tasks/private/ask_statement_cache.json"
MODEL = "openai/gpt-6-luna"
TIMEOUT_SECONDS = 20.0


def load_statement(path):
    """Rows as ``{"date", "time", "merchant", "note", "amount", "category"}``,
    oldest first. Amounts are signed pounds: negative is money out."""
    with open(path, encoding="utf-8-sig") as handle:
        raw = list(csv.DictReader(handle))
    if not raw:
        return []
    rows = []
    if "account" in raw[0]:  # combine_statements.py output
        for r in raw:
            rows.append({"date": r["date"], "time": r["time"], "account": r["account"],
                         "merchant": r["merchant"].strip(), "note": r["note"].strip(),
                         "amount": round(float(r["amount"]), 2), "category": r["category"].strip(),
                         "internal": r["internal"] == "True"})
        rows.sort(key=lambda r: (r["date"], r["time"]))
        return rows
    for r in raw:
        if "Created" in r:  # Monzo search export
            when = datetime.datetime.strptime(r["Created"], "%d/%m/%y, %H:%M")
            merchant, note, category = r["Title"], r.get("Subtitle", ""), r.get("Categories", "")
        elif "Date" in r:  # Monzo full export
            when = datetime.datetime.strptime(f"{r['Date']} {r.get('Time') or '00:00:00'}", "%d/%m/%Y %H:%M:%S")
            merchant, note, category = r.get("Name", ""), r.get("Notes and #tags", ""), r.get("Category", "")
        else:
            raise ValueError("unrecognised statement format")
        rows.append({"date": when.strftime("%Y-%m-%d"), "time": when.strftime("%H:%M"),
                     "merchant": merchant.strip(), "note": note.strip(),
                     "amount": round(float(r["Amount"]), 2), "category": category.strip()})
    rows.sort(key=lambda r: (r["date"], r["time"]))
    return rows


def describe(rows):
    """What the model is told about the data: layout, range and every merchant."""
    merchants = collections.defaultdict(lambda: [0, collections.Counter()])
    for r in rows:
        merchants[r["merchant"]][0] += 1
        merchants[r["merchant"]][1][r["category"]] += 1
    listing = "\n".join(f"- {name!r}: {count} transactions, Monzo category {dict(cats)}"
                        for name, (count, cats) in sorted(merchants.items(), key=lambda m: -m[1][0]))
    if "account" in rows[0]:
        return (
            f"{len(rows)} transactions from {rows[0]['date']} to {rows[-1]['date']}, all in GBP, from two of the "
            "same person's accounts: 'main' (a current account: salary in, bills and card spending out) and "
            "'monzo' (a spending account topped up from main).\n"
            "Each row is a dict with keys: 'date' ('YYYY-MM-DD'), 'time' ('HH:MM', empty for main), 'account' "
            "('main' or 'monzo'), 'merchant' (the statement name), 'note' (extra text; for main the full "
            "statement description), 'amount' (signed pounds as a float: negative is money out, positive is "
            "money in), 'category' (for monzo, Monzo's category id; for main, the payment type such as "
            "'Contactless Payment', 'Direct debit', 'Card or other'), 'internal' (True for money moved between "
            "the person's own accounts or Monzo savings pots: not spending or income, exclude it from totals "
            "unless the question is about transfers).\n"
            f"Example rows: {json.dumps(rows[:3])}\n\n"
            f"Every merchant name in the data (categories shown are per account as above):\n{listing}"
        )
    return (
        f"{len(rows)} transactions from {rows[0]['date']} to {rows[-1]['date']}, all in GBP.\n"
        "Each row is a dict with keys: 'date' ('YYYY-MM-DD'), 'time' ('HH:MM'), 'merchant' (the statement "
        "name), 'note' (extra text, often empty), 'amount' (signed pounds as a float: negative is money "
        "spent, positive is money in), 'category' (Monzo's category id).\n"
        f"Example rows: {json.dumps(rows[:3])}\n\n"
        f"Every merchant name in the data:\n{listing}"
    )


def build_prompt(question, description, error=None):
    modules = ", ".join(sandbox.ALLOWED_MODULES)
    text = (
        "You answer questions about a person's bank statement by writing code that computes the answer.\n\n"
        f"The data:\n{description}\n\n"
        f"Question: {question}\n\n"
        "Decide what the question means: which merchants count (statement names vary, and a name can "
        "mislead: for example a canteen run by a caterer at a company's site is not that company's shop), "
        "which rows (spending is negative amounts; say if refunds are netted), and which period. Then write "
        "Python defining solve(rows), which returns the answer as one plain-text string a person can read, "
        "with money as £ and two decimals and a small aligned table where that helps. Compute everything "
        f"from rows; do not hard-code results. Pure Python; you may import only {modules}; no classes, no "
        "file or network access, no names beginning with an underscore.\n\n"
        "Reply with JSON only, no code fence: {\"assumptions\": \"<one or two plain sentences on what you "
        "counted and why>\", \"code\": \"<python source>\"}"
    )
    if error:
        text += f"\n\nA previous answer failed when run: {error}. Fix it and reply again in the same form."
    return text


def parse_reply(text):
    try:
        value = fast_path.strict_json(fast_path._unfence(text))
    except (ValueError, TypeError, RecursionError):
        return None, "REPLY_NOT_JSON"
    if not isinstance(value, dict) or not isinstance(value.get("code"), str):
        return None, "REPLY_FIELDS_MISSING"
    code = fast_path._unfence(value["code"]) + "\n"
    accepted, reason = sandbox.check_source(code)
    if not accepted:
        return None, f"CODE_REJECTED:{reason}"
    return {"assumptions": str(value.get("assumptions", "")), "code": code}, None


def run(code, rows):
    result = sandbox.run_function(code, [[rows]], TIMEOUT_SECONDS)
    if not result.ok:
        return None, result.error
    first = result.results[0]
    if not first["ok"]:
        return None, first["error"]
    value = first["value"]
    return (value if isinstance(value, str) else json.dumps(value, indent=1)), None


def question_key(question):
    return " ".join(question.lower().split())


class Asker:
    def __init__(self, rows, remote_fn=remote.generate, api_key=None, cache_path=CACHE, model=MODEL):
        self.rows = rows
        self.description = describe(rows)
        self.remote_fn = remote_fn
        self.api_key = api_key if api_key is not None else os.getenv("OPENROUTER_API_KEY")
        self.cache_path = Path(cache_path)
        self.model = model
        try:
            self.cache = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.cache = {}
        config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))["remote"]
        self.config = {**config, "model": model, "max_tokens": 8192, "temperature": 0}

    def _save(self):
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(self.cache, indent=1), encoding="utf-8")

    def ask(self, question):
        """Returns ``{"answer", "assumptions", "code", "cached", "ms", "model_calls", "cost"}``;
        ``answer`` is None with an ``error`` if no working code was found."""
        started = time.perf_counter()
        key = question_key(question)
        cached = self.cache.get(key)
        if cached:
            answer, error = run(cached["code"], self.rows)
            if answer is not None:
                return {"answer": answer, "assumptions": cached["assumptions"], "code": cached["code"],
                        "cached": True, "ms": (time.perf_counter() - started) * 1000, "model_calls": 0,
                        "cost": 0.0}
        calls, cost, error, reply = 0, 0.0, None, None
        for _ in range(2):
            result = self.remote_fn(build_prompt(question, self.description, error), self.config, self.api_key)
            calls += 1
            cost += getattr(result, "cost", None) or 0.0
            if not result.success:
                error = result.error
                continue
            reply, error = parse_reply(result.text)
            if reply is None:
                continue
            answer, error = run(reply["code"], self.rows)
            if answer is not None:
                self.cache[key] = reply
                self._save()
                return {"answer": answer, **reply, "cached": False,
                        "ms": (time.perf_counter() - started) * 1000, "model_calls": calls, "cost": cost}
        return {"answer": None, "error": error, "cached": False, "code": (reply or {}).get("code"),
                "ms": (time.perf_counter() - started) * 1000, "model_calls": calls, "cost": cost}


def show(result, show_code=False):
    if result["answer"] is None:
        print(f"[no answer: {result['error']}]")
        return
    print(result["answer"])
    print(f"\n[{'saved code, no model call' if result['cached'] else 'new code'} | "
          f"{result['ms']:.0f} ms | model calls {result['model_calls']} | cost ${result['cost']:.4f}]")
    print(f"[assumptions: {result['assumptions']}]")
    if show_code:
        print("\n" + result["code"])


def main():
    parser = argparse.ArgumentParser(description="Ask questions about a bank statement.")
    parser.add_argument("question", nargs="?", help="the question; omit for interactive mode")
    parser.add_argument("--csv", required=True, help="the statement export")
    parser.add_argument("--show-code", action="store_true", help="print the code that computed the answer")
    parser.add_argument("--forget", action="store_true", help="ignore saved code for this question")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    asker = Asker(load_statement(args.csv))
    questions = [args.question] if args.question else iter(lambda: input("\nquestion> ").strip(), "")
    for question in questions:
        if args.forget:
            asker.cache.pop(question_key(question), None)
        show(asker.ask(question), args.show_code)


if __name__ == "__main__":
    try:
        main()
    except (EOFError, KeyboardInterrupt):
        print()
