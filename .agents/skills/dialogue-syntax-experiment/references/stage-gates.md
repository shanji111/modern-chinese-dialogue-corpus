# Stage gates

## Gate 0: reproducibility

Pass only when source scripts are tracked, the frozen snapshot manifest verifies, split leakage checks pass, and project state is current.

## Gate 1: pair-level confirmatory evidence

Require a new grouped sample, documented independent human overlap, agreement before adjudication, locked model/threshold/hybrid logic, and one-time external-holdout evaluation with uncertainty intervals and source slices.

## Gate 1E: AI exploratory evidence (non-confirmatory)

When independent human annotation is unavailable, allow a versioned AI draft
route for development error slicing, uncertainty analysis, and prompt/model
diagnosis. Require complete AI provenance and schema validation, keep the
non-network and asynchronous-network profiles separate, and do not promote
these labels to gold or use them for a confirmatory claim. Gate 1 remains
unpassed until an independently authorized annotation/adjudication process is
available.

## Gate 2: column expansion

Require a larger positive-pair gold set plus negative and uncertain end-to-end cases. Preserve the current 50-pair set as historical development evidence. Measure span, relation-type, and core-column agreement. Train candidate keep/filter models only after enough independently reviewed candidates exist.

## Gate 3: offline website wrapper

Allow a separate deterministic interface that returns rule evidence, model score, hybrid decision, versions, and warnings. Do not change routes, ranking, or production data.

## Gate 4: batch shadow and admin review

Run on new data into a separate experiment artifact or database. Show results to administrators only after error review. Capture explicit human accept/reject/correct feedback.

## Gate 5: user-visible influence

Require confirmatory evidence, calibration, stable source slices, reviewed shadow errors, a rollback path, and explicit user authorization. Keep the interpretable rule graph primary.
