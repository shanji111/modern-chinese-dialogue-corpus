# Dialogue Syntax Label Schema

Use these labels as multi-label annotations for adjacent dialogue pairs. Mark a
label only when the relation is visible in the A/B pair or its minimal context.

## Allowed Annotation Values

- `resonance_present` must be exactly one of: `yes`, `no`, `uncertain`.
- Each `label_*` column must be exactly one of: `1`, `0`, `?`.
- `evidence_span_a` and `evidence_span_b` must be direct substrings copied from
  the original A/B turns.
- Multiple evidence spans must be separated with `|||`.
- When `resonance_present=no`, the core mechanism labels should normally be `0`.
- When `resonance_present=yes`, at least one core mechanism label should be `1`.
- `label_analogy_candidate` is exploratory and is not part of first-stage core
  rule F1 evaluation.

Core mechanism labels for first-stage evaluation:

- `label_reproduction`
- `label_parallelism`
- `label_selective_reuse`
- `label_repair`
- `label_contrast`

`label_analogy_candidate` should still be filled when relevant, but it is
reported separately.

## Boundary Principles

These principles summarize the pilot boundary decisions and should be used
when a pair sits between ordinary adjacency and dialogue-syntax resonance.

- Ordinary factual question-answer pairs are not automatically resonance. If B
  only provides a price, fact, object, or routine answer, and there is no
  locatable reproduction, slot filling, structural alignment, or selective
  uptake from A, mark `resonance_present=no`.
- Slot-filling question-answer pairs may count as weak resonance. If A opens a
  clear interrogative slot and B fills that slot while preserving a recoverable
  question-answer frame, mark `resonance_present=yes`; common core labels are
  `label_parallelism=1` and/or `label_selective_reuse=1`.
- Handoff answers are not resonance by default. If B merely redirects the
  question to another speaker or asks someone else to answer, without reusing
  the structural resources of A, mark `resonance_present=no`.
- Demonstratives such as "this", "that", "these", `此`, `这`, or `那个` may
  count as `label_selective_reuse=1` when they stably point back to a concrete
  object, set, proposition, or evaluation type in A and B uses that referent for
  further questioning, denial, evaluation, or contrast. If the referent is not
  stable, use `uncertain` or leave the core label as `?`.
- Pure stance alignment is not a first-stage core label. If B only agrees,
  endorses, rejects, or echoes a stance without stable form, structure, or
  referential uptake, mark `resonance_present=no` or `uncertain` and explain the
  boundary in notes.
- Analogy is exploratory in the first stage. Mark
  `label_analogy_candidate=1` when a cross-domain or relational mapping is
  visible, but do not include it in core F1. If the analogy also has
  reproduction, parallelism, or selective reuse, mark the relevant core labels
  too; otherwise keep the core mechanism as `?` or `0` as appropriate.
- Garbled, mismatched, or unreliable pairs should not be forced into a positive
  label. Mark `resonance_present=uncertain`, use `?` for unstable mechanism
  labels when needed, and explain that the pair may need later exclusion.

## 重现 (`reproduction`)

B reuses a lexical item, phrase, or compact expression from A.

Positive cues:
- exact lexical echo
- shared substantive phrase
- repeated named entity or compact expression

Do not mark when:
- only stop words or discourse particles overlap
- the two turns merely discuss the same topic

## 平行 (`parallel`)

A and B share a recognizable constructional or functional frame.

Positive cues:
- the same clause frame with different slot fillers
- repeated stance frame such as "I think X / I think Y"
- question or conditional frames reused across turns

Do not mark when:
- there is word overlap but no comparable frame
- the second turn is only a generic answer

## 选择/修正 (`selection`)

B selectively takes up part of A and extends, narrows, repairs, or reformulates
it.

Positive cues:
- B repeats part of A and adds a correction
- B narrows or completes an expression from A
- B uses reformulation markers such as "actually", "that is", or "more exactly"

Do not mark when:
- B simply repeats A without development
- B answers with new material and does not select from A

## 对比 (`contrast`)

B negates, opposes, replaces, or contrastively reframes A.

Positive cues:
- direct negation of A material
- "not X but Y" relation
- contrastive turn with "but", "however", or equivalent markers

Do not mark when:
- a negative word appears but does not target A
- B states an unrelated negative fact

## 问答回应 (`qa_response`)

A creates an interrogative slot and B answers, rejects, or otherwise addresses
it.

Positive cues:
- A asks and B gives an accountable answer
- B refuses, corrects, or reframes the question while still addressing it

Do not mark when:
- the question marker is embedded in unrelated quoted text
- B is adjacent but does not respond to the question

## 类比 (`analogy`)

A and B map different surface material onto a similar relational structure.

Positive cues:
- different words but comparable roles or relations
- metaphorical or analogical structural mapping

Do not mark when:
- there is only semantic similarity
- the pair shares topic without relational mapping

## 无明显关系 (`no_relation`)

Use this when no positive relation is clear at the current annotation
granularity. If `no_relation` is marked, leave all positive labels blank or 0.
