GUIDE_NAV_ITEMS = [
    {"id": "intro", "label": "一、简介"},
    {"id": "corpus", "label": "二、语料构成"},
    {"id": "methods", "label": "三、主要检索方式"},
    {"id": "examples", "label": "四、检索式示例"},
    {"id": "advanced", "label": "五、高级检索字段"},
    {"id": "results", "label": "六、结果展示与统计"},
    {"id": "multimodal", "label": "七、多模态与音频说明"},
    {"id": "usage", "label": "八、使用与引用"},
    {"id": "faq", "label": "九、常见问题"},
]

GUIDE_OVERVIEW_CARDS = [
    {
        "title": "检索对象",
        "body": "平台以汉语对话性材料为主要对象，覆盖日常交际、影视对白、文本对话、网络互动、访谈、课堂互动和多模态记录等多种来源。",
    },
    {
        "title": "匹配单位",
        "body": "普通检索和正则检索通常以当前话轮或当前片段为基本匹配单位，不自动跨越前后多个话轮进行拼接匹配。",
    },
    {
        "title": "结果回溯",
        "body": "检索结果页提供居中检索视图、完整对话视图、上下文展开以及来源信息，便于研究者进行复核、引用与回溯。",
    },
]

GUIDE_INTRO_PARAGRAPHS = [
    "“汉语对话语料库”是在“对话转向”理论视野下建设的汉语互动语料检索平台。平台以真实互动和对话过程为核心，收录日常对话、影视对白、网络互动、访谈语料、课堂交流、多模态材料及古代汉语对话等多个子库，服务于对话句法、互动语言学、话语分析、语用学、语体差异和历时/跨类型比较等研究方向。",
    "本平台并不只将对话材料视为静态语言资源，而是强调语言形式与互动功能之间的关联。用户可通过普通检索、正则检索、高级检索和对话句法检索，观察具体表达在不同语料类型、不同说话人关系和不同上下文环境中的使用方式。检索结果将尽可能保留语料类型、来源、标题、说话人、年份、对话编号及媒体相关信息，以支持样例回溯、课堂展示、研究取例和后续分析。具体语料规模以检索页实时统计为准。",
]

GUIDE_CORPUS_ROWS = [
    {
        "corpus_type": "日常对话",
        "main_content": "日常交际中的自然话轮。",
        "research_use": "可用于口语表达、应答结构、话轮转换和高频回应方式研究。",
        "remark": "适合初步观察口语中的常见表达及互动惯例。",
    },
    {
        "corpus_type": "影视对白",
        "main_content": "影视剧本或字幕中的人物对白。",
        "research_use": "可用于虚构对话、人物语言风格和语体分析。",
        "remark": "适合比较口语化写作与自然会话的差异。",
    },
    {
        "corpus_type": "古代汉语",
        "main_content": "古代文献中的对话性材料。",
        "research_use": "可用于历时比较和传统对话结构研究。",
        "remark": "材料来源和时间跨度较大，宜结合来源信息判断。",
    },
    {
        "corpus_type": "文本对话",
        "main_content": "小说、戏剧、叙事文本中的对话片段。",
        "research_use": "可用于文学对话与人物互动研究。",
        "remark": "适合观察书面叙事环境中的对话组织方式。",
    },
    {
        "corpus_type": "网络回帖",
        "main_content": "网络平台中的互动性文本。",
        "research_use": "可用于网络话语、回应格式和立场表达研究。",
        "remark": "适合观察非正式书面互动的表达特点。",
    },
    {
        "corpus_type": "访谈语料",
        "main_content": "问答式访谈文本。",
        "research_use": "可用于机构话语、提问方式和回应策略研究。",
        "remark": "较适合观察制度化问答场景中的互动结构。",
    },
    {
        "corpus_type": "课堂互动",
        "main_content": "课堂场景中的师生互动。",
        "research_use": "可用于教学话语、反馈方式和课堂提问研究。",
        "remark": "不同课堂类型之间可能存在明显语体差异。",
    },
    {
        "corpus_type": "多模态语料",
        "main_content": "带有音频或相关媒体信息的对话记录。",
        "research_use": "可用于语音、停顿、转写文本与互动结构的综合观察。",
        "remark": "是否可在线播放受数据来源与授权状态影响。",
    },
]

GUIDE_METHOD_ROWS = [
    {
        "method_name": "普通检索",
        "target_text": "适合查找单词、短语或固定表达。",
        "description": "用于检索包含某一词语或短语的话轮，适合初步观察表达分布与使用场景。",
        "example_text": "你好、我觉得、没关系",
    },
    {
        "method_name": "正则检索",
        "target_text": "适合查找带有变体、间隔或边界限制的表达。",
        "description": "用于检索包含可变成分、距离限制、字符集合或位置边界的表达形式。",
        "example_text": "下次.*见、吃.{0,6}饭、^你好|见$",
    },
    {
        "method_name": "高级检索",
        "target_text": "适合限定字段、语料类型、说话人、标题、年份、正文长度或是否包含音频。",
        "description": "在同一检索能力上增加范围、字段和排序等限定条件，适合更细致地控制结果集合。",
        "example_text": "按来源、标题、说话人、年份范围或是否带音频进行筛选",
    },
    {
        "method_name": "对话句法检索",
        "target_text": "适合观察相邻话轮之间的回应、承接、重复、类比、否定、补全等互动关系。",
        "description": "用于从相邻话轮关系出发观察对话结构，而不是仅检索某个词语或短语。",
        "example_text": "承接、回应、重复、否定、补全等互动关系",
    },
]

GUIDE_QUERY_EXAMPLE_ROWS = [
    {
        "purpose": "查找固定表达",
        "query_text": "我觉得",
        "description": "检索包含“我觉得”的话轮。",
    },
    {
        "purpose": "查找问候语",
        "query_text": "你好",
        "description": "检索包含“你好”的话轮。",
    },
    {
        "purpose": "查找否定回应",
        "query_text": "没关系",
        "description": "检索常见否定或缓和性回应表达。",
    },
    {
        "purpose": "查找“下次……见”",
        "query_text": "下次.*见",
        "description": "用于正则检索，匹配“下次见”“下次有空见”等变体，仅在单个话轮或当前片段内匹配，不自动跨话轮。",
    },
    {
        "purpose": "查找“吃……饭”",
        "query_text": "吃.{0,6}饭",
        "description": "用于正则检索，匹配“吃饭”“吃个晚饭”“吃完再去吃饭”等表达，仅在单个话轮或当前片段内匹配，不自动跨话轮。",
    },
    {
        "purpose": "查找话轮开头的“你好”",
        "query_text": "^你好",
        "description": "用于正则检索，限定表达出现在话轮开头，仅在单个话轮或当前片段内匹配。",
    },
    {
        "purpose": "查找话轮结尾的“吧/吗/呢”",
        "query_text": "[吧吗呢]$",
        "description": "用于正则检索，观察语气词结尾，仅在单个话轮或当前片段内匹配。",
    },
]

GUIDE_ADVANCED_FIELD_ROWS = [
    {
        "field_name": "检索字段",
        "field_role": "限定关键词在正文、标题、说话人或当前话轮中匹配。",
        "field_scenario": "适合区分“正文命中”和“标题命中”，或只观察当前话轮中的表达。",
    },
    {
        "field_name": "匹配方式",
        "field_role": "可选择包含、精确匹配或正则匹配。",
        "field_scenario": "适合在固定表达、边界限制和形式变体之间切换。",
    },
    {
        "field_name": "排除词",
        "field_role": "排除包含特定词语或表达的结果。",
        "field_scenario": "适合缩小噪音较多的结果集合。",
    },
    {
        "field_name": "语料类型",
        "field_role": "限定日常对话、访谈语料、文本对话、古代汉语等来源板块。",
        "field_scenario": "适合做跨类型比较，或仅检索某一类材料。",
    },
    {
        "field_name": "标题/作品/来源",
        "field_role": "限定某一作品、节目、访谈或数据来源。",
        "field_scenario": "适合回到特定作品、栏目或语料集合内部继续检索。",
    },
    {
        "field_name": "说话人",
        "field_role": "限定带有说话人标注的材料。",
        "field_scenario": "适合观察某一角色、主持人、采访者或受访者的表达方式。",
    },
    {
        "field_name": "年份/时间范围",
        "field_role": "限定材料的时间范围。",
        "field_scenario": "适合做历时比较或阶段性比较。",
    },
    {
        "field_name": "正文长度",
        "field_role": "排除过短或过长的话轮。",
        "field_scenario": "适合控制结果长度，便于初步取例。",
    },
    {
        "field_name": "是否带音频",
        "field_role": "限定保存了可访问音频信息的记录。",
        "field_scenario": "仅表示该条记录保存了与音频相关的元数据或访问路径，不等于所有原始音频均可在线播放。",
    },
]

GUIDE_ADVANCED_FIGURE = {
    "image_path": "guide-images/guide-advanced-search.png",
    "image_alt": "高级检索界面示例截图",
}

GUIDE_RESULT_SECTIONS = [
    {
        "title": "居中检索视图",
        "body": "居中检索视图以命中表达为中心展示左右上下文，适合快速观察搭配、共现和局部语境。研究者可据此判断命中表达是否符合预期形式，并据需要继续展开上下文。",
        "image_path": "guide-images/guide-results-ccl.png",
        "image_alt": "居中检索视图示例截图",
        "caption": "图 1. 居中检索视图示例：结果摘要栏、视图切换、命中话轮、来源信息与上下文入口同时可见。",
    },
    {
        "title": "完整对话视图",
        "body": "完整对话视图展示命中话轮所在的完整对话或较大上下文，适合观察话题推进、回应结构和话轮衔接。对于需要判断跨话轮关系的研究问题，应优先结合该视图使用。",
        "image_path": "guide-images/guide-results-dialogue.png",
        "image_alt": "完整对话视图示例截图",
        "caption": "图 2. 完整对话视图示例：命中话轮被置于完整对话结构中，便于观察说话人顺序、回应位置与局部衔接。",
    },
    {
        "title": "统计结果",
        "body": "高频词或正则检索可能先显示当前页统计，再在后台补充精确总数。页面若显示“统计中”，表示系统仍在计算完整结果；此时当前页结果已可用于初步观察。",
    },
    {
        "title": "上下文按钮",
        "body": "上下文按钮用于展开命中项所在的局部对话环境，帮助研究者判断检索结果是否符合研究目标，并检查命中表达在前后话轮中的互动位置。",
        "image_path": "guide-images/guide-results-context.png",
        "image_alt": "上下文展开示例截图",
        "caption": "图 3. 上下文展开示例：点击结果页中的“上下文”后，可查看命中话轮、相邻话轮及相关来源元数据。",
    },
    {
        "title": "来源信息",
        "body": "每条结果应尽量保留语料类型、标题、来源、说话人、年份、对话 ID 或页面链接等信息，以便研究引用和结果回溯。",
    },
]

GUIDE_MULTIMODAL_PARAGRAPHS = [
    "“只看带音频”表示该条记录中保存了与音频相关的元数据或访问路径。由于原始材料的公开权限、托管状态、授权边界和文件格式可能不同，页面能显示音频信息并不意味着所有音频均可在线播放。",
    "研究者引用多模态材料时，应同时记录语料类型、来源、时间范围、数据集名称和检索日期。若检索结果需要作为音频或视频证据使用，还应进一步核查原始媒体的可访问状态与授权说明。",
]

GUIDE_USAGE_PARAGRAPHS = [
    "本平台检索结果可用于课堂展示、课程论文、研究取例和现象观察。引用检索结果时，建议至少保留检索词、检索日期、语料类型、数据来源、标题/作品名、说话人信息、对话 ID 或页面链接。若研究结论依赖音频、视频或多模态样例，还应记录时间戳、媒体来源和授权状态。",
    "数据来源、许可和展示边界以站内“数据来源与许可说明”为准。不得默认将站内检索结果视为可自由再分发或商业使用的数据。",
]

GUIDE_FAQ_ITEMS = [
    {
        "question": "普通搜索框可以直接使用正则表达式吗？",
        "answer_paragraphs": [
            "普通搜索框主要用于词语、短语和固定表达的字面检索。为兼容部分检索习惯，当输入内容具有明显的正则表达式特征时，系统可尝试按正则方式进行匹配；但自动识别可能受到特殊字符、转义符号和边界条件的影响。因此，若检索目标涉及变体形式、间隔字数、话轮开头或结尾等条件，建议使用“正则检索”或“高级检索”中的匹配方式设置，以获得更稳定、可解释的结果。",
            "例如，检索“我觉得”时可直接使用普通检索；若需要查找“吃……饭”“下次……见”等形式，则更适合使用正则表达式。",
        ],
    },
    {
        "question": "为什么正则检索不会跨前后话轮匹配？",
        "answer_paragraphs": [
            "本语料库以“话轮”或“文本片段”作为基本检索单位。正则检索默认只在当前话轮或当前片段内部执行，不自动跨越前后话轮。这一设计是为了保留对话语料中的说话人边界、话轮顺序和互动结构，避免将不同说话人的相邻话轮误合并为一个连续文本。",
            "如果研究目标涉及跨话轮回应、承接、重复、否定、补全或类比等互动关系，建议在结果页使用“完整对话视图”或“上下文”功能观察相邻话轮；涉及对话句法关系的研究，也可结合“对话句法检索”进一步分析。",
        ],
    },
    {
        "question": "为什么结果页会显示“统计中”？",
        "answer_paragraphs": [
            "当检索词频较高、检索范围较大，或使用较复杂的正则表达式时，系统可能会先返回当前页结果，以保证页面响应速度；完整命中数量则由后台继续计算。因此，页面显示“统计中”并不表示检索失败，而是表示完整统计结果尚未计算完成。",
            "在这种情况下，当前页结果已经可以用于初步观察和样例筛选；若需要引用总频次或进行定量统计，应等待系统补全精确总数，或在限定语料类型、年份范围、来源板块后重新检索。",
        ],
    },
    {
        "question": "为什么有些结果没有说话人？",
        "answer_paragraphs": [
            "部分语料来源本身没有可靠的说话人标注，或原始材料只保留了对话内容而未保存发话者信息。因此，结果中说话人字段为空，通常表示该条记录缺少可核验的说话人元数据，并不代表系统在展示过程中删除了相关信息。",
            "在使用这类结果时，研究者应根据研究目的谨慎处理。如果研究问题依赖说话人身份、角色关系或机构话语身份，建议优先选择带有明确说话人标注的材料；如果研究重点是表达形式、话轮结构或语用功能，则无说话人标注的材料仍可作为文本对话样例使用，但引用时应注明其元数据限制。",
        ],
    },
    {
        "question": "为什么有些多模态记录能看到转写，却播放不了音频？",
        "answer_paragraphs": [
            "“带音频”或“多模态”标记通常表示该条记录保存了与音频相关的元数据、转写文本或访问路径，但并不等同于所有原始音频均可在线播放。音频播放状态可能受到文件托管方式、公开权限、授权边界、格式转换和数据整理进度等因素影响。",
            "因此，这类记录可以作为文本转写材料使用；但如果研究结论依赖语音、停顿、重音、语调或其他听觉证据，应进一步核查原始音频的可访问性、来源信息和授权状态，并在引用时记录语料类型、数据来源、检索日期及必要的时间戳信息。",
        ],
    },
]


def build_guide_context(resonance_search_enabled=False):
    method_rows = list(GUIDE_METHOD_ROWS)
    if not resonance_search_enabled:
        method_rows = [
            dict(row, example_text="若当前站点开放该入口，可用于观察相邻话轮互动关系")
            if row["method_name"] == "对话句法检索"
            else row
            for row in method_rows
        ]

    return {
        "guide_nav_items": GUIDE_NAV_ITEMS,
        "guide_overview_cards": GUIDE_OVERVIEW_CARDS,
        "guide_intro_paragraphs": GUIDE_INTRO_PARAGRAPHS,
        "guide_corpus_rows": GUIDE_CORPUS_ROWS,
        "guide_method_rows": method_rows,
        "guide_query_example_rows": GUIDE_QUERY_EXAMPLE_ROWS,
        "guide_advanced_field_rows": GUIDE_ADVANCED_FIELD_ROWS,
        "guide_advanced_figure": GUIDE_ADVANCED_FIGURE,
        "guide_result_sections": GUIDE_RESULT_SECTIONS,
        "guide_multimodal_paragraphs": GUIDE_MULTIMODAL_PARAGRAPHS,
        "guide_usage_paragraphs": GUIDE_USAGE_PARAGRAPHS,
        "guide_faq_items": GUIDE_FAQ_ITEMS,
        "resonance_search_enabled": resonance_search_enabled,
    }
