# From bank statements to the template: a worked example

Everything here is **synthetic**. Alex Morgan, Riverside Building Society, the employer, the landlord and the billers are invented. The finances have the same shape as a real two-account setup:

- weekly wages go into a current account;
- rent, bills and a debt repayment go out of it;
- frequent top-ups go to a spending account (Monzo-style), where day-to-day spending happens.

The period is three monthly statements, 12 Aug to 11 Nov 2026.

To rebuild every file here:

```
python make_synthetic.py   # writes the statements (and a truth file for checking)
python run_pipeline.py     # stages 1 to 4
```

No AI model is used anywhere in this pipeline. Every step is ordinary code, so the same statements always give the same workbook.

## Stage 0: what you start with

**Three current-account statements as PDFs** (`statements/Riverside_*.pdf`). This is how one page reads as text:

```
2026         Balance from statement 100 dated 11/08/2026                                                               912.40
2026
13 Aug       Contactless Payment                                                                   3.68
             WORKPLACE CANTEEN THURROCK
             Contactless Payment                                                                  24.12
             WM MORRISONS STORE DARTVILLE
             Transfer to A Morgan                                                                 50.00                834.60
14 Aug       Bank credit ACME LOGISTICS LTD                                                               566.23
             REF 4471 0092
             Contactless Payment                                                                   3.24
             WORKPLACE CANTEEN THURROCK                                                                              1,397.59
15 Aug       Direct debit RIVERSIDE BORO COUNCIL                                              138.00
             Transfer to A Morgan                                                             100.00                 1,159.59
16 Aug       Contactless Payment                                                               22.40
             WM MORRISONS STORE DARTVILLE
             Contactless Payment                                                                   3.47
```

Things that make these statements awkward to read automatically:

- A date appears only on the first transaction of each day.
- The shop name sits on the line below "Contactless Payment".
- The balance is printed only once a day.
- A foreign-currency purchase brings an exchange-rate line and a separate fee line.

**The spending account's app export as CSV** (`statements/spending_account_export.csv`), with 227 transactions:

```
ID,Created,Title,Subtitle,Amount,Currency,Categories
tx_000000,"12/08/26, 15:14",Transport for London,,-5.84,GBP,transport
tx_000001,"12/08/26, 20:01",Wetherspoon,The Moon and Lantern,-11.24,GBP,eating_out
tx_000002,"13/08/26, 09:38",MORGAN ALEX,Sent from Riverside,50.00,GBP,transfers
tx_000003,"13/08/26, 11:49",Transport for London,,-5.83,GBP,transport
tx_000004,"13/08/26, 12:37",Wetherspoon,The Moon and Lantern,-11.31,GBP,eating_out
tx_000005,"14/08/26, 11:27",Sky Bet,,-10.00,GBP,entertainment
tx_000006,"14/08/26, 13:20",The Red Lion,,-10.15,GBP,entertainment
```

## Stage 1: read the PDFs (`statement_pdf.py`)

Each line of the PDF text is placed in its column by position. Dates carry forward to the lines below them, and shop names are joined to their payments.

**Check:** every balance printed on a statement is recomputed from the opening balance plus every transaction up to that point. All 3 statements reconcile, and each opens at the previous one's close. The result is 170 transactions in `stages/1_current_account_extracted.csv`:

| date | kind | merchant | amount | balance |
|---|---|---|---|---|
| 2026-08-13 | Contactless Payment | WORKPLACE CANTEEN THURROCK | -3.68 |  |
| 2026-08-13 | Contactless Payment | WM MORRISONS STORE DARTVILLE | -24.12 |  |
| 2026-08-13 | Transfer to | A Morgan | -50.0 | 834.6 |
| 2026-08-14 | Bank credit | ACME LOGISTICS LTD | 566.23 |  |
| 2026-08-14 | Contactless Payment | WORKPLACE CANTEEN THURROCK | -3.24 | 1397.59 |
| 2026-08-15 | Direct debit | RIVERSIDE BORO COUNCIL | -138.0 |  |

**Second check:** because these statements are synthetic, the true list exists (`truth/current_account.csv`). The extraction matches it on all 170 lines: date, amount and description.

## Stage 2: combine the accounts (`combine_statements.py`)

The two accounts are merged over the statement period. Money Alex moves between their own accounts must not count as spending.

- **How a transfer is spotted:** "Transfer to A Morgan" on the current account is paired with "MORGAN ALEX", the same amount arriving in the spending account within 3 days.
- **What happens to it:** each pair is marked internal. So are moves into a savings pot.
- **Result:** 43 transfers paired, none left unpaired.

One day, 13 Aug, from `stages/2_combined.csv`. The £50 transfer appears on both accounts, and both copies are marked internal:

| date | account | merchant | amount | internal |
|---|---|---|---|---|
| 2026-08-13 | main | WORKPLACE CANTEEN THURROCK | -3.68 | no |
| 2026-08-13 | main | WM MORRISONS STORE DARTVILLE | -24.12 | no |
| 2026-08-13 | main | A Morgan | -50.0 | yes |
| 2026-08-13 | monzo | MORGAN ALEX | 50.0 | yes |
| 2026-08-13 | monzo | Transport for London | -5.83 | no |
| 2026-08-13 | monzo | Wetherspoon | -11.31 | no |

## Stage 3: put each row in the template's shape and categorise

**Rows:** each row becomes the template's eight input columns (A to H). Internal transfers get the category override "internal transfer". Current-account rows keep the printed balance, so the template can check it.

**Merchants:** each merchant gets one category from a short rules table in `run_pipeline.py`. The first rule whose words appear in the merchant's name wins. All 25 merchants were matched, and none fell through to "other".

`stages/3_transactions_for_template.csv`, first rows, 397 in total:

| Date | Account | Merchant | Details | Money out | Money in | Category override | Printed balance |
|---|---|---|---|---|---|---|---|
| 2026-08-12 | Spending | Transport for London | transport | 5.84 |  |  |  |
| 2026-08-12 | Spending | Wetherspoon | The Moon and Lantern | 11.24 |  |  |  |
| 2026-08-13 | Riverside | WORKPLACE CANTEEN THURROCK | Contactless Payment | WORKPLACE CANTEEN THURROCK | 3.68 |  |  |  |
| 2026-08-13 | Riverside | WM MORRISONS STORE DARTVILLE | Contactless Payment | WM MORRISONS STORE DARTVILLE | 24.12 |  |  |  |
| 2026-08-13 | Riverside | A Morgan | Transfer to A Morgan | 50.00 |  | internal transfer | 834.6 |
| 2026-08-13 | Spending | MORGAN ALEX | Sent from Riverside |  | 50.00 | internal transfer |  |

`stages/3_merchants.csv`, which becomes the Merchants sheet:

| Merchant | Category |
|---|---|
| ACME LOGISTICS LTD | income |
| Amazon | online shopping and subscriptions |
| BRIGHTSPARK ENERGY | bills and utilities |
| CREDITLINE RECOVERIES | debt repayments |
| Cheque deposit | income |
| Foreign currency transaction fee | online shopping and subscriptions |
| GREGGS PLC DARTVILLE | eating out |
| Greggs | eating out |
| J PATEL | rent |
| LEARNWELL ONLINE LONDON | online shopping and subscriptions |
| Lidl | groceries |
| McDonald's | eating out |
| Morrisons | groceries |
| NETFLIX.COM 866-579-7172 | online shopping and subscriptions |
| PIXELHOST.IO TALLINN | online shopping and subscriptions |
| RIVERSIDE BORO COUNCIL | bills and utilities |
| Sky Bet | gambling |
| Tesco | groceries |
| The Red Lion | pubs and bars |
| Transport for London | transport |
| VOXTEL MOBILE | bills and utilities |
| WM MORRISONS STORE DARTVILLE | groceries |
| WORKPLACE CANTEEN THURROCK | eating out |
| Wetherspoon | pubs and bars |
| eBay | online shopping and subscriptions |

## Stage 4: fill the template's inputs (`stages/4_filled_template.xlsx`)

The pipeline writes only the yellow input cells:

| Input sheet | What gets written |
|---|---|
| Settings | The first month (Aug 2026), plus two accounts: Riverside with its opening balance from the first statement, and Spending, whose export has no balance |
| Categories | The template's list, plus one new category, "rent" |
| Transactions | The 397 rows from stage 3 |
| Merchants | The 25 merchants and their categories |

Every output then calculates from those inputs.

**Checks sheet**

- Transactions entered: **397**
- Rows with no category (add the merchant on Merchants): **0**
- Printed balances that do not match the running balance: **0**
- Rows dated outside the 12-month period: **0**
- Spending total: Monthly summary minus Category by month: **0**

**Monthly summary** (August and November are part-months)

| Month | Money in | Spent: Riverside | Spent: Spending | Spent: total | Net |
|---|---|---|---|---|---|
| Aug 2026 | £1,752.22 | £560.75 | £407.34 | £968.09 | £784.13 |
| Sep 2026 | £2,600.28 | £1,694.20 | £480.82 | £2,175.02 | £425.26 |
| Oct 2026 | £2,988.54 | £1,655.11 | £576.92 | £2,232.03 | £756.51 |
| Nov 2026 | £600.42 | £1,204.81 | £211.64 | £1,416.45 | £-816.03 |
| **Total** | **£7,941.46** | **£5,114.87** | **£1,676.72** | **£6,791.59** | **£1,149.87** |

**Category by month**, totals

| Category | Total | Share |
|---|---|---|
| rent | £2,685.00 | 39.6% |
| groceries | £1,421.79 | 21.0% |
| bills and utilities | £824.04 | 12.2% |
| pubs and bars | £771.41 | 11.4% |
| debt repayments | £300.00 | 4.4% |
| online shopping and subscriptions | £271.29 | 4.0% |
| eating out | £240.69 | 3.6% |
| transport | £218.87 | 3.2% |
| gambling | £40.00 | 0.6% |

**Cross-check:** total spending, £6,791.59, matches a count made directly from the generator's own lists. That count includes the £18.50 eBay refund, which appears as money in.

## Two parser fixes this example found

Reconciling balances proves the amounts are right. It cannot prove the shop names are right, or that no day was dropped. The truth file can, and it found two problems:

1. **Shop names lost when the balance shares their line.** Some layouts print the day's balance on the same line as the shop name. The parser had attached the balance and dropped the name, on 35 of the 170 rows. It now keeps both. A "Closing balance" line is also skipped rather than read as part of a shop name.
2. **First-day purchases dropped.** Combining started the shared period at the current account's first transaction (13 Aug), which lost two spending-account purchases on 12 Aug, £17.08 in all. The statement period can now be passed in.

Neither problem changes the result for the real statements this was built on. Their output is byte-for-byte the same.
