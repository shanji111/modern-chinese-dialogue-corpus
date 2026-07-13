# Hybrid Shadow Next Steps

This roadmap keeps integration staged and reversible.

## Stage A: Offline Interface Wrapper

Goal:

Create an offline wrapper around the hybrid contract. It should accept pair text plus rule evidence and return BERT confidence plus hybrid metadata.

Exit conditions:

- Inputs and outputs match `hybrid_shadow_api_contract.md`.
- No database writes.
- No website route changes.
- Reproducible output on a fixed sample.

Risks:

- Threshold configuration may drift.
- Missing rule evidence may lead to misleading summaries.

## Stage B: Offline Batch On Existing Samples

Goal:

Run suitable existing samples through the wrapper offline.

Recommended text sources:

- Curated text dialogues.
- Daily conversation data with clear adjacent turns.
- Interview data with stable Q/A structure.
- Script/dialogue data with clean speaker turns.

Use caution with:

- Noisy network replies.
- Low-quality machine-generated fragments.
- Mismatched or truncated conversations.
- Contextless one-liners.

Exit conditions:

- Batch outputs include warning flags and explanation summaries.
- Manual spot-check confirms rule-negative/BERT-high candidates are reviewable.
- Topic-related false positives are tracked.

Risks:

- Many network replies may be topic-adjacent but not resonance.
- Genre imbalance may distort confidence.

## Stage C: Website Shadow Logging

Goal:

Record hybrid outputs for selected searches without showing them to users.

Exit conditions:

- Logging is opt-in or admin-only.
- No production search ranking changes.
- No database mutation without explicit migration review.
- Logs can be deleted or disabled.

Risks:

- Performance overhead.
- Privacy and retention policy questions.
- Misinterpreting shadow logs as labels.

## Stage D: Admin-Only Review Display

Goal:

Show hybrid metadata in a backend/admin review surface.

Exit conditions:

- Rule graph remains primary explanation.
- BERT score appears only as auxiliary confidence.
- Rule-negative/BERT-high cases are labeled as review candidates.
- Reviewers can mark false positives without changing gold automatically.

Risks:

- Reviewers may over-trust BERT.
- Confidence badges may be mistaken for gold labels.

## Stage E: Limited User-Visible Confidence

Goal:

Consider user-visible confidence only after offline and admin review prove useful.

Exit conditions:

- Larger gold set.
- Stable multi-seed and cross-validation results.
- Clear false-positive handling.
- Product copy avoids AI truth claims.
- Rule graph explanations remain available.

Risks:

- Users may treat confidence as certainty.
- Hidden model drift.
- Extra complexity in search interpretation.

## Long-Term Direction

The preferred architecture is:

Rules produce candidates and graph explanations.

BERT supplies confidence and recall supplementation.

Hybrid logic decides review priority and optional ranking hints.

Human review remains the authority for gold labels.

