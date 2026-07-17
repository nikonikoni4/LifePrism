"""
Web-Demo 演示数据模板常量

所有模拟数据的内容模板集中管理，方便维护和扩展。
"""

# ==================== 应用列表 ====================

DEMO_APPS = [
    # (app, title, category_id, sub_category_id, is_multipurpose)
    ("Code.exe", "Visual Studio Code", "cat-work", "subcat-work-other", 1),
    ("codebuddy.exe", "CodeBuddy - Project Alpha", "cat-work", "subcat-work-other", 1),
    ("chrome.exe", "GitHub - repository", "cat-work", "subcat-work-other", 1),
    ("chrome.exe", "Stack Overflow - Question", "cat-work", "subcat-work-other", 1),
    ("chrome.exe", "Documentation - API Reference", "cat-study", "subcat-study-other", 1),
    ("chrome.exe", "YouTube - Tutorial", "cat-study", "subcat-study-other", 1),
    ("chrome.exe", "Bilibili - 影视", "cat-entertainment", "subcat-entertainment-other", 1),
    ("chrome.exe", "知乎 - 浏览", "cat-entertainment", "subcat-entertainment-other", 1),
    ("chrome.exe", "Gmail - Inbox", "cat-other", "subcat-other-other", 1),
    ("terminal.exe", "Terminal", "cat-work", "subcat-work-other", 0),
    ("spotify.exe", "Spotify", "cat-entertainment", "subcat-entertainment-other", 0),
    ("wechat.exe", "微信", "cat-other", "subcat-other-other", 0),
    ("notion.exe", "Notion - Notes", "cat-work", "subcat-work-other", 1),
    ("obsidian.exe", "Obsidian - Knowledge Base", "cat-study", "subcat-study-other", 0),
    ("steam.exe", "Steam", "cat-entertainment", "subcat-entertainment-other", 0),
    ("figma.exe", "Figma - Design", "cat-work", "subcat-work-other", 0),
]

# ==================== 行为分析模板 ====================

BEHAVIOR_TEMPLATES = [
    "编写代码，处理 {feature} 功能",
    "调试 {component} 模块的 bug",
    "查阅 {topic} 相关技术文档",
    "参加项目进度同步会议",
    "代码审查，review {module} 模块",
    "编写单元测试，覆盖 {feature} 场景",
    "重构 {component} 代码结构",
    "学习 {topic} 新技术框架",
    "浏览技术社区，了解行业动态",
    "整理项目文档和笔记",
    "回复消息、处理日常沟通",
    "规划设计 {feature} 的架构方案",
]

FEATURE_NAMES = [
    "用户认证",
    "数据同步",
    "消息推送",
    "文件上传",
    "搜索优化",
    "API 接口",
    "前端组件",
    "数据可视化",
    "性能优化",
    "错误处理",
]
COMPONENT_NAMES = ["core", "api", "frontend", "database", "auth", "notification", "storage"]
TOPIC_NAMES = [
    "React Hooks",
    "FastAPI 中间件",
    "SQLite 优化",
    "Docker 部署",
    "Redis 缓存",
    "WebSocket",
    "GraphQL",
    "RESTful API 设计",
]

# ==================== 心情条目模板 ====================

MOOD_TEMPLATES = [
    {
        "mood_type_id": "joy",
        "score": 90,
        "content": "今天完成了计划中的功能开发，代码运行顺利，感觉很有成就感",
    },
    {"mood_type_id": "calm", "score": 70, "content": "按部就班地推进项目，节奏稳定，心情平静"},
    {"mood_type_id": "calm", "score": 70, "content": "今天在阳台看了会儿书，阳光很好，感觉很舒适"},
    {
        "mood_type_id": "pensive",
        "score": 50,
        "content": "思考项目的下一步方向，有一些不确定性需要梳理",
    },
    {
        "mood_type_id": "pensive",
        "score": 50,
        "content": "看了一篇关于技术趋势的文章，引发对未来规划的思考",
    },
    {
        "mood_type_id": "melancholy",
        "score": 30,
        "content": "今天效率不高，感觉有些疲倦，需要调整节奏",
    },
    {"mood_type_id": "joy", "score": 90, "content": "运动后精神状态很好，感觉身体在慢慢恢复"},
    {"mood_type_id": "calm", "score": 70, "content": "散步时看到晚霞很美，记录下了这个瞬间"},
]

# ==================== 日焦点模板 ====================

DAILY_FOCUS_TEMPLATES = [
    "完成 {feature} 功能开发",
    "推进 {component} 模块重构",
    "学习 {topic} 并做笔记",
    "整理项目文档，补充 README",
    "修复已知 bug，提升代码质量",
    "设计 {feature} 方案并评审",
    "完成本周的代码审查工作",
]

# ==================== 习惯定义 ====================

DEMO_HABITS = [
    {
        "id": "hab-demo-001",
        "name": "晨间阅读",
        "description": "每天早上阅读至少 30 分钟",
        "frequency_type": "daily",
        "current_level": 2,
    },
    {
        "id": "hab-demo-002",
        "name": "每日运动",
        "description": "每天进行至少 20 分钟的运动",
        "frequency_type": "daily",
        "current_level": 1,
    },
    {
        "id": "hab-demo-003",
        "name": "冥想练习",
        "description": "每天冥想 10 分钟，培养正念",
        "frequency_type": "daily",
        "current_level": 1,
    },
    {
        "id": "hab-demo-004",
        "name": "写日记",
        "description": "每天记录当天的思考和感悟",
        "frequency_type": "daily",
        "current_level": 3,
    },
]

# ==================== 价值观 ====================

DEMO_VALUES = [
    {
        "id": "val-demo-001",
        "keywords": "持续成长;终身学习",
        "content_positive": "保持好奇心，不断学习新知识、新技能，在专业领域持续深耕",
        "content_negative": "不满足于现状，拒绝停滞和固步自封",
    },
    {
        "id": "val-demo-002",
        "keywords": "身心健康;自律",
        "content_positive": "关注身体和心理健康，通过规律运动、健康饮食和充足睡眠维持良好状态",
        "content_negative": "不因工作压力忽视身体信号，不长期透支健康",
    },
    {
        "id": "val-demo-003",
        "keywords": "创造价值;影响力",
        "content_positive": "通过技术能力创造对他人有用的产品，解决实际问题",
        "content_negative": "不做无意义的重复劳动，不满足于表面完成",
    },
    {
        "id": "val-demo-004",
        "keywords": "真实;自我接纳",
        "content_positive": "诚实地面对自己的感受和局限，接纳不完美的自己，同时努力改善",
        "content_negative": "不为了迎合他人而伪装，不过度自我批判",
    },
]

# ==================== 承诺 ====================

DEMO_COMMITMENTS = [
    {
        "id": "cmt-demo-001",
        "content": "每天阅读技术书籍或文章至少 30 分钟",
        "value_id": "val-demo-001",
        "status": "active",
    },
    {
        "id": "cmt-demo-002",
        "content": "每周完成至少 3 次运动训练",
        "value_id": "val-demo-002",
        "status": "active",
    },
    {
        "id": "cmt-demo-003",
        "content": "每天 23:00 前放下手机准备入睡",
        "value_id": "val-demo-002",
        "status": "active",
    },
    {
        "id": "cmt-demo-004",
        "content": "每季度发布一个开源项目或技术文章",
        "value_id": "val-demo-003",
        "status": "active",
    },
    {
        "id": "cmt-demo-005",
        "content": "每天写日记记录思考和感悟",
        "value_id": "val-demo-004",
        "status": "active",
    },
    {
        "id": "cmt-demo-006",
        "content": "每周回顾个人目标和进展",
        "value_id": "val-demo-001",
        "status": "active",
    },
]

# ==================== 日记模板 ====================

DIARY_TEMPLATES = [
    {
        "mood": "calm",
        "importance": "normal",
        "morning": "今天天气不错，早上起来后做了简单的拉伸。计划今天主要推进 {feature} 的开发工作。",
        "evening": "今天进展顺利，完成了大部分计划内容。下午抽空看了会儿书。\n\n### 今天最有价值的一件事情\n\n成功调试了一个困扰了两天的 bug，找到了根本原因。\n\n### 今天发生的好事情\n\n傍晚散步时看到了很美的夕阳。",
    },
    {
        "mood": "joy",
        "importance": "important",
        "morning": "昨晚睡眠质量不错，精神很好。今天计划完成 {feature} 的上线部署。",
        "evening": "今天效率很高！不仅完成了部署，还顺便优化了一些性能瓶颈。\n\n### 今天最有价值的一件事情\n\n发现了一个长期存在的性能问题并成功修复，响应时间降低了 60%。\n\n### 今天发生的好事情\n\n同事对我的代码重构方案表示认可，团队协作很顺畅。",
    },
    {
        "mood": "pensive",
        "importance": "important",
        "morning": "醒得比较早，想了很久关于项目下一步方向的事情。今天主要做技术调研。",
        "evening": "花了一天时间调研技术方案，有几个不错的选择需要进一步评估。\n\n### 今天最有价值的一件事情\n\n梳理清楚了技术选型的决策矩阵，后续方向更明确了。\n\n### 今天发生的好事情\n\n看了几篇高质量的技术文章，收获颇丰。",
    },
    {
        "mood": "calm",
        "importance": "normal",
        "morning": "今天状态一般，昨晚有点晚睡。准备从简单的任务开始，逐步进入状态。",
        "evening": "虽然开始有些困难，但逐渐进入状态后还是完成了不少工作。\n\n### 今天最有价值的一件事情\n\n重构了 {component} 模块的代码，可读性和可维护性都有提升。\n\n### 今天发生的好事情\n\n自己做了一顿简单的饭，味道还不错。",
    },
    {
        "mood": "melancholy",
        "importance": "normal",
        "morning": "天气有些阴沉，心情也有些低落。今天可能需要适当放松一下。",
        "evening": "今天工作效率不太高，有些任务没完成。提醒自己不要给自己太大压力。\n\n### 今天最有价值的一件事情\n\n意识到了自己最近有些过度工作，需要调整节奏。\n\n### 今天发生的好事情\n\n晚上泡了杯热茶，听着音乐发了一会儿呆，感觉放松了些。",
    },
    {
        "mood": "joy",
        "importance": "important",
        "morning": "今天是周末，计划做一些自己想做的事情：看书、运动、整理房间。",
        "evening": "度过了充实而放松的一天。运动后身体感觉很舒服。\n\n### 今天最有价值的一件事情\n\n花了两个小时深入阅读了一直想读的技术书籍，做了详细的笔记。\n\n### 今天发生的好事情\n\n整理完房间后感觉整个空间都清爽了许多。",
    },
    {
        "mood": "calm",
        "importance": "important",
        "morning": "新的一周开始，回顾了上周的进展并制定了本周计划。关键任务是 {feature}。",
        "evening": "周一的节奏控制得不错，完成了周计划的分解和任务分配。\n\n### 今天最有价值的一件事情\n\n制定了清晰的本周目标和任务分解，对接下来几天的工作有了明确方向。\n\n### 今天发生的好事情\n\n下班后在阳台看了会儿星星，夜空很清澈。",
    },
]

# ==================== 时间悖论模板 ====================

TIME_PARADOX_ENTRIES = [
    {
        "mode": "past",
        "content": (
            "回顾过去一年，最大的变化是在技术能力上的成长。从最初的简单 CRUD 到现在能够独立负责"
            "一个模块的架构设计。同时也意识到自己在沟通表达方面还有提升空间。过去的某些选择虽然"
            "当时看是困难的，但现在回头看都是必要的成长过程。"
        ),
        "ai_abstract": "过去一年的成长回顾：技术能力提升、独立架构设计能力建立，沟通表达仍需加强",
    },
    {
        "mode": "present",
        "content": (
            "当前状态：正在推进一个重要的项目迭代，同时在学习新的技术框架。日常在编码、学习、"
            "运动之间寻找平衡。有时会感到时间不够用的压力，但整体上对现在的状态还算满意。正在"
            "尝试更系统地管理自己的时间和精力。"
        ),
        "ai_abstract": "当前状态：项目推进+学习新技术，寻求工作与生活的平衡",
    },
    {
        "mode": "future",
        "content": (
            "对未来一年的期待：希望能够在专业领域有更深入的发展，完成至少一个有影响力的项目。"
            "同时也希望能保持健康的身体状态，养成长期的良好习惯。不给自己设太宏大的目标，专注"
            "于持续进步和积累。"
        ),
        "ai_abstract": "未来展望：专业深入发展、完成有影响力项目、保持健康习惯",
    },
]

# ==================== 目标日志模板 ====================

GOAL_JOURNAL_TEMPLATES = [
    {
        "goal_id": "goal-daily",
        "content": "今天按计划推进了项目开发，完成了计划中的主要任务",
        "mood": "calm",
        "duration": 240,
    },
    {
        "goal_id": "goal-daily",
        "content": "学习了新技术框架的基础概念，做了一些实践练习",
        "mood": "joy",
        "duration": 90,
    },
    {
        "goal_id": "goal-daily",
        "content": "今天效率一般，只完成了部分计划任务，需要调整节奏",
        "mood": "pensive",
        "duration": 120,
    },
    {
        "goal_id": "goal-example",
        "content": "完善了项目的文档结构，补充了关键模块的使用说明",
        "mood": "calm",
        "duration": 60,
    },
    {
        "goal_id": "goal-example",
        "content": "进行了代码审查，发现并修复了 2 个潜在问题",
        "mood": "joy",
        "duration": 45,
    },
]

# ==================== 待办事项模板 ====================

TODO_TEMPLATES = [
    # scheduled (在过去几天)
    {"content": "完成 {feature} 功能开发", "state": "completed", "link_to_goal_id": "goal-daily"},
    {
        "content": "代码审查：检查 {component} 模块",
        "state": "completed",
        "link_to_goal_id": "goal-daily",
    },
    {"content": "更新项目 README 文档", "state": "completed", "link_to_goal_id": "goal-example"},
    {
        "content": "修复 {component} 模块的高优先级 bug",
        "state": "completed",
        "link_to_goal_id": "goal-daily",
    },
    {"content": "学习 {topic} 核心概念", "state": "completed", "link_to_goal_id": "goal-daily"},
    {"content": "整理本周工作日志", "state": "completed", "link_to_goal_id": "goal-daily"},
    {"content": "编写 {feature} 单元测试", "state": "scheduled", "link_to_goal_id": "goal-daily"},
    {"content": "优化数据库查询性能", "state": "scheduled", "link_to_goal_id": "goal-daily"},
    {"content": "技术方案评审准备", "state": "scheduled", "link_to_goal_id": "goal-example"},
    {"content": "完成前端组件的响应式适配", "state": "scheduled", "link_to_goal_id": "goal-daily"},
    # pool
    {"content": "调研 WebSocket 长连接方案", "state": "pool", "link_to_goal_id": "goal-example"},
    {"content": "学习 Docker 容器化部署", "state": "pool", "link_to_goal_id": "goal-daily"},
    {"content": "搭建自动化 CI/CD 流水线", "state": "pool", "link_to_goal_id": "goal-example"},
    {"content": "编写 API 接口文档", "state": "pool", "link_to_goal_id": "goal-daily"},
    {"content": "设计数据缓存策略", "state": "pool", "link_to_goal_id": "goal-example"},
    # shelved
    {"content": "尝试搭建个人博客", "state": "shelved", "link_to_goal_id": None},
    {"content": "学习 Rust 编程语言", "state": "shelved", "link_to_goal_id": None},
]

# ==================== 自定义时间块模板 ====================

TIMELINE_BLOCK_TEMPLATES = [
    ("阅读时间", "cat-study", "subcat-study-other", "#5AD8A6"),
    ("运动锻炼", "cat-other", "subcat-other-other", "#F6BD16"),
    ("午休", "cat-other", "subcat-other-other", "#cbd5e1"),
    ("散步", "cat-other", "subcat-other-other", "#5AD8A6"),
    ("沟通讨论", "cat-work", "subcat-work-other", "#5B8FF9"),
    ("写日记", "cat-other", "subcat-other-other", "#E8684A"),
    ("专注开发", "cat-work", "subcat-work-other", "#5B8FF9"),
    ("思考规划", "cat-work", "subcat-work-other", "#F6BD16"),
]

# ==================== 行为日志时间段偏好 ====================

WORK_BLOCKS = [
    (8, 12, 0.7),  # 上午：70% 工作类应用
    (13, 18, 0.65),  # 下午：65% 工作类
    (19, 23, 0.3),  # 晚上：30% 工作类
]

# ==================== 自定义记录模板 ====================

DEMO_CUSTOM_RECORDS = [
    {
        "type_id": "crt-demo-reading",
        "name": "读书记录",
        "slug": "reading",
        "description": "记录每日阅读情况，包括书名、时长和笔记",
        "icon": "bookOpen",
        "accent_color": "blue",
        "fields": [
            {
                "id": "crf-demo-r1",
                "field_name": "书名",
                "field_key": "book_name",
                "field_type": "text",
                "sort_order": 0,
                "display_role": "title",
            },
            {
                "id": "crf-demo-r2",
                "field_name": "阅读时长",
                "field_key": "reading_time",
                "field_type": "text",
                "sort_order": 1,
                "display_role": "chip",
            },
            {
                "id": "crf-demo-r3",
                "field_name": "读书笔记",
                "field_key": "note",
                "field_type": "text",
                "sort_order": 2,
                "display_role": "main",
            },
        ],
        "entries": [
            {
                "book_name": "《深入浅出设计模式》",
                "reading_time": "45分钟",
                "note": "学习了策略模式和观察者模式，对解耦有了更深的理解。策略模式适合算法族的切换场景，观察者模式适合一对多的事件通知。",
            },
            {
                "book_name": "《代码整洁之道》",
                "reading_time": "30分钟",
                "note": "重新审视了函数命名的重要性，好的命名可以让代码自解释。决定从明天开始重构一些旧代码的命名。",
            },
            {
                "book_name": "《原子习惯》",
                "reading_time": "25分钟",
                "note": "习惯的形成需要四个步骤：提示、渴求、回应、奖励。小习惯比大目标更容易坚持。",
            },
            {
                "book_name": "《程序员修炼之道》",
                "reading_time": "40分钟",
                "note": "破窗理论很有启发——不要容忍任何一处糟糕的代码或设计，它们会像破窗一样引发更多的问题。",
            },
            {
                "book_name": "《思考，快与慢》",
                "reading_time": "35分钟",
                "note": "系统1和系统2的区分很精妙。很多直觉判断实际上来自系统1的快速模式匹配，需要警惕认知偏差。",
            },
            {
                "book_name": "《重构：改善既有代码的设计》",
                "reading_time": "50分钟",
                "note": "学习了提炼函数、内联变量等重构手法。小步快跑、频繁测试是安全重构的关键。",
            },
            {
                "book_name": "《软技能：代码之外的生存指南》",
                "reading_time": "30分钟",
                "note": "除了技术能力，职业规划、个人品牌、健康管理同样重要。打算开始写技术博客。",
            },
        ],
    },
    {
        "type_id": "crt-demo-exercise",
        "name": "锻炼记录",
        "slug": "exercise",
        "description": "记录每日运动锻炼情况，包括类型、时长和感受",
        "icon": "heart",
        "accent_color": "green",
        "fields": [
            {
                "id": "crf-demo-e1",
                "field_name": "锻炼类型",
                "field_key": "exercise_type",
                "field_type": "text",
                "sort_order": 0,
                "display_role": "title",
            },
            {
                "id": "crf-demo-e2",
                "field_name": "时长",
                "field_key": "duration",
                "field_type": "text",
                "sort_order": 1,
                "display_role": "chip",
            },
            {
                "id": "crf-demo-e3",
                "field_name": "感受",
                "field_key": "feeling",
                "field_type": "text",
                "sort_order": 2,
                "display_role": "main",
            },
        ],
        "entries": [
            {
                "exercise_type": "跑步",
                "duration": "30分钟",
                "feeling": "傍晚沿着河边跑了3公里，配速6分左右。天气凉爽，跑完浑身舒畅，感觉一天的疲劳都消散了。",
            },
            {
                "exercise_type": "力量训练",
                "duration": "40分钟",
                "feeling": "做了俯卧撑、深蹲和哑铃推举。上肢力量有明显进步，俯卧撑能连做25个了。",
            },
            {
                "exercise_type": "瑜伽",
                "duration": "25分钟",
                "feeling": "跟视频做了一套肩颈放松的瑜伽。拉伸后肩膀和背部舒服多了，适合久坐后的恢复。",
            },
            {
                "exercise_type": "游泳",
                "duration": "45分钟",
                "feeling": "蛙泳800米，自由泳400米。水中的感觉很好，全身肌肉都得到了锻炼，游完特别饿。",
            },
            {
                "exercise_type": "骑行",
                "duration": "60分钟",
                "feeling": "周末骑行去了郊外，往返约15公里。沿途风景不错，呼吸新鲜空气心情也变好了。",
            },
            {
                "exercise_type": "HIIT",
                "duration": "20分钟",
                "feeling": "高强度间歇训练，做完大汗淋漓。虽然时间短但消耗很大，心率一度飙到170，心肺功能在提升。",
            },
            {
                "exercise_type": "散步",
                "duration": "40分钟",
                "feeling": "晚饭后在公园散步，步伐不快。边走路边听了会播客，放松身心的好方式。",
            },
        ],
    },
]
