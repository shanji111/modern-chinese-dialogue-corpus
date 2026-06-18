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
- `artifacts/` may be ignored by Git. Human annotation files must be backed up
  separately before editing.
- Never run cleanup or regeneration commands against a directory that may
  contain filled human annotation files.
- Writers refuse to overwrite existing artifacts by default. Use `--overwrite`
  only for intentional regeneration, and do not force overwrites of filled
  annotation files.

## Files

- `LABEL_SCHEMA.md`: annotation definitions and boundary notes.
- `sample_pairs.py`: builds annotation CSV/JSONL from a read-only SQLite DB.
- `evaluate_rules.py`: evaluates existing rule flags against human labels.
- `similarity_baseline.py`: runs lexical similarity and optional cached BERT
  embedding baselines without finetuning.
- `prepare_model_data.py`: converts filled annotation CSV into JSONL splits.
- `bert_pair_classifier.py`: optional offline BERT finetuning entrypoint.
- `split_blind_annotation.py`: creates blind annotation and evaluation-key CSVs.
- `validate_annotations.py`: validates filled blind annotation CSVs without
  modifying them.
- `split_safety.py`: helper functions for future train/dev/test leakage checks.

## Split Safety Fields

- `normalized_pair_hash`: SHA-256 over normalized `text_a + text_b`; use it only
  to identify duplicate text pairs.
- `conversation_group_key`: `dataset_name + "::" + conversation_key`; use it to
  keep adjacent pairs from the same conversation in the same train/dev/test
  partition.

Future train/dev/test splits must verify that these three key sets are disjoint
between partitions:

- `pair_id`
- `normalized_pair_hash`
- `conversation_group_key`

## Suggested Workflow

1. Generate an annotation sample:

   ```powershell
   python -B .\experiments\dialogue_syntax_bert\sample_pairs.py `
     --db "D:\现代汉语对话语料库\corpus.db" `
     --output-dir .\experiments\dialogue_syntax_bert\artifacts\pilot_50 `
     --sample-size 50 `
     --max-per-conversation 2
   ```

   The database is opened in SQLite `mode=ro`; outputs go under `artifacts/`.

2. Create blind annotation files:

   ```powershell
   python -B .\experiments\dialogue_syntax_bert\split_blind_annotation.py `
     --input-csv .\experiments\dialogue_syntax_bert\artifacts\pilot_50\pilot_50.csv `
     --output-dir .\experiments\dialogue_syntax_bert\artifacts\pilot_50
   ```

3. Fill the blind annotation CSV.

   Use `yes`, `no`, or `uncertain` for `resonance_present`. Use `1`, `0`, or
   `?` for each `label_*` column.

4. Validate filled annotations:

   ```powershell
   python -B .\experiments\dialogue_syntax_bert\validate_annotations.py `
     --csv .\experiments\dialogue_syntax_bert\artifacts\pilot_50\pilot_50_annotation_blind.csv
   ```

5. Evaluate current rules after annotation:

   ```powershell
   python -B .\experiments\dialogue_syntax_bert\evaluate_rules.py `
     --annotations .\experiments\dialogue_syntax_bert\artifacts\pilot_50\pilot_50_annotation_blind.csv `
     --key .\experiments\dialogue_syntax_bert\artifacts\pilot_50\pilot_50_evaluation_key.csv
   ```

6. Run non-finetuned baselines:

   ```powershell
   python -B .\experiments\dialogue_syntax_bert\similarity_baseline.py `
     --annotations .\experiments\dialogue_syntax_bert\artifacts\annotation\dialogue_pair_annotation_sample.csv
   ```

   Add `--bert-model <local-or-cached-model>` only in an experiment environment
   where `torch` and `transformers` are installed.

7. Prepare model data and finetune offline:

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
