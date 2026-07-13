# Dialogue Syntax Experiment State

Updated: 2026-07-13

## Current position

- Working branch: `codex/dialogue-syntax-stabilize`
- Parent experiment branch: `experiment/dialogue-syntax-bert` at `e930c03`
- Phase 0 commit: `438bf95` (`Stabilize dialogue syntax experiment state`)
- Current stage: Phase 1, external-validation annotation handoff
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

## Phase 0 result

Phase 0 is complete:

1. the 31 previously untracked experiment scripts are versioned;
2. 54 compact frozen artifacts are versioned with SHA-256 hashes;
3. the project Skill is valid;
4. the reproducibility checker passed all historical-state checks.

## Frozen external-validation selection

- Total: 800 new pairs.
- Development annotation packet: 600 pairs.
- Dataset-disjoint external holdout: 200 pairs.
- Independent second-annotator overlap: 180 development pairs and 60 holdout pairs.
- Strata: 240 rule positive, 160 random rule negative, 160 hard/boundary, 160 potential false negative, 80 analogy/parallel candidates.
- The external holdout covers daily, text, film/television, interview, and network sources.
- All existing 300 gold pairs, their normalized hashes, and 294 existing conversation groups were excluded.
- No human labels are present yet. The holdout remains sealed.

## Required next action

Send the primary blind packets to annotator A and the overlap packets to a genuinely independent annotator B. Neither annotator may see `selection_key.csv`, the private rule key, model outputs, or the other annotator's labels. Run agreement scoring before adjudication. Do not train or tune on the external holdout.

## Integration rule

Do not modify the website merely because the historical hybrid score is promising. Website work begins with an offline wrapper and batch shadow logs only after the confirmatory pair-level gate passes. User-visible ranking remains a later, separately authorized gate.
