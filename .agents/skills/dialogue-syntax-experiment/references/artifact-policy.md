# Artifact policy

- Keep generated scratch outputs in the ignored `experiments/dialogue_syntax_bert/artifacts/` tree.
- Keep compact, immutable evidence in `experiments/dialogue_syntax_bert/reproducibility/<version>/`.
- Include gold CSVs, split keys, metric JSON, essential reports, and prediction CSVs needed to audit headline metrics.
- Exclude model weights, caches, raw database copies, large spreadsheets duplicated by CSV, and temporary render/inspection files.
- Generate `MANIFEST.sha256.json` with the bundled freeze script. A hash change requires a new snapshot version, not an overwrite.
- Record the snapshot version and manifest path in `EXPERIMENT_REGISTRY.json`.
- Before closing a stage, verify every source script used by the stage is tracked and the state checker passes without `--skip-git`.
