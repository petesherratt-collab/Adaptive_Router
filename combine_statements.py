"""Combine the main account (from statement_pdf.py) with a Monzo export into one table.

    python combine_statements.py --main real_tasks/private/main_account.csv --monzo MONZO.csv \\
        --owner "SHERRATT" --out real_tasks/private/combined.csv

Money moved between the owner's own accounts is marked ``internal`` so it is
not counted as spending or income: a transfer out of the main account to the
owner's name is paired with a Monzo credit from the owner's name of the same
amount within three days. Monzo pot moves (savings pots) are internal too.
Only the overlapping period is kept, so both accounts are complete in it.
Runs locally; output stays in ``real_tasks/private/`` (git-ignored).
"""

from __future__ import annotations

import argparse
import csv
import datetime

import ask_statement

FIELDS = ["date", "time", "account", "merchant", "note", "amount", "category", "internal"]
POTS = {"savings"}


def combine(main_rows, monzo_rows, owner, start=None, end=None):
    """``start``/``end`` (ISO dates) default to the main account's first and last transactions;
    pass the statement period when it starts or ends on a day with no main-account transaction."""
    owner = owner.upper()
    start, end = start or main_rows[0]["date"], end or main_rows[-1]["date"]
    main = [{"date": r["date"], "time": "", "account": "main", "merchant": r["merchant"] or r["kind"],
             "note": r["description"], "amount": float(r["amount"]), "category": r["kind"], "internal": False}
            for r in main_rows]
    monzo = [{**r, "account": "monzo", "internal": r["category"] in POTS}
             for r in monzo_rows if start <= r["date"] <= end]
    credits = [r for r in monzo if r["amount"] > 0 and owner in r["merchant"].upper()]
    debits = [r for r in monzo if r["amount"] < 0 and owner in r["merchant"].upper()]
    paired = 0
    for out in (r for r in main if owner in r["merchant"].upper()):
        day = datetime.date.fromisoformat(out["date"])
        pool = credits if out["amount"] < 0 else debits
        match = next((c for c in pool if not c["internal"] and abs(c["amount"] + out["amount"]) < 0.005
                      and abs((datetime.date.fromisoformat(c["date"]) - day).days) <= 3), None)
        if match:
            match["internal"] = out["internal"] = True
            paired += 1
    rows = sorted(main + monzo, key=lambda r: (r["date"], r["time"], r["account"]))
    return rows, paired


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--main", required=True)
    parser.add_argument("--monzo", required=True)
    parser.add_argument("--owner", required=True, help="a word of the owner's name as it appears on transfers")
    parser.add_argument("--out", required=True)
    parser.add_argument("--start", help="first day of the statement period (YYYY-MM-DD)")
    parser.add_argument("--end", help="last day of the statement period (YYYY-MM-DD)")
    args = parser.parse_args()
    with open(args.main, encoding="utf-8") as handle:
        main_rows = list(csv.DictReader(handle))
    rows, paired = combine(main_rows, ask_statement.load_statement(args.monzo), args.owner, args.start, args.end)
    with open(args.out, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    unpaired = [r for r in rows if not r["internal"] and args.owner.upper() in r["merchant"].upper()]
    print(f"{len(rows)} rows, {rows[0]['date']} to {rows[-1]['date']}; {paired} transfers paired; "
          f"{len(unpaired)} owner-named rows left unpaired")


if __name__ == "__main__":
    main()
