# rule_baseline_v1 error analysis

## Why this baseline is conservative

- v1 only trusts explicit surface triggers from `turn_a` / `turn_b` and allows many pairs to stay empty.
- v1 does not auto-generate `analogy` and barely touches `semantic_substitution` unless the wording is extremely explicit.
- high-risk long-range pragmatic mapping is intentionally left for later reranking / richer generation stages.

## Relation types missed most

- pragmatic_function: missed 16 / gold 21 (matched 5)
- slot_filling: missed 13 / gold 19 (matched 6)
- semantic_substitution: missed 12 / gold 16 (matched 4)
- contrast: missed 10 / gold 11 (matched 1)
- coreference_or_demonstrative: missed 9 / gold 18 (matched 9)
- lexical_reproduction: missed 8 / gold 26 (matched 18)
- analogy: missed 6 / gold 7 (matched 1)
- syntactic_parallelism: missed 6 / gold 7 (matched 1)
- repair: missed 5 / gold 9 (matched 4)
- short_answer: missed 1 / gold 1 (matched 0)

## Pairs with zero relaxed match

F300V1-0017(2651506), F300V1-0033(2723890), F300V1-0052(2735205), F300V1-0081(2719051), F300V1-0092(2723587), F300V1-0097(2668887), F300V1-0106(2737971), F300V1-0117(2723842), F300V1-0128(2733691), F300V1-0150(2735985), F300V1-0154(2736359), F300V1-0159(2735303), F300V1-0185(2734249), F300V1-0205(2730840), F300V1-0219(2735511), F300V1-0220(2733787), F300V1-0224(2724233), F300V1-0244(2734050), F300V1-0250(2705383), F300V1-0265(2736207)

## Typical unmatched gold columns

- F300V1-0020/C03: slot_filling | A=`什么` | B=`科学`
- F300V1-0023/C03: slot_filling | A=`做什么` | B=`看看`
- F300V1-0050/C03: slot_filling | A=`甚么名字` | B=`巴山虎`
- F300V1-0050/C04: slot_filling | A=`甚么名字` | B=`倚海龙`
- F300V1-0127/C02: analogy | A=`大鹏与他是一母所生` | B=`妖精的外甥`
- F300V1-0127/C03: analogy | A=`佛母` | B=`外甥`
- F300V1-0127/C04: semantic_substitution | A=`大鹏` | B=`妖精`
- F300V1-0127/C06: analogy | A=`佛母` | B=`你还是妖精的外甥哩`
- F300V1-0137/C02: lexical_reproduction | A=`贵姓` | B=`姓`
- F300V1-0137/C03: slot_filling | A=`贵姓` | B=`王`

## Typical overgenerated prediction columns

- F300V1-0002/P01: short_answer | A=`子奚不为政？` | B=`书云` | note=rule=short_answer; explicit question with short B-side answer
- F300V1-0008/P03: coreference_or_demonstrative | A=`凑合了` | B=`那` | note=rule=demonstrative; proposition recall via 那
- F300V1-0024/P01: contrast | A=`在西梁国毒敌山琵琶洞` | B=`却来呼唤小神` | note=rule=contrast; explicit contrast/evaluation marker in B
- F300V1-0055/P01: slot_filling | A=`都长这么大了` | B=`和晓霞不一个班` | note=rule=slot_filling; wh-question answered by B-side clause
- F300V1-0081/P01: lexical_reproduction | A=`一块` | B=`一块` | note=rule=lexical_reproduction; exact common substring
- F300V1-0081/P02: coreference_or_demonstrative | A=`少平说要交给你` | B=`那` | note=rule=demonstrative; proposition recall via 那
- F300V1-0127/P02: coreference_or_demonstrative | A=`我` | B=`你` | note=rule=coreference; speaker-role / deictic shift
- F300V1-0128/P01: short_answer | A=`则齐其庶几乎` | B=`可得闻与` | note=rule=short_answer; explicit question with short B-side answer
- F300V1-0137/P02: coreference_or_demonstrative | A=`你` | B=`我` | note=rule=coreference; speaker-role / deictic shift
- F300V1-0204/P02: lexical_reproduction | A=`台湾` | B=`台湾` | note=rule=lexical_reproduction; exact common substring

## Why analogy is not auto-generated

- analogy needs a stable structure-transfer chain from A to B, and baseline v1 intentionally avoids pretending that surface similarity is enough.
- keeping analogy out of v1 makes the baseline easier to audit and prevents false positives from ironic or evaluative dialogue.

## What a future BERT-assisted reranker/filter should prioritize

- pragmatic_function columns that depend on discourse force rather than lexical overlap
- semantic_substitution cases with real replacement slots instead of topic-level relatedness
- long-range coreference / demonstrative mapping
- analogy candidates with structural transfer
- filtering weak lexical overlaps that create overgeneration noise

