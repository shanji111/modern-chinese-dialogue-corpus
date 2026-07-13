# Confirmatory annotation protocol

## Sampling

- Exclude all existing gold `pair_id`, `normalized_pair_hash`, and `conversation_group_key` values.
- Stratify by source, dataset, rule-positive, rule-negative, shared-term hard negative, and potential rule false negative.
- Cap samples per conversation and keep entire conversations in one partition.
- Freeze a private master key before distributing blind files.

## Independent annotation

- Give annotators identical written definitions but no model prediction, rule flag, prior gold, or other annotator output.
- Require `yes`, `no`, or `uncertain` for pair resonance and `1`, `0`, or `?` for mechanism labels.
- Copy evidence spans directly from the turns.
- Record annotator identity or provenance, annotation date, and packet version.
- Double-annotate at least the predeclared overlap subset. Do not use AI-assisted drafting as a substitute for independent human annotation.

## Agreement and adjudication

- Calculate raw agreement and Cohen's kappa before either annotator sees the other's labels.
- Report binary resonance agreement and per-mechanism agreement separately.
- Preserve both raw files. Write adjudicated gold to a new file with decision notes and provenance.
- If agreement is poor, revise the guide and annotate a new calibration packet before expanding.

## Holdout

- Separate development and confirmatory holdout groups before model work.
- Seal the holdout labels and do not inspect slice results until rules, model, threshold, calibration, and hybrid logic are frozen.
- Evaluate the holdout once for the confirmatory report; later changes require a new holdout.
