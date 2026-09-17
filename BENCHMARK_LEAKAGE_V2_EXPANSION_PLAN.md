# Benchmark Leakage Controls v2 — Expansion Plan

Status: **DRAFT — NO MODEL EXECUTION AUTHORIZED**

This expands the completed v1 pilot in both requested dimensions: a fresh
20-variant bundle and three local model strata. V1 evidence remains immutable
and is not reused for task content, oracle construction, or scoring.

## Scope

- 10 fresh task IDs;
- `base` and `mut1` variants for every task ID;
- 20 task variants total;
- 3 repetitions per variant and condition;
- models: `gemma3:270m`, `gemma3:1b`, `gemma3:4b`;
- conditions: ordinary model and `input_removed` / `input_shuffled` ablations;
- 180 ordinary model observations and 360 ablation observations;
- null baselines run offline before any model call.

The 10 task IDs cover structured extraction, sentiment/priority
classification, bullet and label formatting, JSON formatting, and deterministic
transformation. Classification and transformation findings remain separate
from any validator-effectiveness claim.

## Required freeze order

1. Review fresh tasks, oracle values, and mutants.
2. Run null baselines through the shared oracle and normalization path.
3. Redesign or exclude any task with `CV_NULL_BASELINE_PASSES`.
4. Authenticate all task/oracle/control hashes and model identities.
5. Freeze repetitions, output paths, budgets, and model order in a committed
   execution plan.
6. Run each model once in order `270m`, `1b`, `4b`.
7. Run analysis only after all model and ablation rows reconcile.

No model request is allowed while this document remains `DRAFT`.

## Interpretation boundary

The expansion measures raw and normalized oracle correctness, normalization
dependence, null-baseline defeat, ablation failure, and base/mutant agreement.
It does not establish semantic correctness, eliminate false acceptance, or
generalize to unseen tasks. A model pass is not an operational routing gate.
