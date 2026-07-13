# majority baseline on gold_v1_binary

- train majority class: yes
- train distribution: yes=160, no=40
- prediction rule: predict yes for every row.
- training: no
- BERT: not run

|split|accuracy|pos_precision|pos_recall|pos_f1|macro_f1|weighted_f1|balanced_accuracy|no_precision|no_recall|no_f1|tp|fp|fn|tn|
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
|train|0.800|0.800|1.000|0.889|0.444|0.711|0.500|0.000|0.000|0.000|160|40|0|0|
|dev|0.791|0.791|1.000|0.883|0.442|0.698|0.500|0.000|0.000|0.000|34|9|0|0|
|test|0.791|0.791|1.000|0.883|0.442|0.698|0.500|0.000|0.000|0.000|34|9|0|0|
|full|0.797|0.797|1.000|0.887|0.444|0.707|0.500|0.000|0.000|0.000|228|58|0|0|

The dev/test result is all-yes: no-class recall is 0.000, so positive-class F1 alone is misleading.
