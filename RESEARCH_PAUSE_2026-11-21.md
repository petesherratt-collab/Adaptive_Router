# Fast-path line: paused 2026-11-21, restarted 2026-11-25

**Restarted 2026-11-25.** A real repeated task now exists: the owner's
`change-signals` repository polls 51 company web pages daily and labels each change
through this router (step A, "is it cosmetic?", on the fast path with learning on;
step B, "buy, sell or irrelevant?", raced and decided by majority). Its router
measures and a criterion read on 2027-01-05 were frozen in that repository's
`AMENDMENT_1.md`. Development continues here at Phase B of `ROADMAP.md`.

**Status before the restart:** paused, not closed. It restarts if the owner has a real task they
repeat often enough to measure (see "What would restart it").

## The bounded claim

When a task's shape repeats and most of the work is computation, writing the
whole job as code once beats racing models on every request. Adoption is by
execution against answers the models agreed on, and no model judges.

- **Single steps** became code that answered about 40 to 90 times faster than
  one model call. Shown prospectively on easy and hard step shapes.
- **Whole jobs, written once:**
  - On unseen jobs with test inputs it took 0.50 of the race's time and was
    2.1 points more accurate (V5, prospective).
  - One earlier prospective run failed on a rounding rule (V4).
- **Real data:** the owner's Monzo export, 4,166 transactions, sorted into
  categories.
  - Code plus the agreed model answers got 94.9% right.
  - Code alone got 84.6% and models alone 63.6%.
  - A model was needed for 3% to 16% of transactions.

## Where it stops working

- **Jobs needing many separate readings of text.**
  - Write-once loses its speed edge (1.11 of the race's time).
  - Batching the readings cut model calls to a seventh, but it was no faster
    and lost 3.8 points.
- **Models planning the steps** did worst every time (superseded).
- **Flagging disagreement is useful:** 94% of unflagged answers were right
  against 18% of flagged ones. It was never measured on its own for time.

## Why pause

The method pays off only on a task that repeats. The owner's real data (two
bank accounts, combined and reconciled; see README) gave useful one-off
answers through `ask_statement.py`. Those questions are not repeated, though,
and a monthly statement is too rare to need the router. Phases B and C of
`ROADMAP.md` would only refine results on made-up benchmarks.

## State at pause

- **Current path:** write once (`main.py --task-json`).
- **Defaults:** `uncertainty_gate` is on; batching and narrow racing are off.
  The gate waits for a second answer, so it costs some time. That cost was not
  measured separately.
- **Tools kept for the owner's use:**
  - `ask_statement.py`: plain-English questions about a statement.
  - `statement_pdf.py`: reads Nationwide PDF statements and reconciles them.
  - `combine_statements.py`: merges the main account with Monzo.
- **Data:** everything personal stays in the git-ignored `real_tasks/private/`.

## What would restart it

A task that:

- arrives many times (daily or more);
- has the same shape each time;
- has answers that can be checked later.

Examples: a daily feed read and classified the same way, or a forecasting or
paper-trading log scored against what actually happened.

When one exists, restart at Phase B of `ROADMAP.md` on that task.
