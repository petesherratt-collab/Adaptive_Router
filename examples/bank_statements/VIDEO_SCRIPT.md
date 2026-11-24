# Video plan: bank statements to a self-checking spreadsheet

**Length:** about 8–10 minutes.
**What you show:** only the synthetic data in this folder (Alex Morgan, Riverside Building Society). Keep your real statements and spreadsheet off screen.

**Before recording, open these:**

1. A Riverside statement PDF (`statements/Riverside_Sep_2026.pdf`).
2. The app export, in a spreadsheet or text editor (`statements/spending_account_export.csv`).
3. The blank template (`bank_statement_template.xlsx`).
4. The filled template (`stages/4_filled_template.xlsx`).
5. A terminal in the repository root.
6. The explainer page, for the closing shot.

---

## Title ideas

- I turned my bank statements into a spreadsheet that checks itself
- PDF bank statements → one spreadsheet (free template)
- Where does my money actually go? Two bank accounts, one spreadsheet

## Thumbnail

On the left, the statement page image (`media/statement_page-1.png`), tilted slightly. On the right, the green "Category by month" tab, with "rent 40%" visible. An arrow between them.

---

## 0:00 Hook (20–30 s)

**Shot:** The filled template's Category by month tab, then the bars on the explainer page.

**Say:** "Two bank accounts, three months of statements, and one question: where does the money actually go? By the end of this you'll have a spreadsheet that answers it, and checks its own arithmetic against the bank's. The template's free; link below."

## 0:30 The problem (60 s)

**Shot:** The statement PDF, zoomed in.

**Say:**
- "Statements are written for people, not spreadsheets."
- Point at a date that appears only once for several lines.
- Point at "Contactless Payment" with the shop name on the next line.
- Point at a balance printed only once a day.
- Point at the foreign purchase with its separate fee line.
- "And most people have more than one account. Every top-up from your main account to your spending account shows up twice, once going out and once coming in. Count both and you've 'spent' money you only moved."

## 1:30 What you'll get (45 s)

**Shot:** The blank template. Click through the tabs: Read me, then the yellow tabs, then the green tabs.

**Say:**
- "Yellow tabs are what you fill in: settings, categories, transactions and merchants. Green tabs fill themselves in: a monthly summary, spending by category, and checks."
- "You don't need any code to use this. You can paste transactions straight in."

## 2:15 Stage 1: reading the PDFs (90 s)

**Shot:** The terminal, running `python examples/bank_statements/run_pipeline.py`. Pause on the stage 1 lines.

**Say:**
- "The reader places each line in its column by position, carries the date down to the lines below it, and joins each shop name to its payment."
- "Here's the bit I like. Every balance the bank printed gets recomputed from the opening balance plus each transaction. If one transaction is missed or misread, the balances stop agreeing, and you'd see it here."
- Show `stages/1_current_account_extracted.csv` next to the PDF and match two or three lines.

## 3:45 Stage 2: two accounts, no double counting (60 s)

**Shot:** `stages/2_combined.csv` filtered to 13 Aug, or the stage 2 table on the explainer page.

**Say:**
- "The £50 'Transfer to A Morgan' leaving the current account is paired with the £50 'MORGAN ALEX' arriving in the spending account: same amount, within three days. Both copies get marked internal, so they don't count as spending or income."
- "Forty-three transfers in three months, all paired."

## 4:45 Stage 3: categories (60 s)

**Shot:** The `RULES` list in `run_pipeline.py`, then the Merchants tab.

**Say:**
- "Each merchant gets one category from a short list of rules. Morrisons, Tesco and Lidl mean groceries; Wetherspoon means pubs."
- "This is where your judgement matters. In the spreadsheet every category is a drop-down. Change one, and every total follows." Do it live: move a merchant to a different category and show Category by month update.

## 5:45 Stage 4: the answers (90 s)

**Shot:** The filled template: Monthly summary, then Category by month, then Checks.

**Say:**
- Monthly summary: "Money in, spent per account, net. August and November are part-months, because the statements run from the 12th to the 11th."
- Category by month: "Rent is 40% of spending. Groceries come next at 21%. Pubs are 11%."
- Checks: "Zero uncategorised, zero balance mismatches. And the total, £6,791.59, matches a count I took straight from the data."

## 7:15 What testing with known answers caught (60–75 s)

**Shot:** The "What testing with known answers found" section of the explainer page.

**Say:**
- "Here's why I used made-up statements. Because I generated the data, I knew the right answer for every line."
- "The balance check passed. Every amount was right. But comparing against the known answers showed that on 35 lines the shop name had gone missing. That happens when a bank prints the balance on the same line as the shop name, and balances can't catch it."
- "The second bug: purchases on the first day of the statement were dropped, because that day had nothing on the main account. That was £17.08."
- "Both are fixed. The lesson: test with data where you already know the answer."

## 8:30 Close (30 s)

**Shot:** The explainer page, scrolled to "Get the files".

**Say:** "The blank template, the sample statements and the code are all linked below. If your bank's PDF looks different, the reader may need adjusting, but the template works with any bank. You just paste the rows."

---

## Description (paste into YouTube)

```
Turn PDF bank statements and a banking-app export into one spreadsheet that adds itself up and checks its own arithmetic.

Free template + sample files (all synthetic data):
https://github.com/petesherratt-collab/Adaptive_Router/tree/main/examples/bank_statements

Written walkthrough: <paste your explainer page link after sharing it>

0:00 Where does the money go?
0:30 Why statements are hard to read automatically
1:30 The template: yellow in, green out
2:15 Reading the PDFs, and checking every balance
3:45 Two accounts without double counting
4:45 Categories
5:45 The answers
7:15 What testing with known answers caught
8:30 Get the files

All names, accounts and amounts in this video are invented. Not financial advice.
```

## Before you publish

- [ ] **Explainer page sharing.** It is private until you share it from its Share menu.
- [ ] **Your own data.** Check every frame for your real statements, spreadsheet, notifications or browser tabs.
