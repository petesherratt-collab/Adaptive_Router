"""Read Nationwide FlexAccount PDF statements into transaction rows, locally.

    python statement_pdf.py STATEMENT.pdf [...] --out real_tasks/private/main_account.csv

Uses ``pdftotext -layout`` and the column positions of each page's
"Date | Description | £ Out | £ In | £ Balance" header. No model is used.

Every printed running balance is checked against the opening balance plus the
transactions so far; a statement that does not reconcile is reported and its
rows are still written, marked, so nothing is silently wrong. Output goes to
``real_tasks/private/`` (git-ignored) and never into the repository.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import re
import subprocess
import sys

AMOUNT = re.compile(r"(?<![\d.,])\d{1,3}(?:,\d{3})*\.\d{2}(?![\d.])")
DATE = re.compile(r"^\s{0,6}(\d{2} [A-Z][a-z]{2})(?:\s{2,}(.*))?$")
YEAR = re.compile(r"^\s{0,6}(20\d{2})(?:\s|$)")
OPENING = re.compile(r"Balance from statement \d+ dated (\d{2})/(\d{2})/(\d{4})")
FOOTER = ("Please check your statement", "Nationwide Building Society is authorised", "DC86 (")
SKIP = ("Effective Date", "Closing balance", "Balance carried forward")
KINDS = ("Contactless Payment", "Direct debit", "Bank credit", "Transfer to", "Transfer from",
         "Standing order", "Cash withdrawal", "Cheque deposit", "Payment to", "Visa purchase")


def page_columns(header):
    """Right edges of the Out, In and Balance headings on this page."""
    return {"out": header.index("Out") + 3, "in": header.index("In", header.index("Out") + 3) + 2,
            "balance": header.index("Balance") + 7}


def parse_text(text, source=""):
    """Rows ``{"date", "description", "amount", "balance", "source"}`` (amount signed) plus the
    opening balance and the printed balances to reconcile against."""
    rows, checks, year, date, opening = [], [], None, None, None
    pending = []  # descriptions printed above their amounts (the PDF sometimes lays a day out that way)
    for page in text.split("\f"):
        lines = page.splitlines()
        start = next((i for i, l in enumerate(lines) if "Description" in l and "Balance" in l and "Out" in l), None)
        if start is None:
            continue
        cols = page_columns(lines[start])
        cut = cols["balance"] + 4
        for raw in lines[start + 1:]:
            if any(f in raw for f in FOOTER):
                break
            line = raw[:cut].rstrip()
            if not line.strip() or any(s in line for s in SKIP):
                continue
            found = OPENING.search(line)
            if found:
                year = int(found.group(3))
                amounts = list(AMOUNT.finditer(line))
                opening = float(amounts[-1].group().replace(",", "")) if amounts else None
                continue
            y = YEAR.match(line)
            if y:
                year = int(y.group(1))
                line = " " * len(y.group(0)) + line[len(y.group(0)):]
            d = DATE.match(line)
            if d:
                date = datetime.datetime.strptime(f"{d.group(1)} {year}", "%d %b %Y").date()
            out = inn = bal = None
            for m in AMOUNT.finditer(line):
                value = float(m.group().replace(",", ""))
                edge = m.end()
                column = min(cols, key=lambda c: abs(cols[c] - edge))
                if column == "out":
                    out = value
                elif column == "in":
                    inn = value
                else:
                    bal = value
            text_part = AMOUNT.sub("", line[d.end(1):] if d else line).strip()
            text_part = re.sub(r"\s{2,}", " ", text_part)
            if out is not None or inn is not None:
                if not text_part and pending:
                    text_part = pending.pop(0)
                rows.append({"date": date.isoformat(), "description": text_part,
                             "amount": round((inn or 0.0) - (out or 0.0), 2), "balance": bal, "source": source})
                if bal is not None:
                    checks.append((len(rows), bal, False))
            elif bal is not None:
                if rows:  # a balance with no amount: it belongs to one of the day's last rows
                    rows[-1]["balance"] = bal
                    if text_part:  # some layouts print the balance on a continuation line (the payee)
                        rows[-1]["description"] = f"{rows[-1]['description']} | {text_part}"
                        checks.append((len(rows), bal, False))
                    else:
                        checks.append((len(rows), bal, True))
                elif opening is None:
                    opening = bal
            elif text_part and (text_part.startswith(KINDS) or pending):
                if text_part.startswith(KINDS):
                    pending.append(text_part)
                else:
                    pending[-1] = f"{pending[-1]} | {text_part}"
            elif text_part and rows:
                rows[-1]["description"] = f"{rows[-1]['description']} | {text_part}"
    return rows, opening, checks


def reconcile(rows, opening, checks):
    """Problems as ``(row_number, printed, computed)``; empty when every balance agrees."""
    if opening is None:
        return [(0, None, None)]
    problems, total = [], opening
    sums = []
    for r in rows:
        total = round(total + r["amount"], 2)
        sums.append(total)
    for n, printed, loose in checks:
        window = sums[max(0, n - 4):n] if loose else [sums[n - 1]]
        if all(abs(v - printed) > 0.005 for v in window):
            problems.append((n, printed, sums[n - 1]))
    return problems


def split(description):
    """(kind, merchant): 'Contactless Payment | WM MORRISONS STORE ERITH' -> ('Contactless Payment', ...)."""
    parts = [p.strip() for p in description.split("|")]
    head = parts[0]
    for kind in KINDS:
        if head.startswith(kind):
            rest = head[len(kind):].strip()
            merchant = rest or (parts[1] if len(parts) > 1 else "")
            return kind, merchant
    return "Card or other", head


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pdfs", nargs="+")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    everything, bad = [], 0
    for path in args.pdfs:
        text = subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True,
                              check=True).stdout
        rows, opening, checks = parse_text(text, source=path.rsplit("/", 1)[-1])
        problems = reconcile(rows, opening, checks)
        status = "ok" if not problems else f"{len(problems)} balance mismatches, first at row {problems[0][0]}"
        bad += bool(problems)
        print(f"{rows[0]['date'] if rows else '?'} .. {rows[-1]['date'] if rows else '?'}: {len(rows)} rows, "
              f"{len(checks)} balances checked: {status}", file=sys.stderr)
        for r in rows:
            r["kind"], r["merchant"] = split(r["description"])
            r["reconciled"] = not problems
        everything += rows
    with open(args.out, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, ["date", "kind", "merchant", "description", "amount", "balance",
                                         "reconciled", "source"])
        writer.writeheader()
        writer.writerows(everything)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
