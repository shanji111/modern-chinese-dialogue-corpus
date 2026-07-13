# Hybrid Shadow UI Design Notes

These notes describe a possible future website presentation. They do not modify frontend code.

## Display Principles

Do not display:

- `AI judged true`
- `AI judged false`
- `BERT confirms resonance`

Prefer:

- `AI-assisted confidence`
- `Possible hidden carry-over`
- `Suggested for manual review`

The UI should keep the rule graph as the primary explanation. BERT should appear as an auxiliary score or badge, not as the reason itself.

## Candidate List Behavior

Default behavior should not automatically filter results.

Allowed shadow behaviors:

- Add a confidence badge.
- Add a hidden-resonance marker for rule-negative/BERT-high pairs.
- Adjust sort order in a shadow-only experiment.
- Export candidates for offline review.

Avoid:

- Removing rule-negative candidates solely because BERT is low.
- Promoting BERT-high candidates without showing that rule evidence is absent.
- Showing a graph generated from BERT.

## Rule-Negative But BERT-High

For `rule_any_positive=0` and high BERT probability, show:

`Possible hidden carry-over. Rule evidence is weak or absent; manual review recommended.`

This is useful for demonstrative/reference, short-answer, and slot-filling cases.

## Topic-Related False Positive Risk

For known risk patterns, show:

`Warning: topic relatedness is not the same as dialogue-syntax resonance.`

This matters because stable false positive `F300V1-0221` shows that BERT may over-score discourse continuity without stable reusable syntax resources.

## Rule Graph

The graph remains the main explanation layer:

- Matched spans.
- Reused terms.
- Pattern alignment.
- Repair/contrast/negation evidence.
- Rule flags.

BERT can annotate confidence around the pair, but it should not create graph nodes or edges.

## Review Workflow

Recommended workflow:

1. Keep normal search behavior unchanged.
2. Add shadow confidence metadata in internal exports.
3. Add review badges in an admin-only view.
4. Only later consider user-visible confidence.

