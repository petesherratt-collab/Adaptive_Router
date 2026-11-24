"""Build the blank bank-statement template (bank_statement_template.xlsx).

    python build_template.py
"""
import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter as L
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import FormulaRule
from openpyxl.comments import Comment

from pathlib import Path
OUT = str(Path(__file__).resolve().parent / "bank_statement_template.xlsx")
ROWS = 3000          # transaction rows with formulas ready
NCAT = 20            # category slots
NMER = 500           # merchant slots
NACC = 3             # accounts
MONTHS = 12
F = "Arial"
base = Font(name=F, size=10); bold = Font(name=F, size=10, bold=True); head = Font(name=F, size=10, bold=True, color="FFFFFF")
title = Font(name=F, size=14, bold=True); blue = Font(name=F, size=10, color="0000FF"); green = Font(name=F, size=10, color="008000")
note = Font(name=F, size=9, italic=True)
hfill = PatternFill("solid", fgColor="1F4E78"); infill = PatternFill("solid", fgColor="FFF2CC"); outfill = PatternFill("solid", fgColor="E2EFDA")
ex = Font(name=F, size=10, color="0000FF", italic=True)
GBP = '£#,##0.00;-£#,##0.00;"-"'; DATE = "dd mmm yyyy"; MON = "mmm yyyy"
thin = Border(top=Side(style="thin"))
wb = Workbook()

def headers(ws, cols, row=1, fill=hfill):
    for i, (h, w) in enumerate(cols, 1):
        c = ws.cell(row, i, h); c.font = head; c.fill = fill; c.alignment = Alignment(wrap_text=True, vertical="center")
        if w: ws.column_dimensions[L(i)].width = w

# ===================== INPUT: Settings =====================
st = wb.create_sheet("Settings")
st.column_dimensions["A"].width = 30; st.column_dimensions["B"].width = 18; st.column_dimensions["C"].width = 22; st.column_dimensions["D"].width = 60
st["A1"] = "Settings and accounts (INPUT)"; st["A1"].font = title
st["A3"] = "First month of the period"; st["A3"].font = bold
c = st["B3"]; c.value = datetime.date(2026, 1, 1); c.number_format = MON; c.font = blue; c.fill = infill
st["D3"] = "Any date in the first month. The summaries cover 12 months from here."; st["D3"].font = note
headers(st, [("Account name", None), ("Opening balance (£)", None), ("Closing balance on last statement (£)", None), ("Notes", None)], row=5)
examples = [("Current", 1200.00, None, "Example — rename to your account, e.g. 'Nationwide'."), ("Spending", 50.00, None, "Example — e.g. 'Monzo'. Leave unused rows blank.")]
for i in range(NACC):
    r = 6 + i
    for j in (1, 2, 3):
        c = st.cell(r, j); c.fill = infill; c.font = blue
        if j > 1: c.number_format = GBP
    if i < len(examples):
        st.cell(r, 1, examples[i][0]); st.cell(r, 2, examples[i][1]); st.cell(r, 4, examples[i][3]).font = note
st["A10"] = "Opening balance: the balance before the first transaction you paste for that account. Closing balance is optional; if given, the Checks sheet compares it."; st["A10"].font = note

# ===================== INPUT: Categories =====================
ca = wb.create_sheet("Categories")
headers(ca, [("Category", 34), ("Counts as spending/income?", 16), ("Notes", 60)])
cats = [("groceries", "Yes"), ("pubs and bars", "Yes"), ("eating out", "Yes"), ("transport", "Yes"), ("bills and utilities", "Yes"),
        ("debt repayments", "Yes"), ("payments to people", "Yes"), ("gambling", "Yes"), ("online shopping and subscriptions", "Yes"),
        ("income", "Yes"), ("other", "Yes"), ("internal transfer", "No")]
for i in range(NCAT):
    r = 2 + i
    for j in (1, 2):
        c = ca.cell(r, j); c.fill = infill; c.font = blue
    if i < len(cats):
        ca.cell(r, 1, cats[i][0]); ca.cell(r, 2, cats[i][1])
ca.cell(2, 3, "Edit, add or remove categories (up to 20). 'No' = left out of totals, e.g. money moved between your own accounts.").font = note
ca.cell(13, 3, "Use for transfers between your own accounts and savings pots, so they are not counted twice.").font = note
dvyn = DataValidation(type="list", formula1='"Yes,No"'); ca.add_data_validation(dvyn); dvyn.add(f"B2:B{NCAT+1}")
CATLIST = f"Categories!$A$2:$A${NCAT+1}"

# ===================== INPUT: Merchants =====================
me = wb.create_sheet("Merchants")
headers(me, [("Merchant (exactly as in Transactions)", 40), ("Category", 30), ("Transactions", 12), ("Money out (£)", 14), ("Money in (£)", 14)])
mex = [("SUPERMARKET STORE", "groceries"), ("EMPLOYER LTD", "income"), ("ENERGY CO", "bills and utilities"), ("Transfer to own account", "internal transfer"), ("Top-up from Current", "internal transfer"), ("CORNER PUB", "pubs and bars")]
dvcat = DataValidation(type="list", formula1=CATLIST); me.add_data_validation(dvcat); dvcat.add(f"B2:B{NMER+1}")
TX = lambda col: f"Transactions!${col}$2:${col}${ROWS+1}"
for i in range(NMER):
    r = 2 + i
    for j in (1, 2):
        c = me.cell(r, j); c.fill = infill; c.font = blue
    if i < len(mex):
        me.cell(r, 1, mex[i][0]).font = ex; me.cell(r, 2, mex[i][1]).font = ex
    c = me.cell(r, 3, f'=IF(A{r}="","",COUNTIF({TX("C")},A{r}))'); c.font = green
    c = me.cell(r, 4, f'=IF(A{r}="","",SUMIFS({TX("E")},{TX("C")},A{r}))'); c.font = green; c.number_format = GBP
    c = me.cell(r, 5, f'=IF(A{r}="","",SUMIFS({TX("F")},{TX("C")},A{r}))'); c.font = green; c.number_format = GBP
me.freeze_panes = "A2"; me.auto_filter.ref = f"A1:E{NMER+1}"

# ===================== INPUT: Transactions =====================
tx = wb.create_sheet("Transactions")
cols = [("Date", 12), ("Account", 12), ("Merchant", 32), ("Details", 36), ("Money out (£)", 13), ("Money in (£)", 13),
        ("Category override (optional)", 22), ("Printed balance (optional)", 14),
        ("Month", 10), ("Category", 26), ("Counted?", 9), ("Running balance (£)", 15), ("Balance check", 11)]
headers(tx, cols)
for j in range(9, 14): tx.cell(1, j).fill = PatternFill("solid", fgColor="375623")
txex = [(datetime.date(2026, 1, 2), "Current", "EMPLOYER LTD", "Bank credit — salary", None, 2000.00, None, 3200.00),
        (datetime.date(2026, 1, 3), "Current", "Transfer to own account", "Transfer to Spending", 100.00, None, None, 3100.00),
        (datetime.date(2026, 1, 3), "Spending", "Top-up from Current", "Faster payment in", None, 100.00, None, 150.00),
        (datetime.date(2026, 1, 4), "Current", "SUPERMARKET STORE", "Contactless Payment", 42.10, None, None, None),
        (datetime.date(2026, 1, 5), "Current", "ENERGY CO", "Direct debit", 85.00, None, None, 2972.90),
        (datetime.date(2026, 1, 6), "Spending", "CORNER PUB", "Card payment", 12.40, None, None, 137.60)]
dvcat2 = DataValidation(type="list", formula1=CATLIST, allow_blank=True); tx.add_data_validation(dvcat2); dvcat2.add(f"G2:G{ROWS+1}")
dvacc = DataValidation(type="list", formula1=f"Settings!$A$6:$A${5+NACC}"); tx.add_data_validation(dvacc); dvacc.add(f"B2:B{ROWS+1}")
for i in range(ROWS):
    r = 2 + i
    for j in range(1, 9):
        c = tx.cell(r, j); c.fill = infill; c.font = blue
        if j == 1: c.number_format = DATE
        if j in (5, 6, 8): c.number_format = GBP
    if i < len(txex):
        for j, v in enumerate(txex[i], 1):
            if v is not None: tx.cell(r, j, v).font = ex
    tx.cell(r, 9, f'=IF(A{r}="","",DATE(YEAR(A{r}),MONTH(A{r}),1))').number_format = MON
    tx.cell(r, 10, f'=IF(A{r}="","",IF(G{r}<>"",G{r},IFERROR(INDEX(Merchants!$B$2:$B${NMER+1},MATCH(C{r},Merchants!$A$2:$A${NMER+1},0)),"uncategorised")))')
    tx.cell(r, 11, f'=IF(A{r}="","",IFERROR(INDEX(Categories!$B$2:$B${NCAT+1},MATCH(J{r},{CATLIST},0)),"Yes"))')
    c = tx.cell(r, 12, f'=IF(A{r}="","",IFERROR(INDEX(Settings!$B$6:$B${5+NACC},MATCH(B{r},Settings!$A$6:$A${5+NACC},0)),0)'
                       f'+SUMIFS(F$2:F{r},B$2:B{r},B{r})-SUMIFS(E$2:E{r},B$2:B{r},B{r}))'); c.number_format = GBP
    tx.cell(r, 13, f'=IF(OR(A{r}="",H{r}=""),"",IF(ABS(L{r}-H{r})<0.005,"ok","MISMATCH"))')
    for j in range(9, 14): tx.cell(r, j).font = base
tx.freeze_panes = "A2"; tx.auto_filter.ref = f"A1:M{ROWS+1}"
red = PatternFill("solid", fgColor="F8CBAD")
tx.conditional_formatting.add(f"M2:M{ROWS+1}", FormulaRule(formula=['M2="MISMATCH"'], fill=red))
tx.conditional_formatting.add(f"J2:J{ROWS+1}", FormulaRule(formula=['J2="uncategorised"'], fill=red))

# ===================== OUTPUT: Monthly summary =====================
su = wb.create_sheet("Monthly summary")
acc = lambda k: f"Settings!$A${6+k}"
cols = [("Month", 11), ("Money in (£)", 14)] + [(None, 15)] * NACC + [("Spent: total (£)", 15), ("Net (£)", 13), ("Internal transfers (£)", 16)]
headers(su, [(h or "", w) for h, w in cols])
for k in range(NACC):
    su.cell(1, 3 + k, f'=IF({acc(k)}="","(unused account)","Spent: "&{acc(k)}&" (£)")').font = head
cnt = f'{TX("K")},"Yes"'
for m in range(MONTHS):
    r = 2 + m
    c = su.cell(r, 1, f"=DATE(YEAR(Settings!$B$3),MONTH(Settings!$B$3)+{m},1)"); c.number_format = MON
    c = su.cell(r, 2, f'=SUMIFS({TX("F")},{TX("I")},$A{r},{cnt})'); c.font = green
    for k in range(NACC):
        c = su.cell(r, 3 + k, f'=IF({acc(k)}="",0,SUMIFS({TX("E")},{TX("I")},$A{r},{cnt},{TX("B")},{acc(k)}))'); c.font = green
    su.cell(r, 3 + NACC, f"=SUM({L(3)}{r}:{L(2+NACC)}{r})")
    su.cell(r, 4 + NACC, f"=B{r}-{L(3+NACC)}{r}")
    c = su.cell(r, 5 + NACC, f'=SUMIFS({TX("E")},{TX("I")},$A{r},{TX("K")},"No")'); c.font = green
    for j in range(2, 6 + NACC): su.cell(r, j).number_format = GBP
t = MONTHS + 2
su.cell(t, 1, "Total").font = bold
for j in range(2, 6 + NACC):
    c = su.cell(t, j, f"=SUM({L(j)}2:{L(j)}{t-1})"); c.font = bold; c.number_format = GBP; c.border = thin
su.cell(t + 2, 1, "Money in and spending leave out categories marked 'No' on Categories (internal transfers). Internal transfers column shows money moved out in those categories.").font = note
su.freeze_panes = "B2"

# ===================== OUTPUT: Category by month =====================
cm = wb.create_sheet("Category by month")
headers(cm, [("Category", 32)] + [("", 11)] * MONTHS + [("Total (£)", 13), ("Share", 8), ("Average per month (£)", 14), ("Counted?", 9)])
for m in range(MONTHS):
    c = cm.cell(1, 2 + m, f"='Monthly summary'!A{2+m}"); c.number_format = MON; c.font = head
TJ = MONTHS + 2
for i in range(NCAT + 1):
    r = 2 + i
    if i < NCAT:
        cm.cell(r, 1, f'=IF(Categories!A{2+i}="","",Categories!A{2+i})').font = green
    else:
        cm.cell(r, 1, "uncategorised").font = base
    for m in range(MONTHS):
        c = cm.cell(r, 2 + m, f'=IF($A{r}="","",IF($A{r}="income",SUMIFS({TX("F")},{TX("J")},$A{r},{TX("I")},{L(2+m)}$1),SUMIFS({TX("E")},{TX("J")},$A{r},{TX("I")},{L(2+m)}$1)-SUMIFS({TX("F")},{TX("J")},$A{r},{TX("I")},{L(2+m)}$1,{TX("K")},"Yes",{TX("J")},"<>income")))')
        c.number_format = GBP; c.font = green
    c = cm.cell(r, TJ, f'=IF($A{r}="","",SUM({L(2)}{r}:{L(TJ-1)}{r}))'); c.number_format = GBP; c.font = bold
    c = cm.cell(r, TJ + 1, f'=IF(OR($A{r}="",$A{r}="income",{L(TJ+3)}{r}="No",N({L(TJ)}{r})=0,N({L(TJ)}${NCAT+4})=0),"",{L(TJ)}{r}/{L(TJ)}${NCAT+4})'); c.number_format = "0.0%"
    c = cm.cell(r, TJ + 2, f'=IF($A{r}="","",{L(TJ)}{r}/{MONTHS})'); c.number_format = GBP
    cm.cell(r, TJ + 3, f'=IF($A{r}="","",IF($A{r}="uncategorised","Yes",IFERROR(INDEX(Categories!$B$2:$B${NCAT+1},MATCH($A{r},{CATLIST},0)),"Yes")))').font = green
tr = NCAT + 4
cm.cell(tr, 1, "Total spending (counted categories, excl. income)").font = bold
for m in range(MONTHS + 1):
    j = 2 + m
    c = cm.cell(tr, j, f'=SUMIFS({L(j)}2:{L(j)}{NCAT+2},$A$2:$A${NCAT+2},"<>income",${L(TJ+3)}$2:${L(TJ+3)}${NCAT+2},"Yes")'); c.number_format = GBP; c.font = bold; c.border = thin
cm.cell(tr + 2, 1, "Each cell = money out minus refunds (money in) in that category and month. The income row shows money in instead, for reference. "
        "The total leaves out income and every category marked 'No' on Categories.").font = note
cm.freeze_panes = "B2"

# ===================== OUTPUT: Checks =====================
ck = wb.create_sheet("Checks")
ck.column_dimensions["A"].width = 52; ck.column_dimensions["B"].width = 16; ck.column_dimensions["C"].width = 60
ck["A1"] = "Checks"; ck["A1"].font = title
rows = [
 ("Transactions entered", f'=COUNT({TX("A")})', "", None),
 ("Rows with no category (add the merchant on Merchants)", f'=COUNTIF({TX("J")},"uncategorised")', "Filter Transactions column J for 'uncategorised'.", None),
 ("Printed balances that do not match the running balance", f'=COUNTIF({TX("M")},"MISMATCH")', "0 means every transaction for that account was pasted, in order.", None),
 ("Rows dated outside the 12-month period", f'=COUNTIFS({TX("A")},"<"&\'Monthly summary\'!A2)+COUNTIFS({TX("A")},">="&DATE(YEAR(\'Monthly summary\'!A13),MONTH(\'Monthly summary\'!A13)+1,1))', "Not included in the summaries.", None),
 ("Spending total: Monthly summary minus Category by month", f"=ROUND('Monthly summary'!{L(3+NACC)}{t}-('Category by month'!{L(TJ)}{tr}+SUMIFS(Transactions!$F$2:$F${ROWS+1},Transactions!$K$2:$K${ROWS+1},\"Yes\",Transactions!$J$2:$J${ROWS+1},\"<>income\")),2)", "Should be 0 (refunds are netted in Category by month).", GBP),
]
for i, (a, f, n, fmt) in enumerate(rows, 3):
    ck.cell(i, 1, a).font = bold; c = ck.cell(i, 2, f); c.fill = outfill
    if fmt: c.number_format = fmt
    ck.cell(i, 3, n).font = note
headers(ck, [("Account", None), ("Calculated closing (£)", None), ("Difference from last statement (£)", None)], row=10)
for k in range(NACC):
    r = 11 + k
    ck.cell(r, 1, f'=IF({acc(k)}="","",{acc(k)})').font = green
    c = ck.cell(r, 2, f'=IF({acc(k)}="","",Settings!$B${6+k}+SUMIFS({TX("F")},{TX("B")},{acc(k)})-SUMIFS({TX("E")},{TX("B")},{acc(k)}))'); c.number_format = GBP
    c = ck.cell(r, 3, f'=IF(OR({acc(k)}="",Settings!$C${6+k}=""),"",ROUND(B{r}-Settings!$C${6+k},2))'); c.number_format = GBP
ck.cell(15, 1, "A difference of 0 means the statements and your pasted transactions agree.").font = note

# ===================== Read me =====================
rm = wb["Sheet"]; rm.title = "Read me"
rm.column_dimensions["A"].width = 26; rm.column_dimensions["B"].width = 100
rm["A1"] = "Bank statement workbook"; rm["A1"].font = title
rm["A2"] = "Paste your transactions; the summaries fill themselves in. Works for one to three accounts."; rm["A2"].font = base
steps = [
 ("INPUTS (yellow cells)", ""),
 ("1. Settings", "First month of the period; each account's name and opening balance (and, optionally, the closing balance on its last statement)."),
 ("2. Categories", "The category list and whether each counts as spending/income. Keep 'internal transfer' marked 'No'."),
 ("3. Transactions", "Paste one row per transaction into columns A–F: date, account (as named on Settings), merchant, details, money out, money in (positive numbers). "
                     "G overrides the category for one row. H is the balance printed on the statement, if you want it checked. Keep each account's rows in statement order."),
 ("4. Merchants", "One row per merchant name, exactly as it appears in Transactions, with its category. A merchant missing here shows as 'uncategorised'."),
 ("OUTPUTS (calculated)", ""),
 ("Monthly summary", "Money in, spending per account, total, net and internal transfers, for 12 months."),
 ("Category by month", "Spending per category per month (refunds netted), totals, shares and monthly average."),
 ("Checks", "Uncategorised rows, balance mismatches, rows outside the period, and each account's calculated closing balance against its last statement."),
 ("Transactions I–M", "Month, category, whether counted, running balance per account and balance check, worked out per row."),
 ("Colours", "Yellow fill / blue text = input · green text = pulled from another sheet · black = calculated · red fill = needs attention."),
 ("Example data", "The italic rows on Settings, Merchants and Transactions are examples showing the format. Delete or overwrite them."),
 ("Limits", f"{ROWS:,} transaction rows, {NMER} merchants, {NCAT} categories, {NACC} accounts, 12 months. Money amounts are positive in both columns."),
]
for i, (a, b) in enumerate(steps, 4):
    rm.cell(i, 1, a).font = bold if b else Font(name=F, size=11, bold=True, color="1F4E78")
    c = rm.cell(i, 2, b); c.font = base; c.alignment = Alignment(wrap_text=True, vertical="top")
    if len(b) > 100: rm.row_dimensions[i].height = 28 * (len(b) // 100 + 1) / 2 + 14

order = ["Read me", "Settings", "Categories", "Transactions", "Merchants", "Monthly summary", "Category by month", "Checks"]
wb._sheets = [wb[n] for n in order]
for n in ("Settings", "Categories", "Transactions", "Merchants"): wb[n].sheet_properties.tabColor = "FFC000"
for n in ("Monthly summary", "Category by month", "Checks"): wb[n].sheet_properties.tabColor = "70AD47"
wb.save(OUT); print("saved", OUT)
