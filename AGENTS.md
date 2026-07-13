# Project Guidance

## Start here

- Read `PROJECT_STATE.md` and `experiments/dialogue_syntax_bert/EXPERIMENT_REGISTRY.json` before experiment work.
- Use the repository skill at `.agents/skills/dialogue-syntax-experiment/` for sampling, annotation, evaluation, freezing, or integration work.
- Work on an experiment branch or worktree. Preserve unrelated user changes in the main checkout.

## Safety boundaries

- Treat `D:\现代汉语对话语料库\corpus.db` as production data. Open it only with SQLite URI `mode=ro` and never copy it into a managed worktree.
- Do not change Flask routes, production ranking, migrations, deployment configuration, or the production database unless the applicable integration gate is recorded as passed and the user explicitly authorizes that stage.
- Do not overwrite a frozen gold set. Create a new version and retain the previous version and hashes.
- Keep local model weights outside Git. The current MacBERT location is `D:\hf_models\hfl_chinese_macbert_base`; record a model identifier and checksum or source metadata instead of committing weights.

## Evaluation integrity

- Split by `conversation_group_key`; verify `pair_id`, `normalized_pair_hash`, and `conversation_group_key` are disjoint.
- Select thresholds and strategies on development data only. Do not use the frozen test set or future external holdout to tune prompts, rules, thresholds, or model choices.
- Treat the existing 43-row test set as historical evidence because it has been inspected repeatedly. Use a new locked external holdout for the next confirmatory claim.
- Never describe AI-assisted review as independent human double annotation. Record annotator provenance and calculate agreement before adjudication.
- BERT may score sentence pairs or rule-generated candidates. It must not directly create final spans or modify gold at the current stage.

## Artifact policy

- Generated artifacts remain under `experiments/dialogue_syntax_bert/artifacts/` and may stay ignored.
- Track the compact reproducibility snapshot under `experiments/dialogue_syntax_bert/reproducibility/` with SHA-256 hashes.
- Track experiment source scripts. Before closing a stage, ensure no relevant script is untracked.

## Required closeout

Run:

```powershell
python -B .\.agents\skills\dialogue-syntax-experiment\scripts\check_project_state.py --repo-root .
```

Then update `PROJECT_STATE.md` and `EXPERIMENT_REGISTRY.json` with the result, limitations, next gate, and exact artifact version. Report `git status --short` without modifying unrelated files.
