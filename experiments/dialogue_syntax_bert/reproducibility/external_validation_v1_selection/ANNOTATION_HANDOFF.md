# External Validation V1 Annotation Handoff

This selection is frozen and contains no human labels. Do not sort, delete, merge, or renumber rows.

## Annotator A

Fill:

- `development_annotation_blind.csv` (600 rows)
- `external_holdout_annotation_blind.csv` (200 rows)

Return them as new files named:

- `development_annotator_a_filled.csv`
- `external_holdout_annotator_a_filled.csv`

## Independent annotator B

Fill independently:

- `development_overlap_annotator_b_blind.csv` (180 rows)
- `external_holdout_overlap_annotator_b_blind.csv` (60 rows)

Return them as new files named:

- `development_overlap_annotator_b_filled.csv`
- `external_holdout_overlap_annotator_b_filled.csv`

## Allowed values

- `resonance_present`: `yes`, `no`, or `uncertain`.
- Each `label_*`: `1`, `0`, or `?`.
- Evidence spans must be exact substrings copied from the corresponding turn.
- Explain uncertain or boundary cases in the note fields.

## Blinding requirements

- Do not show either annotator `selection_key.csv`.
- Do not show either annotator `artifacts/external_validation_v1_private/master_rule_key_private.csv`.
- Do not show rule flags, BERT scores, previous gold, or the other annotator's answers.
- Do not use GPT, Codex, or another model to draft labels if the annotation is to count as independent human annotation.

## After both returns

Run agreement scoring before adjudication. Preserve both raw filled files unchanged. Write adjudicated labels to a new versioned file; never overwrite either annotator's file.
