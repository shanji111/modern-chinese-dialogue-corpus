# BERT Shadow v3 Stability Analysis

## Error Consistency

- Stable FN count: 2
- Stable FP count: 1
- Seed-sensitive sample count: 12
- Stable FN risk counts: `{"demonstrative_or_reference": 1, "short_answer": 1}`
- Stable FP risk counts: `{"topic_related_but_not_resonance": 1}`

## Stable FNs

F300V1-0234, F300V1-0111

## Stable FPs

F300V1-0221

## Seed-Sensitive Samples

F300V1-0060, F300V1-0250, F300V1-0092, F300V1-0214, F300V1-0205, F300V1-0211, F300V1-0235, F300V1-0006, F300V1-0142, F300V1-0213, F300V1-0078, F300V1-0243

## Interpretation

Stable FNs should be read as persistent blind spots. If they are concentrated in demonstrative/reference, short-answer, or selective-reuse cases, future work should analyze implicit carry-over rather than simply increasing epochs.
