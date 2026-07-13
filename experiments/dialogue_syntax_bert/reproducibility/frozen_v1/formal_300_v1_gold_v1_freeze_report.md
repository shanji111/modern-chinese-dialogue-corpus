# formal_300_v1 gold_v1 freeze report

## Source

formal_300_v1_gold_v1 is frozen from formal_300_v1_gold_candidate_v3 after pilot calibration, formal 300 annotation, top30 review, round2 targeted review, and final sanity check.

## Process

1. Pilot 50 established blind annotation, rule key separation, boundary principles, and rule evaluation flow.
2. Formal 300 v1 sampled adjacent dialogue pairs with stratified sources and retained evaluation keys for rule analysis.
3. AI-assisted full annotation was validated and then corrected for evidence span issues.
4. Top30 review applied high-priority manual decisions to create gold_candidate v1.
5. Round2 targeted review checked remaining high-risk false negatives and preserved the candidate labels.
6. Final sanity check reviewed 12 freeze-critical samples. The changed row count was 0/12, satisfying the freeze criterion of <= 2/12.

## gold_v1 distribution

- yes: 228
- no: 58
- uncertain: 14
- total: 300

## gold_v1_binary distribution

- yes: 228
- no: 58
- total: 286

## Why uncertain stays in master gold

Uncertain rows preserve documented boundary cases such as context loss, malformed or mismatched dialogue, pure stance alignment, and unstable analogy/selection cases. They remain useful for audit and future guideline refinement, but binary training/evaluation should exclude them to avoid teaching the model unstable labels.

## Why this can enter baseline / BERT stage

The dataset has passed structural validation, evidence-span validation, staged review, final sanity check, and freeze threshold checks. The frozen master file can support descriptive analysis, while the binary export provides a clean yes/no subset for baseline and later BERT experiments.

## Limitations

- This is still a 300-row dataset and should be treated as v1 seed gold, not a final broad-coverage benchmark.
- False negatives remain numerous for semantic selection, slot filling, short answers, and reference-based resonance; model experiments should report these categories separately.
- analogy_candidate is retained as an experimental label and should not enter core binary F1.
- The binary file excludes uncertain rows by design.

## Validation snapshot

- gold_candidate_v3 issues: 0
- gold_v1 rows: 300
- gold_v1_binary rows: 286
- binary validation issues: 0
