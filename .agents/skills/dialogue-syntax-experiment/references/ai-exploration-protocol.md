# AI-assisted exploratory annotation protocol

This route is for exploration, error analysis, and prompt/model diagnosis. It
does not create gold labels, independent-human agreement, or a confirmatory
external-validity claim.

## Packet roles

- `external_validation_v2_ai_exploratory` is the primary non-network packet.
  It contains daily dialogue, interview, film/subtitle dialogue, and textual
  dialogue. Its development and holdout partitions are dataset-disjoint, but
  the holdout is still exploratory until a separately authorized confirmatory
  annotation process exists.
- `network_async_stress_v1` is a separate asynchronous-network stress profile.
  Never pool its metrics with continuous-dialogue metrics.
- Files named `*_ai_audit_subset.csv` are second-pass AI audit packets. They
  are not a second annotator and must not be scored with Cohen's kappa as if
  they were independent human labels.

## Required provenance

Every AI output row must preserve the packet `annotation_id` and include:

- `ai_model`;
- `ai_prompt_version`;
- `ai_run_id`;
- `ai_confidence` as a numeric value in `[0, 1]`;
- `ai_review_status`, normally `ai_draft_v1` or `ai_second_pass_v1`.

The run manifest must also record the execution date, packet hash, prompt
hash/version, model settings, and whether the run saw development or holdout
rows. Do not silently replace a previous run; write a new versioned artifact.

## Labeling instructions

The model receives only the two turns and the written definitions. It must
return strict JSON/CSV using `yes`, `no`, or `uncertain` for resonance and
`1`, `0`, or `?` for mechanism fields. Evidence spans must be copied exactly
from the corresponding turn. If the context is insufficient, use
`uncertain`/`?` and explain the reason rather than inferring missing context.

Use development rows for prompt and error-slice exploration. Freeze the model,
prompt, threshold, and aggregation rule before looking at holdout summaries;
do not tune on AI holdout labels. Any holdout result is descriptive until
human or otherwise independently authorized adjudication is obtained.

## Reporting

Report coverage, uncertainty rate, and provenance completeness before any
performance number. Slice by source profile and by stratum. Keep AI draft
metrics separate from the historical 300-row human-reviewed gold metrics and
from the network stress profile. The website remains blocked from using these
labels as production or confirmatory truth.
