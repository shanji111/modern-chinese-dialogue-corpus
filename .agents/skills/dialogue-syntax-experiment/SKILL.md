---
name: dialogue-syntax-experiment
description: Run, audit, freeze, and advance the modern-Chinese dialogue-syntax BERT experiment. Use for pair sampling, blind annotation, leakage-safe splitting, rule or MacBERT evaluation, column-gold work, reproducibility checks, experiment-state recovery, and gated website-shadow planning in this repository.
---

# Dialogue Syntax Experiment

## Begin every run

1. Read `AGENTS.md`, `PROJECT_STATE.md`, and `experiments/dialogue_syntax_bert/EXPERIMENT_REGISTRY.json`.
2. Inspect the current branch and `git status --short`; preserve unrelated changes.
3. Identify the active stage and confirm that its prerequisite gate is passed.
4. Treat `corpus.db` as read-only production data.

## Route the task

- For freezing, hashing, reproduction, or state recovery, read `references/artifact-policy.md` and run the bundled state checker.
- For sampling, confirmatory human annotation packets, agreement, adjudication, or external holdout work, read `references/annotation-protocol.md`.
- For AI-assisted exploratory annotation, read `references/ai-exploration-protocol.md` and validate every run with `scripts/validate_ai_exploration_annotations.py`.
- For column generation or website work, read `references/stage-gates.md` and stop if the prerequisite gate is not passed.

## Execute safely

- Create new versioned outputs; never overwrite frozen gold or completed human annotation.
- Keep `pair_id`, `normalized_pair_hash`, and `conversation_group_key` disjoint across splits.
- Tune only on training/development data. Keep any confirmatory holdout sealed; an AI exploratory holdout is descriptive and must not be used for tuning.
- Preserve model, prompt, run, confidence, and review-status provenance on every AI row. AI drafts are never gold and never count as independent-human agreement.
- Preserve rules as the interpretable path. Use BERT for pair scoring or candidate keep/filter unless a later approved experiment changes the scope.
- Do not edit website routes, ranking, deployment, migrations, or production data during offline stages.

## Validate and close

Run:

```powershell
python -B .\.agents\skills\dialogue-syntax-experiment\scripts\check_project_state.py --repo-root .
```

For a new double-annotation batch, run the agreement script before adjudication:

```powershell
python -B .\.agents\skills\dialogue-syntax-experiment\scripts\score_annotation_agreement.py `
  --annotator-a <a.csv> --annotator-b <b.csv> --output-dir <report-dir>
```

For an AI exploratory batch, run the provenance/schema validator instead:

```powershell
python -B .\.agents\skills\dialogue-syntax-experiment\scripts\validate_ai_exploration_annotations.py `
  --packet <packet.csv> --annotations <ai_annotations.csv> --report <report.json>
```

Update both state files with the exact version, hashes, metrics, limitations, and next gate. Report failures as failures; do not silently relax checks or bless changed hashes.
