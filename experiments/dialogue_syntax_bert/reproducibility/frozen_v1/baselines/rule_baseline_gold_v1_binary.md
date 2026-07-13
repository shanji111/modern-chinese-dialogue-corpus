# rule baseline on gold_v1_binary

## Overall

- rows: 286
- precision / recall / F1: 0.873 / 0.575 / 0.693
- TP / FP / FN / TN: 131 / 19 / 97 / 39

## By sample_stratum

|sample_stratum|total|precision|recall|f1|tp|fp|fn|tn|
|---|---|---|---|---|---|---|---|---|
|rule_positive|89|0.843|1.000|0.915|75|14|0|0|
|rule_negative_random|57|0.000|0.000|0.000|0|0|39|18|
|hard_negative_or_boundary|56|0.919|0.739|0.819|34|3|12|7|
|potential_false_negative|55|0.000|0.000|0.000|0|0|42|13|
|analogy_or_parallel_candidate|29|0.917|0.846|0.880|22|2|4|1|

## By source

|source|total|precision|recall|f1|tp|fp|fn|tn|
|---|---|---|---|---|---|---|---|---|
|文本对话|168|0.916|0.517|0.661|76|7|71|14|
|日常对话|52|0.893|0.676|0.769|25|3|12|12|
|影视对白|13|0.833|0.455|0.588|5|1|6|1|
|访谈语料|31|0.727|0.842|0.780|16|6|3|6|
|网络回帖|18|0.750|0.545|0.632|6|2|5|5|
|多模态语料|4|1.000|1.000|1.000|3|0|0|1|

## False positives

|annotation_id|source|dataset_name|sample_stratum|rule_summary|
|---|---|---|---|---|
|F300V1-0004|文本对话|红楼梦|rule_positive|question_response|
|F300V1-0011|文本对话|老乞大|rule_positive|question_response|
|F300V1-0022|网络回帖|tieba-305w|rule_positive|question_response|
|F300V1-0029|文本对话|平凡的世界|rule_positive|question_response|
|F300V1-0035|访谈语料|china_interview|rule_positive|question_response|
|F300V1-0041|访谈语料|mfa_press|rule_positive|reproduction / parallelism|
|F300V1-0062|日常对话|douban-multiturn-100w|rule_positive|question_response|
|F300V1-0064|日常对话|qingyun-11w|rule_positive|question_response|
|F300V1-0066|网络回帖|贴吧回帖|rule_positive|question_response|
|F300V1-0070|访谈语料|china_live|rule_positive|question_response|
|F300V1-0071|文本对话|清平山堂话本|rule_positive|question_response|
|F300V1-0078|文本对话|朴通事|rule_positive|question_response|
|F300V1-0086|文本对话|骆驼祥子|rule_positive|contrast|
|F300V1-0090|日常对话|qingyun-11w|rule_positive|question_response|
|F300V1-0156|访谈语料|china_live|hard_negative_or_boundary|reproduction / parallelism / question_response|
|F300V1-0179|访谈语料|mfa_press|hard_negative_or_boundary|reproduction / parallelism / question_response|
|F300V1-0201|影视对白|subtitle-useless|hard_negative_or_boundary|question_response|
|F300V1-0278|文本对话|朴通事|analogy_or_parallel_candidate|reproduction / selective_reuse/repair / contrast / question_response|
|F300V1-0294|访谈语料|china_live|analogy_or_parallel_candidate|reproduction / parallelism / question_response|

## False negatives

|annotation_id|source|dataset_name|sample_stratum|risk_type|
|---|---|---|---|---|
|F300V1-0091|文本对话|平凡的世界|rule_negative_random|semantic_selection + demonstrative_or_reference + short_answer|
|F300V1-0092|文本对话|唐传奇|rule_negative_random|semantic_selection + demonstrative_or_reference + short_answer|
|F300V1-0096|文本对话|论语|rule_negative_random|semantic_selection + short_answer|
|F300V1-0097|日常对话|qingyun-11w|rule_negative_random|semantic_selection + short_answer|
|F300V1-0098|文本对话|骆驼祥子|rule_negative_random|semantic_selection|
|F300V1-0099|访谈语料|china_interview|rule_negative_random|semantic_selection + demonstrative_or_reference|
|F300V1-0102|文本对话|世说新语|rule_negative_random|semantic_selection + slot_filling + short_answer|
|F300V1-0103|文本对话|西游记|rule_negative_random|semantic_selection|
|F300V1-0104|文本对话|孟子|rule_negative_random|semantic_selection + demonstrative_or_reference|
|F300V1-0105|文本对话|朴通事|rule_negative_random|semantic_selection + demonstrative_or_reference + short_answer|
|F300V1-0106|影视对白|subtitle-useless|rule_negative_random|semantic_selection + demonstrative_or_reference + short_answer|
|F300V1-0107|文本对话|雷雨|rule_negative_random|semantic_selection + short_answer|
|F300V1-0109|文本对话|清平山堂话本|rule_negative_random|semantic_selection + demonstrative_or_reference|
|F300V1-0110|日常对话|chatterbot|rule_negative_random|semantic_selection + slot_filling + short_answer|
|F300V1-0111|网络回帖|贴吧回帖|rule_negative_random|semantic_selection + demonstrative_or_reference + short_answer|
|F300V1-0112|文本对话|水浒传|rule_negative_random|semantic_selection + demonstrative_or_reference + short_answer|
|F300V1-0113|文本对话|老乞大|rule_negative_random|semantic_selection + demonstrative_or_reference + analogy|
|F300V1-0114|日常对话|douban-multiturn-100w|rule_negative_random|semantic_selection + demonstrative_or_reference|
|F300V1-0116|文本对话|平凡的世界|rule_negative_random|semantic_selection + demonstrative_or_reference + short_answer|
|F300V1-0117|文本对话|唐传奇|rule_negative_random|semantic_selection + demonstrative_or_reference + short_answer|
|F300V1-0118|日常对话|青云语料|rule_negative_random|semantic_selection|
|F300V1-0119|文本对话|红楼梦|rule_negative_random|semantic_selection + demonstrative_or_reference|
|F300V1-0120|文本对话|论语|rule_negative_random|semantic_selection + demonstrative_or_reference|
|F300V1-0122|文本对话|骆驼祥子|rule_negative_random|semantic_selection + demonstrative_or_reference + short_answer|
|F300V1-0124|文本对话|朱子语类|rule_negative_random|semantic_selection|
|F300V1-0127|文本对话|西游记|rule_negative_random|semantic_selection + demonstrative_or_reference + analogy|
|F300V1-0128|文本对话|孟子|rule_negative_random|semantic_selection + slot_filling + demonstrative_or_reference + short_answer|
|F300V1-0129|文本对话|朴通事|rule_negative_random|semantic_selection + demonstrative_or_reference|
|F300V1-0131|文本对话|雷雨|rule_negative_random|semantic_selection + demonstrative_or_reference + short_answer|
|F300V1-0133|文本对话|清平山堂话本|rule_negative_random|semantic_selection + demonstrative_or_reference|
|F300V1-0136|文本对话|水浒传|rule_negative_random|semantic_selection + slot_filling + short_answer|
|F300V1-0137|文本对话|老乞大|rule_negative_random|semantic_selection + slot_filling + short_answer|
|F300V1-0139|日常对话|chatterbot-1k|rule_negative_random|semantic_selection + short_answer|
|F300V1-0141|文本对话|唐传奇|rule_negative_random|semantic_selection + demonstrative_or_reference + short_answer|
|F300V1-0143|文本对话|红楼梦|rule_negative_random|semantic_selection + demonstrative_or_reference + short_answer|
|F300V1-0144|文本对话|论语|rule_negative_random|semantic_selection + slot_filling + short_answer|
|F300V1-0148|文本对话|朱子语类|rule_negative_random|semantic_selection + demonstrative_or_reference|
|F300V1-0149|网络回帖|tieba-305w|rule_negative_random|semantic_selection + demonstrative_or_reference + short_answer|
|F300V1-0150|文本对话|世说新语|rule_negative_random|semantic_selection + short_answer + analogy|
|F300V1-0153|影视对白|subtitle-useless|hard_negative_or_boundary|semantic_selection + slot_filling + short_answer|
|F300V1-0154|文本对话|世说新语|hard_negative_or_boundary|semantic_selection + demonstrative_or_reference + short_answer|
|F300V1-0159|文本对话|朴通事|hard_negative_or_boundary|semantic_selection + short_answer|
|F300V1-0161|文本对话|水浒传|hard_negative_or_boundary|semantic_selection + demonstrative_or_reference + short_answer|
|F300V1-0163|日常对话|chatterbot-1k|hard_negative_or_boundary|semantic_selection + short_answer|
|F300V1-0164|文本对话|清平山堂话本|hard_negative_or_boundary|semantic_selection + demonstrative_or_reference + short_answer|
|F300V1-0168|文本对话|红楼梦|hard_negative_or_boundary|semantic_selection + demonstrative_or_reference|
|F300V1-0182|文本对话|骆驼祥子|hard_negative_or_boundary|semantic_selection + slot_filling + demonstrative_or_reference + short_answer|
|F300V1-0185|文本对话|论语|hard_negative_or_boundary|semantic_selection + short_answer|
|F300V1-0205|文本对话|朱子语类|hard_negative_or_boundary|semantic_selection + demonstrative_or_reference|
|F300V1-0206|文本对话|骆驼祥子|hard_negative_or_boundary|semantic_selection + slot_filling + short_answer|
|F300V1-0207|文本对话|平凡的世界|hard_negative_or_boundary|semantic_selection + demonstrative_or_reference + short_answer|
|F300V1-0211|影视对白|subtitle-useless|potential_false_negative|semantic_selection + demonstrative_or_reference + short_answer|
|F300V1-0212|日常对话|青云语料|potential_false_negative|semantic_selection + short_answer|
|F300V1-0214|网络回帖|贴吧回帖|potential_false_negative|semantic_selection + demonstrative_or_reference|
|F300V1-0215|访谈语料|china_interview|potential_false_negative|semantic_selection + demonstrative_or_reference|
|F300V1-0216|日常对话|douban-multiturn-100w|potential_false_negative|semantic_selection + short_answer|
|F300V1-0217|文本对话|老乞大|potential_false_negative|semantic_selection + demonstrative_or_reference + short_answer|
|F300V1-0219|文本对话|世说新语|potential_false_negative|semantic_selection + demonstrative_or_reference|
|F300V1-0220|文本对话|孟子|potential_false_negative|semantic_selection + demonstrative_or_reference + analogy|
|F300V1-0223|文本对话|论语|potential_false_negative|semantic_selection + short_answer|
|F300V1-0224|文本对话|清平山堂话本|potential_false_negative|semantic_selection + demonstrative_or_reference + short_answer|
|F300V1-0226|文本对话|水浒传|potential_false_negative|semantic_selection + demonstrative_or_reference|
|F300V1-0227|文本对话|雷雨|potential_false_negative|semantic_selection + demonstrative_or_reference + short_answer|
|F300V1-0228|文本对话|唐传奇|potential_false_negative|semantic_selection + slot_filling + demonstrative_or_reference + short_answer|
|F300V1-0229|文本对话|朴通事|potential_false_negative|semantic_selection + demonstrative_or_reference + short_answer|
|F300V1-0230|文本对话|平凡的世界|potential_false_negative|semantic_selection + short_answer|
|F300V1-0231|文本对话|西游记|potential_false_negative|semantic_selection + demonstrative_or_reference|
|F300V1-0232|文本对话|骆驼祥子|potential_false_negative|semantic_selection + demonstrative_or_reference + short_answer|
|F300V1-0234|网络回帖|tieba-305w|potential_false_negative|semantic_selection + demonstrative_or_reference + short_answer|
|F300V1-0235|影视对白|subtitle-useless|potential_false_negative|semantic_selection + demonstrative_or_reference + short_answer|
|F300V1-0237|文本对话|朱子语类|potential_false_negative|semantic_selection + demonstrative_or_reference + short_answer|
|F300V1-0238|网络回帖|贴吧回帖|potential_false_negative|semantic_selection + short_answer + analogy|
|F300V1-0239|访谈语料|china_interview|potential_false_negative|semantic_selection + demonstrative_or_reference + short_answer|
|F300V1-0244|文本对话|孟子|potential_false_negative|semantic_selection + short_answer|
|F300V1-0245|文本对话|红楼梦|potential_false_negative|semantic_selection + short_answer|
|F300V1-0246|日常对话|chatterbot|potential_false_negative|semantic_selection + short_answer|
|F300V1-0247|文本对话|论语|potential_false_negative|semantic_selection + short_answer|
|F300V1-0250|文本对话|水浒传|potential_false_negative|semantic_selection + demonstrative_or_reference|
|F300V1-0251|文本对话|雷雨|potential_false_negative|semantic_selection + demonstrative_or_reference + short_answer|
|F300V1-0252|文本对话|唐传奇|potential_false_negative|semantic_selection + demonstrative_or_reference|
|F300V1-0253|文本对话|朴通事|potential_false_negative|semantic_selection + short_answer|
|F300V1-0254|文本对话|平凡的世界|potential_false_negative|semantic_selection + demonstrative_or_reference + short_answer|
|F300V1-0255|文本对话|西游记|potential_false_negative|semantic_selection + slot_filling + demonstrative_or_reference + short_answer|
|F300V1-0256|文本对话|骆驼祥子|potential_false_negative|semantic_selection + short_answer|
|F300V1-0259|影视对白|subtitle-useless|potential_false_negative|semantic_selection + demonstrative_or_reference|
|F300V1-0260|日常对话|青云语料|potential_false_negative|semantic_selection + demonstrative_or_reference + short_answer|
|F300V1-0261|文本对话|朱子语类|potential_false_negative|semantic_selection + slot_filling + demonstrative_or_reference + short_answer|
|F300V1-0263|日常对话|douban-multiturn-100w|potential_false_negative|semantic_selection + demonstrative_or_reference + short_answer|
|F300V1-0265|文本对话|世说新语|potential_false_negative|semantic_selection|
|F300V1-0266|文本对话|孟子|potential_false_negative|semantic_selection + demonstrative_or_reference + short_answer|
|F300V1-0268|文本对话|论语|potential_false_negative|semantic_selection + demonstrative_or_reference + short_answer|
|F300V1-0269|文本对话|清平山堂话本|potential_false_negative|semantic_selection + short_answer|
|F300V1-0270|日常对话|qingyun-11w|potential_false_negative|semantic_selection + short_answer|
|F300V1-0279|影视对白|subtitle-useless|analogy_or_parallel_candidate|semantic_selection + short_answer + analogy|
|F300V1-0282|文本对话|清平山堂话本|analogy_or_parallel_candidate|semantic_selection + demonstrative_or_reference|
|F300V1-0285|文本对话|世说新语|analogy_or_parallel_candidate|semantic_selection + short_answer|
|F300V1-0293|文本对话|雷雨|analogy_or_parallel_candidate|semantic_selection + demonstrative_or_reference|

## question_response false positive analysis

- count: 17
- samples: F300V1-0004, F300V1-0011, F300V1-0022, F300V1-0029, F300V1-0035, F300V1-0062, F300V1-0064, F300V1-0066, F300V1-0070, F300V1-0071, F300V1-0078, F300V1-0090, F300V1-0156, F300V1-0179, F300V1-0201, F300V1-0278, F300V1-0294

## False negative type analysis

- semantic_selection: 97
- demonstrative_or_reference: 62
- short_answer: 68
- slot_filling: 12
- analogy: 6

## Conclusion

规则 precision 较高，但 recall 不足，主要漏掉 semantic_selection / slot_filling / demonstrative_or_reference / short_answer 等隐性承接类型。
