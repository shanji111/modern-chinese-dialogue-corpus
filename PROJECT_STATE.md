# Dialogue Syntax Experiment State

Updated: 2026-07-13

## Current position

- Working branch: `codex/dialogue-syntax-stabilize`
- Parent experiment branch: `experiment/dialogue-syntax-bert` at `e930c03`
- Current stage: Phase 0, reproducibility stabilization
- Production website integration: not started
- Production database mutation: prohibited

## Frozen historical evidence

- Pair annotation set: 300 rows; yes 228, no 58, uncertain 14.
- Binary pair set: 286 rows; train 200, dev 43, historical test 43.
- Rule historical-test macro-F1: 0.641667.
- MacBERT five-seed historical-test macro-F1: 0.745341 +/- 0.047293.
- Recommended historical hybrid: `rule_priority_with_bert_recall`; macro-F1 0.779487, balanced accuracy 0.815359.
- Column gold: 50 positive pairs, 151 reviewed rows, 135 active columns.
- Column candidate pool: relaxed F1 0.497561, core recall 0.313131.
- Frozen MacBERT heuristic filtering did not beat the unfiltered candidate pool.

These are development-history results, not final external-validation claims.

## Active gate

Phase 0 is complete only when:

1. all experiment scripts required to reproduce the work are tracked;
2. the compact frozen snapshot and SHA-256 manifest are tracked;
3. the project-state checker passes;
4. a clean external-validation protocol and blind annotation tooling exist.

## Next scientific stage

Create a new source- and dataset-grouped sample that excludes every existing gold pair and conversation group. Freeze the sample before annotation. Use two genuinely independent human annotations for a documented subset, calculate agreement before adjudication, and keep the external holdout sealed until all model and threshold choices are frozen.

## Integration rule

Do not modify the website merely because the historical hybrid score is promising. Website work begins with an offline wrapper and batch shadow logs only after the confirmatory pair-level gate passes. User-visible ranking remains a later, separately authorized gate.
