"""From raw statements to a filled-in template, one visible stage at a time.

    python run_pipeline.py

Stage 1  current-account PDFs  -> stages/1_current_account_extracted.csv   (statement_pdf.py, balances reconciled)
Stage 2  + spending-account CSV -> stages/2_combined.csv                     (combine_statements.py, own transfers paired)
Stage 3  categorising rules     -> stages/3_transactions_for_template.csv, stages/3_merchants.csv
Stage 4  template inputs filled -> stages/4_filled_template.xlsx             (outputs calculate from the inputs)

No model is used: every step is code, so the same statements always give the same workbook.
"""

from __future__ import annotations

import csv
import datetime as dt
import shutil
import subprocess
import sys
from pathlib import Path

from openpyxl import load_workbook

HERE = Path(__file__).resolve().parent
ROUTER = HERE.parents[1]          # the repository root (statement_pdf.py, combine_statements.py)
TEMPLATE = HERE / "bank_statement_template.xlsx"
STAGES = HERE / "stages"
sys.path.insert(0, str(ROUTER))
import ask_statement            # noqa: E402  reads the spending-account export
import combine_statements       # noqa: E402

PDFS = [HERE / f"statements/Riverside_{m}_2026.pdf" for m in ("Sep", "Oct", "Nov")]   # in date order
EXPORT = HERE / "statements/spending_account_export.csv"
PERIOD = ("2026-08-12", "2026-11-11")   # from the statements: 12 Aug to 11 Nov
OWNER = "MORGAN"            # a word of the owner's name as it appears on transfers between their own accounts
ACCOUNTS = {"main": "Riverside", "monzo": "Spending"}
OPENING = {"Riverside": 912.40, "Spending": 0.0}   # Riverside: "Balance from statement 100"; the app export has no balance

# Stage 3 rules: the first rule whose words appear in the merchant name decides the category.
RULES = [
    ("ACME LOGISTICS", "income"), ("Cheque deposit", "income"),
    ("J PATEL", "rent"),
    ("CREDITLINE RECOVERIES", "debt repayments"),
    ("BORO COUNCIL", "bills and utilities"), ("BRIGHTSPARK", "bills and utilities"), ("VOXTEL", "bills and utilities"),
    ("NETFLIX", "online shopping and subscriptions"), ("LEARNWELL", "online shopping and subscriptions"),
    ("PIXELHOST", "online shopping and subscriptions"), ("Foreign currency", "online shopping and subscriptions"),
    ("eBay", "online shopping and subscriptions"), ("Amazon", "online shopping and subscriptions"),
    ("MORRISONS", "groceries"), ("Tesco", "groceries"), ("Lidl", "groceries"),
    ("CANTEEN", "eating out"), ("GREGGS", "eating out"), ("McDonald", "eating out"),
    ("Wetherspoon", "pubs and bars"), ("Red Lion", "pubs and bars"),
    ("Transport for London", "transport"),
    ("Sky Bet", "gambling"),
]


def categorise(merchant):
    low = merchant.lower()
    return next((cat for words, cat in RULES if words.lower() in low), "other")


def stage1():
    out = STAGES / "1_current_account_extracted.csv"
    subprocess.run([sys.executable, str(ROUTER / "statement_pdf.py"), *map(str, PDFS), "--out", str(out)], check=True)
    return out


def stage2(main_csv):
    with open(main_csv, encoding="utf-8") as h:
        main_rows = list(csv.DictReader(h))
    rows, paired = combine_statements.combine(main_rows, ask_statement.load_statement(EXPORT), OWNER, *PERIOD)
    # printed balances travel with the main-account rows, for the template's balance check
    balances = iter(r["balance"] for r in main_rows)
    for r in rows:
        r["printed_balance"] = next(balances) if r["account"] == "main" else ""
    out = STAGES / "2_combined.csv"
    with open(out, "w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, combine_statements.FIELDS + ["printed_balance"])
        w.writeheader(); w.writerows(rows)
    print(f"stage 2: {len(rows)} rows from both accounts, {paired} own transfers paired and marked internal")
    return rows


def stage3(rows):
    tx = []
    for r in rows:
        tx.append({"Date": r["date"], "Account": ACCOUNTS[r["account"]], "Merchant": r["merchant"], "Details": r["note"] or r["category"],
                   "Money out": f"{-r['amount']:.2f}" if r["amount"] < 0 else "",
                   "Money in": f"{r['amount']:.2f}" if r["amount"] > 0 else "",
                   "Category override": "internal transfer" if r["internal"] else "",
                   "Printed balance": r["printed_balance"]})
    merchants = sorted({t["Merchant"] for t in tx if not t["Category override"]})
    mer = [{"Merchant": m, "Category": categorise(m)} for m in merchants]
    for name, data, fields in (("3_transactions_for_template.csv", tx, list(tx[0])), ("3_merchants.csv", mer, ["Merchant", "Category"])):
        with open(STAGES / name, "w", newline="", encoding="utf-8") as h:
            w = csv.DictWriter(h, fields); w.writeheader(); w.writerows(data)
    others = [m["Merchant"] for m in mer if m["Category"] == "other"]
    print(f"stage 3: {len(tx)} template rows, {len(mer)} merchants categorised; fell through to 'other': {others or 'none'}")
    return tx, mer


def stage4(tx, mer):
    out = STAGES / "4_filled_template.xlsx"
    shutil.copy(TEMPLATE, out)
    wb = load_workbook(out)
    st, ca, ws, me = wb["Settings"], wb["Categories"], wb["Transactions"], wb["Merchants"]
    st["B3"] = dt.date(2026, 8, 1)
    for i, name in enumerate(ACCOUNTS.values()):
        st.cell(6 + i, 1, name); st.cell(6 + i, 2, OPENING[name]); st.cell(6 + i, 4, None)
    names = [ca.cell(r, 1).value for r in range(2, 22)]
    if "rent" not in names:                       # categories are an input too: add one
        slot = names.index(None) + 2
        ca.cell(slot, 1, "rent"); ca.cell(slot, 2, "Yes")
    for r in range(2, 3002):                      # clear the template's example rows
        for c in range(1, 9):
            ws.cell(r, c).value = None
    for r in range(2, 502):
        me.cell(r, 1).value = None; me.cell(r, 2).value = None
    for i, t in enumerate(tx, 2):
        ws.cell(i, 1, dt.date.fromisoformat(t["Date"])); ws.cell(i, 2, t["Account"]); ws.cell(i, 3, t["Merchant"])
        ws.cell(i, 4, t["Details"])
        ws.cell(i, 5, float(t["Money out"]) if t["Money out"] else None)
        ws.cell(i, 6, float(t["Money in"]) if t["Money in"] else None)
        ws.cell(i, 7, t["Category override"] or None)
        ws.cell(i, 8, float(t["Printed balance"]) if t["Printed balance"] else None)
    for i, m in enumerate(mer, 2):
        me.cell(i, 1, m["Merchant"]); me.cell(i, 2, m["Category"])
    wb.save(out)
    print(f"stage 4: template inputs filled -> {out.name}")
    return out


if __name__ == "__main__":
    STAGES.mkdir(exist_ok=True)
    main_csv = stage1()
    rows = stage2(main_csv)
    tx, mer = stage3(rows)
    stage4(tx, mer)
