# gold_v1_binary split report

- seed: 20260621
- total rows: 286
- leakage-free: yes
- split strategy: grouped by conversation_group_key; yes-only and no-only groups are assigned by current label-target fill ratio, preserving group disjointness while approximating 70/15/15.

## Row and label distribution

|split|rows|yes|no|
|---|---|---|---|
|train|200|160|40|
|dev|43|34|9|
|test|43|34|9|

## sample_stratum distribution

|split|sample_stratum|count|
|---|---|---|
|train|rule_positive|62|
|train|analogy_or_parallel_candidate|20|
|train|potential_false_negative|38|
|train|rule_negative_random|42|
|train|hard_negative_or_boundary|38|
|dev|rule_positive|15|
|dev|hard_negative_or_boundary|11|
|dev|potential_false_negative|5|
|dev|rule_negative_random|9|
|dev|analogy_or_parallel_candidate|3|
|test|potential_false_negative|12|
|test|rule_positive|12|
|test|rule_negative_random|6|
|test|hard_negative_or_boundary|7|
|test|analogy_or_parallel_candidate|6|

## source distribution

|split|source|count|
|---|---|---|
|train|文本对话|122|
|train|日常对话|34|
|train|访谈语料|21|
|train|网络回帖|11|
|train|影视对白|8|
|train|多模态语料|4|
|dev|文本对话|22|
|dev|访谈语料|6|
|dev|日常对话|11|
|dev|影视对白|1|
|dev|网络回帖|3|
|test|网络回帖|4|
|test|日常对话|7|
|test|文本对话|24|
|test|访谈语料|4|
|test|影视对白|4|

## dataset distribution

|split|dataset_name|count|
|---|---|---|
|train|世说新语|8|
|train|douban-multiturn-100w|11|
|train|qingyun-11w|6|
|train|平凡的世界|10|
|train|清平山堂话本|10|
|train|青云语料|7|
|train|水浒传|7|
|train|朱子语类|9|
|train|唐传奇|8|
|train|雷雨|9|
|train|论语|12|
|train|西游记|6|
|train|红楼梦|11|
|train|孟子|7|
|train|mfa_press|10|
|train|贴吧回帖|4|
|train|老乞大|6|
|train|朴通事|8|
|train|subtitle-useless|8|
|train|骆驼祥子|11|
|train|china_interview|7|
|train|chatterbot|6|
|train|tieba-305w|7|
|train|china_live|4|
|train|local-audio-demo|4|
|train|chatterbot-1k|4|
|dev|老乞大|3|
|dev|孟子|4|
|dev|china_interview|3|
|dev|世说新语|4|
|dev|china_live|2|
|dev|qingyun-11w|4|
|dev|水浒传|2|
|dev|红楼梦|2|
|dev|平凡的世界|3|
|dev|青云语料|3|
|dev|chatterbot-1k|2|
|dev|douban-multiturn-100w|2|
|dev|唐传奇|1|
|dev|朴通事|1|
|dev|西游记|1|
|dev|subtitle-useless|1|
|dev|论语|1|
|dev|mfa_press|1|
|dev|tieba-305w|1|
|dev|贴吧回帖|2|
|test|tieba-305w|2|
|test|chatterbot|3|
|test|贴吧回帖|2|
|test|世说新语|2|
|test|骆驼祥子|1|
|test|china_interview|2|
|test|清平山堂话本|1|
|test|水浒传|1|
|test|朱子语类|3|
|test|老乞大|3|
|test|西游记|3|
|test|朴通事|2|
|test|唐传奇|3|
|test|qingyun-11w|1|
|test|subtitle-useless|4|
|test|论语|2|
|test|china_live|1|
|test|孟子|1|
|test|雷雨|1|
|test|青云语料|2|
|test|chatterbot-1k|1|
|test|红楼梦|1|
|test|mfa_press|1|

## Leakage checks

- annotation_id leakage: {"train_dev":[],"train_test":[],"dev_test":[]}
- pair_id leakage: {"train_dev":[],"train_test":[],"dev_test":[]}
- normalized_pair_hash leakage: {"train_dev":[],"train_test":[],"dev_test":[]}
- conversation_group_key leakage: {"train_dev":[],"train_test":[],"dev_test":[]}

Hash leakage: no

conversation_group_key leakage: no
