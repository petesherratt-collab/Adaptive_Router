# Real task V1: categorising the owner's bank transactions

**Status:** FROZEN 2026-11-21 before any provider call. **Scope:** the first
run on real work (roadmap phase D), on the owner's own Monzo export. The owner
agreed to send the data to the model providers; the export and any per-merchant
output stay out of the repository (`real_tasks/private/`, git-ignored), and
only aggregate figures are committed.

## Data

4,166 transactions, 2025-03-05 to 2026-11-21, every one with Monzo's own
category (13 in use), used as the correct answer. Training: before 2026-03-01
(2,232 transactions). Test: from 2026-03-01 (1,934 transactions, 95 merchant
titles, 59 not seen in training, covering 303 test transactions).

## Arms (`real_bank_categorise_v1.py`), scored per test transaction

- E, code only: the training table (merchant title to its most common
  category); unseen merchants get `general`. No model.
- M, models only: the five-model race reads the merchant title and picks one
  of Monzo's 13 categories; raced once per title, first usable answer wins.
- H, hybrid: the training table, unseen titles to the race.
- H2, hybrid that keeps learning: as H, but each test transaction's Monzo
  category joins the table once seen; only a title's first appearance goes to
  the race.

## Readings fixed in advance

Accuracy against Monzo per arm; transactions needing a model; median time per
transaction (a table lookup counts as 0 ms); race agreement per title.
Expected, stated now: E and H2 near the top and near-instant; M clearly less
accurate, because a merchant's name does not always say what Monzo files it
under; H2 the best of the four. Ceiling for any table-based arm: about 15 test
transactions are filed differently from their merchant's usual category.

Expected cost: under $0.50 (475 short calls). No significance test: one
person's data, descriptive by nature.

## Result (2026-11-21)

Code only 84.6%; models only 63.6%; hybrid 94.9% (a model for 16% of
transactions); learning hybrid 94.1% (a model for 3%, 39 ms mean). Models
alone miss the owner's and Monzo's filing conventions. Cost $0.25.
