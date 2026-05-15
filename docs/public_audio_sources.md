# 公开音频/多模态语料接入方案

本文档用于规划公开语音语料的小样本接入。当前阶段只做元数据设计和人工筛选规范，不下载大文件、不导入全量数据、不修改 `corpus.db`。

## 接入原则

- 只做小样本导入：每个数据集先选 20-200 条，优先覆盖不同说话人、场景、口音、时长。
- 只导入可明确授权的片段：保留原始来源、许可证、下载页或论文页。
- 优先保存音频对象键，不把外部下载链接直接当作生产播放地址。
- 朗读型数据只作为普通话发音、ASR 校验和基线展示；对话型、多说话人、多领域数据优先进入现代汉语对话语料库主展示。
- 每条样本必须有准确 `start_time`、`end_time`、转写文本和许可证说明。
- 若许可证限制再分发，网站只展示元数据、转写和来源链接，不公开托管音频。

## 候选数据集评估

| 数据集 | 类型 | 是否适合现代汉语对话语料库 | 推荐导入规模 | 版权/许可证注意事项 | 建议网站展示方式 |
| --- | --- | --- | --- | --- | --- |
| AISHELL-1 | 朗读 | 中等适合。普通话质量高，但以朗读句子为主，不是自然对话；适合做语音检索和发音样例。 | 先导入 50-100 条短句，覆盖不同说话人和句长。 | 官方 OpenSLR 页面说明免费用于学术用途，导入前应保留 OpenSLR/AISHELL 来源和引用信息；避免把它包装成对话语料。 | 标记为“朗读语音”；展示转写、说话人信息、数据集名、许可证说明；可用于音频播放器小样本演示。 |
| MAGICDATA Mandarin Chinese Conversational Speech Corpus | 对话 | 高度适合。包含电话/移动设备采集的普通话对话，贴近现代汉语口语互动。 | 先导入 50-200 个片段，每段 5-20 秒，优先选双人话轮清晰的样本。 | 常见公开版本采用 CC BY-NC-ND 4.0 或非商业限制条款；不得商用，不应改编或再发布衍生数据；需要确认具体下载页条款。 | 标记为“对话语音”；网站可展示片段转写、轮次、说话人性别/年龄段等弱身份信息；若条款不允许再分发音频，则仅展示元数据和原始链接。 |
| WenetSpeech | 播客 / 多领域 | 高度适合做多领域现代汉语语音，含公开视频、访谈、播客、朗读等多种场景；但不是纯对话库，需要筛选。 | 先导入 50-150 个片段，优先选访谈、播客、对话式公开视频片段。 | WenetSpeech 官方说明音频版权归原始所有者，标注可能为弱监督/自动标注；使用前需核验原始来源和分发许可。不要直接镜像大规模音频。 | 标记为“多领域语音”；展示领域标签、原始 URL、转写置信来源；音频可只挂对象存储键或跳转原站。 |
| Common Voice Chinese | 朗读 | 中等适合。开放度高，但主要是志愿者朗读句子，不是对话；适合补充普通话/中文发音多样性。 | 先导入 100-200 条 validated 小样本，平衡口音、性别、年龄段。 | Mozilla Common Voice 数据通常使用 CC0；同时需遵守 Common Voice 条款，例如不得尝试识别贡献者，不要重托管或重分享语音剪辑集合。 | 标记为“开放朗读语音”；展示匿名说话人属性、转写、许可证；避免展示可识别个人身份的信息。 |
| THCHS-30 | 朗读 | 低到中等适合。中文朗读老牌数据集，音质和文本规范有价值，但现代对话性不足。 | 先导入 30-50 条作为历史/基线朗读样本。 | OpenSLR 分发页和原项目说明需要逐条确认；保留原始引用和使用说明。 | 标记为“朗读基线”；用于检索和播放器测试，不作为对话主样本。 |
| ST-CMDS | 朗读 | 中等适合。普通话朗读数据，覆盖多说话人；对话性不足。 | 先导入 50-100 条，选短句和不同说话人。 | OpenSLR 页面一般附带数据说明；导入前确认许可和引用要求。 | 标记为“朗读语音”；可展示为普通话短句样本。 |
| Primewords Chinese Corpus Set 1 | 朗读 / 多说话人 | 中等适合。规模较大、普通话朗读，适合作为开放朗读补充；不是自然对话。 | 先导入 50-100 条，避免全量导入。 | OpenSLR/Primewords 页面说明数据用途和授权，导入前确认是否允许再分发音频。 | 标记为“朗读语音”；展示数据集来源、转写和匿名说话人信息。 |

## 小样本接入流程

1. 人工确认许可证：保存数据集下载页、许可证页、论文页或 README 快照链接。
2. 人工抽样：只选短片段，优先 5-20 秒；对话数据优先选择完整话轮。
3. 人工准备音频：如允许托管，将小样本放到对象存储或本地测试目录；如不允许托管，只保留 `original_url`。
4. 生成 CSV：使用 `talkdata/import_ready/public_audio_samples_template.csv` 字段格式。
5. 预检 CSV：检查空字段、时间边界、许可证文本、重复 `audio_object_key`。
6. 试导入前备份数据库：只在明确确认后导入 20 条以内的样本批次。
7. 网站展示：按 `dataset_name`、`category`、`license` 做筛选和来源提示。

## 字段映射建议

| CSV 字段 | 建议含义 |
| --- | --- |
| `title` | 样本标题，建议包含数据集名和片段编号。 |
| `source` | 来源平台或项目，例如 `OpenSLR`、`Mozilla Common Voice`、`MAGICDATA`。 |
| `category` | 网站分类，例如 `公开语音语料`、`对话语音`、`朗读语音`、`多领域语音`。 |
| `dataset_name` | 标准数据集名。 |
| `transcript` | 该片段转写文本。 |
| `audio_object_key` | 对象存储键或本地音频文件名；未获授权托管时留空。 |
| `original_url` | 官方下载页、原始视频/播客页或样本来源页。 |
| `license` | 许可证名称和限制摘要。 |
| `speaker_info` | 匿名说话人信息，例如 `female, adult, Beijing accent`；不得包含可识别身份。 |
| `start_time` | 片段开始秒数。 |
| `end_time` | 片段结束秒数。 |

## 优先级建议

第一优先级是 MAGICDATA 和 WenetSpeech：它们更接近“现代汉语对话/多模态检索”的目标。MAGICDATA 更像真实对话语料，WenetSpeech 覆盖更广、适合展示多领域检索。AISHELL-1、Common Voice、THCHS-30、ST-CMDS、Primewords 更适合作为朗读型补充和播放器/检索基线。

## 参考来源

- AISHELL-1: https://www.openslr.org/33/
- MAGICDATA Mandarin Chinese Conversational Speech Corpus: https://www.openslr.org/68/
- WenetSpeech: https://github.com/wenet-e2e/WenetSpeech
- Mozilla Common Voice datasets: https://commonvoice.mozilla.org/datasets
- Mozilla Common Voice terms: https://commonvoice.mozilla.org/terms
- THCHS-30: https://www.openslr.org/18/
- ST-CMDS: https://www.openslr.org/38/
- Primewords Chinese Corpus Set 1: https://www.openslr.org/47/
