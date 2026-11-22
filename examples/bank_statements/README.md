# Bank statements to a spreadsheet

Turn PDF bank statements and an app's CSV export into one spreadsheet that
adds itself up. All the data in this folder is **synthetic**: Alex Morgan,
Riverside Building Society, the employer, the landlord and the billers are
invented.

| File | What it is |
|---|---|
| `bank_statement_template.xlsx` | **The template.** It is blank apart from a few example rows. You fill in the yellow input tabs (Settings, Categories, Transactions, Merchants) and the green tabs calculate. |
| `statements/` | Three monthly current-account statements (PDF) and a spending-account export (CSV), all synthetic. |
| `stages/` | The output of each pipeline stage, ending with `4_filled_template.xlsx`. |
| `WALKTHROUGH.md` | Each stage explained, with excerpts. |
| `make_synthetic.py` | Regenerates the synthetic statements. It also writes `truth/`, the true transaction list, which is used to check the extraction. |
| `run_pipeline.py` | PDFs + CSV → combined table → categorised rows → filled template. |
| `build_template.py` | Rebuilds the blank template. |

## Running it

From the repository root:

```
pip install reportlab openpyxl
python examples/bank_statements/make_synthetic.py
python examples/bank_statements/run_pipeline.py
```

`pdftotext` (poppler-utils) must be installed. The PDF reader in
`statement_pdf.py` is written for one statement layout: date, description,
out, in and balance columns, with the balance printed once a day. Other banks'
layouts may need adjusting.

## Using the template with your own data

You don't need the pipeline. Paste your transactions into the Transactions tab
(date, account, merchant, details, money out, money in), list your merchants
with a category each on Merchants, and set your opening balances on Settings.
The Checks tab tells you if anything doesn't add up.
