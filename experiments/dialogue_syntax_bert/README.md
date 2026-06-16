# Dialogue Syntax BERT Experiments

This directory contains offline experiments for BERT-assisted dialogue syntax
analysis. It is intentionally isolated from the production Flask routes,
deployment configuration, migrations, and the main `corpus.db` write path.

## Scope

- Build annotation samples from read-only dialogue-pair data.
- Define a stable multi-label annotation schema.
- Evaluate the current rule baseline against human labels.
- Run offline non-finetuned and finetuned model experiments.
- Store only experimental artifacts under this directory.

## Safety Rules

- Do not write to the production `corpus.db`.
- Use `sqlite3` read-only URI mode when reading a corpus database.
- Write samples, annotation sheets, reports, and model outputs under
  `experiments/dialogue_syntax_bert/artifacts/`.
- Do not import or modify Flask routes for experiments.
- Do not change Render, environment, or migration configuration.

## Files

- `LABEL_SCHEMA.md`: annotation definitions and boundary notes.
- `sample_pairs.py`: builds annotation CSV/JSONL from a read-only SQLite DB.
- `evaluate_rules.py`: evaluates existing rule flags against human labels.
- `similarity_baseline.py`: runs lexical similarity and optional cached BERT
  embedding baselines without finetuning.
- `prepare_model_data.py`: converts filled annotation CSV into JSONL splits.
- `bert_pair_classifier.py`: optional offline BERT finetuning entrypoint.

## Suggested Workflow

1. Generate an annotation sample:

   ```powershell
   python -B .\experiments\dialogue_syntax_bert\sample_pairs.py `
     --db "D:\现代汉语对话语料库\corpus.db" `
     --per-label 200 `
     --negative 400 `
     --random 200
   ```

   The database is opened in SQLite `mode=ro`; outputs go under `artifacts/`.

2. Fill the `label_*` columns in the CSV.

   Use `1` for true and `0` or blank for false. Labels are multi-label except
   that `label_no_relation=1` means no positive relation is present.

3. Evaluate current rules:

   ```powershell
   python -B .\experiments\dialogue_syntax_bert\evaluate_rules.py `
     --annotations .\experiments\dialogue_syntax_bert\artifacts\annotation\dialogue_pair_annotation_sample.csv
   ```

4. Run non-finetuned baselines:

   ```powershell
   python -B .\experiments\dialogue_syntax_bert\similarity_baseline.py `
     --annotations .\experiments\dialogue_syntax_bert\artifacts\annotation\dialogue_pair_annotation_sample.csv
   ```

   Add `--bert-model <local-or-cached-model>` only in an experiment environment
   where `torch` and `transformers` are installed.

5. Prepare model data and finetune offline:

   ```powershell
   python -B .\experiments\dialogue_syntax_bert\prepare_model_data.py `
     --annotations .\experiments\dialogue_syntax_bert\artifacts\annotation\dialogue_pair_annotation_sample.csv

   python -B .\experiments\dialogue_syntax_bert\bert_pair_classifier.py `
     --train-jsonl .\experiments\dialogue_syntax_bert\artifacts\model_data\train.jsonl `
     --dev-jsonl .\experiments\dialogue_syntax_bert\artifacts\model_data\dev.jsonl `
     --model-name bert-base-chinese
   ```

## Integration Boundary

This stage deliberately does not connect BERT to Flask routes. A later stage
can add a separate experimental score table or artifact import step after the
annotation and offline evaluation results justify it.
