# Hybrid Shadow Safety And Limitations

## Data Limitations

The current frozen binary gold set is small:

- `gold_v1_binary`: 286 rows.
- Test split: 43 rows.
- Dev split: 43 rows.

The current result is a useful shadow experiment, not production performance.

## Model Limitations

MacBERT can still confuse topic-related response with dialogue-syntax resonance.

Known stable false positive:

- `F300V1-0221`
- Type: topic-related but not resonance.

Known hard false-negative areas:

- Demonstrative/reference carry-over.
- Short answers.
- Selective reuse with little surface overlap.

These are exactly the areas where BERT helps, but also where confidence can be unstable.

## Operational Risks

Do not:

- Automatically write BERT outputs to production database tables.
- Automatically rewrite gold labels.
- Treat shadow metrics as launch metrics.
- Use test data to tune thresholds.
- Use BERT as the only explanation.
- Generate graph edges from BERT probability.

## Required Before Production Use

Before any production-facing use:

- More gold data.
- Larger dev/test sets.
- More genre-specific evaluation.
- Real website shadow logging.
- Manual review of rule-negative/BERT-high candidates.
- Monitoring for topic-related false positives.
- A rollback plan.

## Safe Current Scope

Safe current use:

- Offline batch analysis.
- Internal review queues.
- Shadow-only confidence scoring.
- Research notes on hidden resonance candidates.

Unsafe current use:

- User-visible automatic claims.
- Database mutation.
- Replacing rule graph explanations.

