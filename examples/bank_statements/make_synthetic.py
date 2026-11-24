"""Make a synthetic set of statements for a fictional person, Alex Morgan.

    python make_synthetic.py      # writes statements/ and truth/

Modelled on the shape of a real two-account setup (weekly wages into a current
account; rent, bills and debt repayments out of it; frequent top-ups to a
Monzo-style spending account where day-to-day spending happens), with every
name, amount and reference invented. The bank ("Riverside Building Society"),
employer, landlord and billers are fictional; shops are ordinary UK chains.

Outputs:
  statements/Riverside_<month>_2026.pdf   three monthly current-account statements (PDF)
  statements/spending_account_export.csv  the spending account's app export (CSV)
  truth/current_account.csv               every current-account line as generated, to check extraction
"""

from __future__ import annotations

import csv
import datetime as dt
import random
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

HERE = Path(__file__).resolve().parent
rng = random.Random(20261122)
START, END = dt.date(2026, 8, 12), dt.date(2026, 11, 11)
OPENING = 912.40
OWNER_TRANSFER = "Transfer to A Morgan"       # how the current account shows a top-up
OWNER_CREDIT = "MORGAN ALEX"                   # how the spending account shows it arriving


def days():
    d = START
    while d <= END:
        yield d
        d += dt.timedelta(days=1)


def money(lo, hi):
    return round(rng.uniform(lo, hi), 2)


# ---------------------------------------------------------------- generate
current = []   # {"date", "lines": [first line text, continuation...], "out", "in"}
spending = []  # {"when", "title", "subtitle", "amount", "category"}


def cur(day, text, out=None, inn=None, more=()):
    current.append({"date": day, "lines": [text, *more], "out": out, "in": inn})


def spend(day, title, amount, category, subtitle="", hour=None):
    when = dt.datetime.combine(day, dt.time(hour if hour is not None else rng.randint(8, 22), rng.randint(0, 59)))
    spending.append({"when": when, "title": title, "subtitle": subtitle, "amount": amount, "category": category})


for day in days():
    wd = day.weekday()
    # --- current account
    if wd == 4:
        cur(day, "Bank credit ACME LOGISTICS LTD", inn=money(555, 615), more=["REF 4471 0092"])
    if day.day == 1:
        cur(day, "Standing order J PATEL", out=895.00)
    if day.day == 5:
        cur(day, "Direct debit CREDITLINE RECOVERIES", out=100.00)
    if day.day == 15:
        cur(day, "Direct debit RIVERSIDE BORO COUNCIL", out=138.00)
    if day.day == 20:
        cur(day, "Direct debit BRIGHTSPARK ENERGY", out=money(78, 92))
    if day.day == 28:
        cur(day, "Direct debit VOXTEL MOBILE", out=58.31)
    if day.day == 3:
        cur(day, "NETFLIX.COM 866-579-7172", out=10.99)
    if day.day == 9:
        cur(day, "LEARNWELL ONLINE LONDON", out=36.00)
    if day.day == 23:
        cur(day, "PIXELHOST.IO TALLINN", out=6.68, more=["9.000000USD at 1.34731"])
        cur(day, "Foreign currency transaction fee", out=0.20)
    if day == dt.date(2026, 9, 17):
        cur(day, "Cheque deposit", inn=200.00)
    if wd < 5 and rng.random() < 0.7:
        cur(day, "Contactless Payment", out=money(1.00, 3.95), more=["WORKPLACE CANTEEN THURROCK"])
    if wd in (0, 3) or rng.random() < 0.12:
        cur(day, "Contactless Payment", out=money(12, 48), more=["WM MORRISONS STORE DARTVILLE"])
    if rng.random() < 0.15:
        cur(day, "Contactless Payment", out=money(2.5, 6.5), more=["GREGGS PLC DARTVILLE"])
    # top-ups to the spending account, most days
    if rng.random() < 0.42:
        amount = rng.choice([100.00, 50.00, 50.00, 20.00])
        cur(day, OWNER_TRANSFER, out=amount)
        arrive = day if rng.random() < 0.8 else day + dt.timedelta(days=1)
        if arrive <= END:
            spend(arrive, OWNER_CREDIT, amount, "transfers", "Sent from Riverside", hour=rng.randint(6, 9))

    # --- spending account
    if rng.random() < 0.6:
        spend(day, "Wetherspoon", -money(3.2, 16), "eating_out", "The Moon and Lantern")
    if wd >= 4 and rng.random() < 0.5:
        spend(day, "The Red Lion", -money(5, 14), "entertainment")
    if wd < 5 and rng.random() < 0.6:
        spend(day, "Transport for London", -money(2.8, 8.9), "transport")
    if rng.random() < 0.35:
        spend(day, rng.choice(["Tesco", "Lidl", "Morrisons"]), -money(3, 22), "groceries")
    if rng.random() < 0.2:
        spend(day, rng.choice(["Greggs", "McDonald's"]), -money(2.5, 8), "eating_out")
    if rng.random() < 0.06:
        spend(day, "eBay", -money(8, 40), "shopping")
    if rng.random() < 0.06:
        spend(day, "Amazon", -money(7, 30), "shopping")
    if rng.random() < 0.05:
        spend(day, "Sky Bet", -10.00, "entertainment")
    if day.day == 14:
        spend(day, "Rainy day", -20.00, "savings", "Moved to pot")

# a refund, so refunds are exercised
spend(dt.date(2026, 10, 2), "eBay", 18.50, "shopping", "Refund")

# ---------------------------------------------------------------- write the spending-account export
(HERE / "statements").mkdir(exist_ok=True)
(HERE / "truth").mkdir(exist_ok=True)
spending.sort(key=lambda s: s["when"])
with open(HERE / "statements/spending_account_export.csv", "w", newline="", encoding="utf-8") as h:
    w = csv.writer(h)
    w.writerow(["ID", "Created", "Title", "Subtitle", "Amount", "Currency", "Categories"])
    for i, s in enumerate(spending):
        w.writerow([f"tx_{i:06d}", s["when"].strftime("%d/%m/%y, %H:%M"), s["title"], s["subtitle"],
                    f"{s['amount']:.2f}", "GBP", s["category"]])

# ---------------------------------------------------------------- write the current-account PDFs
X_DATE, X_DESC, R_OUT, R_IN, R_BAL = 36, 80, 370, 440, 515   # column positions (points); amounts right-aligned
FONT, SIZE, LEAD = "Courier", 8, 11
ROWS_PER_PAGE = 58


def fmt(v):
    return f"{v:,.2f}"


def statement(number, start, end, opening):
    rows = [r for r in current if start <= r["date"] <= end]
    path = HERE / f"statements/Riverside_{end.strftime('%b')}_2026.pdf"
    c = canvas.Canvas(str(path), pagesize=A4)
    width, height = A4
    lines = []   # (date text, description, out, in, balance) - one printed line each
    balance, last_year = opening, None
    for i, r in enumerate(rows):
        first_of_day = i == 0 or rows[i - 1]["date"] != r["date"]
        last_of_day = i == len(rows) - 1 or rows[i + 1]["date"] != r["date"]
        if r["date"].year != last_year:
            lines.append((str(r["date"].year), "", None, None, None, "year"))
            last_year = r["date"].year
        balance = round(balance - (r["out"] or 0) + (r["in"] or 0), 2)
        lines.append((r["date"].strftime("%d %b") if first_of_day else "", r["lines"][0], r["out"], r["in"],
                      balance if last_of_day and not r["lines"][1:] else None, "row"))
        for k, extra in enumerate(r["lines"][1:]):
            is_last = k == len(r["lines"]) - 2
            lines.append(("", extra, None, None, balance if last_of_day and is_last else None, "more"))
    closing = balance

    def page_header(page, carried):
        c.setFont("Helvetica-Bold", 13)
        c.drawString(36, height - 50, "Riverside Building Society")
        c.setFont("Helvetica", 9)
        c.drawString(36, height - 64, "Everyday Current Account  |  Alex Morgan  |  Sort code 00-00-00  Account 00000000 (sample)")
        c.drawRightString(width - 36, height - 50, f"Statement {number}   page {page}")
        c.drawRightString(width - 36, height - 64, f"Statement date {end.strftime('%d %B %Y')}")
        c.setFont(FONT, SIZE)
        y = height - 96
        c.drawString(X_DATE, y, "Date"); c.drawString(X_DESC, y, "Description")
        c.drawRightString(R_OUT, y, "£ Out"); c.drawRightString(R_IN, y, "£ In"); c.drawRightString(R_BAL, y, "£ Balance")
        y -= LEAD * 1.5
        if page == 1:
            prev = start - dt.timedelta(days=1)
            c.drawString(X_DATE, y, str(prev.year if start.month != 1 else start.year))
            c.drawString(X_DESC, y, f"Balance from statement {number - 1} dated {prev.strftime('%d/%m/%Y')}")
            c.drawRightString(R_BAL, y, fmt(opening))
        else:
            c.drawString(X_DATE, y, str(last_year)); c.drawRightString(R_BAL, y, fmt(carried))
        return y - LEAD

    def page_footer():
        c.setFont("Helvetica", 7)
        c.drawString(36, 40, "Please check your statement. Sample document generated for a demonstration; not a real account.")

    page, y = 1, page_header(1, opening)
    running, printed = opening, 0
    for date_text, desc, out, inn, bal, kind in lines:
        if printed == ROWS_PER_PAGE:
            page_footer(); c.showPage(); page += 1; y = page_header(page, running); printed = 0
        if kind == "year":
            c.drawString(X_DATE, y, date_text)
        else:
            c.drawString(X_DATE, y, date_text); c.drawString(X_DESC, y, desc)
            if out is not None: c.drawRightString(R_OUT, y, fmt(out)); running = round(running - out, 2)
            if inn is not None: c.drawRightString(R_IN, y, fmt(inn)); running = round(running + inn, 2)
            if bal is not None: c.drawRightString(R_BAL, y, fmt(bal))
        y -= LEAD; printed += 1
    y -= LEAD
    c.setFont(FONT, SIZE); c.drawString(X_DESC, y, "Closing balance"); c.drawRightString(R_BAL, y, fmt(closing))
    page_footer(); c.save()
    return closing, rows, path


periods = [(dt.date(2026, 8, 12), dt.date(2026, 9, 11)), (dt.date(2026, 9, 12), dt.date(2026, 10, 11)),
           (dt.date(2026, 10, 12), dt.date(2026, 11, 11))]
balance = OPENING
with open(HERE / "truth/current_account.csv", "w", newline="", encoding="utf-8") as h:
    w = csv.writer(h)
    w.writerow(["date", "description", "amount"])
    for n, (s, e) in enumerate(periods, 101):
        balance, rows, path = statement(n, s, e, balance)
        for r in rows:
            w.writerow([r["date"].isoformat(), " | ".join(r["lines"]), round((r["in"] or 0) - (r["out"] or 0), 2)])
        print(f"{path.name}: {len(rows)} transactions, closing {balance:,.2f}")
print(f"spending_account_export.csv: {len(spending)} transactions")
print(f"opening balance {OPENING:,.2f}")
