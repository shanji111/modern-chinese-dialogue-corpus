# Dialogue Syntax Label Schema

Use these labels as multi-label annotations for adjacent dialogue pairs. Mark a
label only when the relation is visible in the A/B pair or its minimal context.

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

