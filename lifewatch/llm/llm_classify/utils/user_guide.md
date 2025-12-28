
# LifePrism 用户使用指南 📖

> **本文档为 AI 助手提供完整的功能参考，用于向用户介绍和解释项目的各项功能及使用方法。**

---

## 项目概述

```json
{
    "id": "project-overview",
    "title": "项目概述",
    "abstract": "LifePrism 是一个 AI 驱动的自我量化与目标管理系统，通过 AI 技术实现时间、目标与自我认知的深度融合，构建'数据-分析-执行'的闭环。",
    "keywords": ["LifePrism", "自我量化", "目标管理", "AI分类", "时间追踪", "ActivityWatch"],
    "items": ["什么是 LifePrism", "核心能力", "迭代计划", "长期愿景", "核心价值", "数据来源", "数据处理过程"],
    "content": [
        {
            "id": "what-is-lifeprism",
            "title": "什么是 LifePrism",
            "abstract": "LifePrism是一个 AI 驱动的自我量化与目标管理系统，旨在通过 AI 技术实现时间、目标与自我认知的深度融合。",
            "keywords": []
        },
        {
            "id": "core-capabilities",
            "title": "核心能力（已上线）",
            "abstract": "系统已上线的核心功能模块，包括数据采集、AI分类、目标管理和AI对话。",
            "keywords": ["数据采集", "AI分类", "可视化", "目标管理", "AI对话"],
            "items": ["全渠道数据采集", "AI 智能分类与可视化", "目标驱动系统", "AI 交互对话"],
            "content": [
                {
                    "title": "全渠道数据采集",
                    "abstract": "整合多种数据来源通道，确保量化的全面性。(目前只上线电脑端，通过 ActivityWatch 收集数据)"
                },
                {
                    "title": "AI 智能分类与可视化",
                    "abstract": "自动处理原始数据并生成直观的分析图表。"
                },
                {
                    "title": "目标驱动系统",
                    "abstract": "模块化管理个人目标与执行进度。"
                },
                {
                    "title": "AI 交互对话",
                    "abstract": "提供基于上下文的智能助手服务。"
                }
            ]
        },
        {
            "id": "iteration-plan",
            "title": "迭代计划（开发中）",
            "abstract": "正在开发的功能模块，包括智能日记和AI定制化总结报告。",
            "keywords": ["智能日记", "AI总结报告", "情绪轨迹"],
            "items": ["智能日记模块", "AI 定制化总结报告"],
            "content": [
                {
                    "title": "智能日记模块",
                    "abstract": "探索结构化记录与情绪轨迹的自动捕捉。"
                },
                {
                    "title": "AI 定制化总结报告",
                    "abstract": "周期性生成多维度的自我洞察报告。"
                }
            ]
        },
        {
            "id": "long-term-vision",
            "title": "长期愿景",
            "abstract": "LifePrism 将进化为支持自我察觉、深度反思、自我定义与自我关怀的伙伴，参考接纳承诺疗法（ACT）六角模型。",
            "keywords": ["ACT", "接纳承诺疗法", "认知解离", "接纳", "自我关怀"],
            "items": ["认知与存在层面", "觉察层面", "行动层面"],
            "content": [
                {
                    "title": "认知与存在层面",
                    "abstract": "通过'AI 日记'与'对话'功能，辅助用户实现认知解离与接纳，通过 AI 的中立视角引导用户观察而非陷入情绪。"
                },
                {
                    "title": "觉察层面",
                    "abstract": "利用数据采集与可视化，帮助用户接触当下，建立以己为景的观察者视角，从繁杂的日常数据中抽离，审视生命全景。"
                },
                {
                    "title": "行动层面",
                    "abstract": "将目标管理与价值导向深度绑定，确保每一项承诺行动都指向用户内心深处真正的价值方向。"
                }
            ]
        },
        {
            "id": "core-values",
            "title": "核心价值",
            "abstract": "LifePrism 的四大核心功能价值：AI分类、可视化分析、目标管理、AI对话。",
            "keywords": ["AI分类", "可视化分析", "目标管理", "AI对话"],
            "content": [
                {
                    "title": "AI 分类",
                    "abstract": "智能识别应用用途（学习、工作、娱乐等）。"
                },
                {
                    "title": "可视化分析",
                    "abstract": "旭日图、柱状图、时间线等多维度展示。"
                },
                {
                    "title": "目标管理",
                    "abstract": "设定目标，管理待办事项。"
                },
                {
                    "title": "AI 对话",
                    "abstract": "智能助手回答问题，提供个性化建议。"
                }
            ]
        },
        {
            "id": "data-sources",
            "title": "数据来源",
            "abstract": "系统支持的数据来源渠道及其当前状态。",
            "keywords": ["ActivityWatch", "数据来源", "数据采集"],
            "content": [
                {
                    "title": "ActivityWatch",
                    "abstract": "主要数据来源（必须安装）。"
                },
                {
                    "title": "用户备注",
                    "abstract": "在timeline页面可自行添加。"
                },
                {
                    "title": "移动端使用数据",
                    "abstract": "未开发。"
                },
                {
                    "title": "其他电子穿戴设备",
                    "abstract": "未开发。"
                }
            ]
        },
        {
            "id": "data-processing",
            "title": "数据处理过程",
            "abstract": "数据从 ActivityWatch 采集到前端展示的完整流程：ActivityWatch → LifePrism后端 → LLM分类 → SQLite数据库 → API → React前端。",
            "keywords": ["数据流程", "LLM分类", "SQLite", "API", "React"]
        }
    ]
}
```

---

## HomePage首页
```json
{
  "id": "home",
  "title": "首页",
  "abstract": "首页提供当日活动概览，包含数据同步功能、待办事项展示、时间使用情况可视化",
  "keywords": ["首页", "仪表盘", "数据同步", "待办事项", "时间概览"],
  "items": ["ActivitySummary", "Today's Focus", "Time Overview", "Activity Details"],
  "content": [
      {
        "id": "activity-summary",
        "title": "ActivitySummary（活动趋势图）",
        "abstract": "展示过去14天的时间使用趋势，支持数据同步和分类筛选。",
        "keywords": ["时间趋势", "柱状图", "同步数据", "分类筛选"],
        "items": ["柱形图交互", "日期选择器", "refresh按钮", "filter按钮", "sync Data按钮"],
        "content": [
            {
                "title": "柱形图交互",
                "abstract": "点击柱形图中的任意柱形，可切换查看该日期的详细数据。"
            },
            {
                "title": "日期选择器",
                "abstract": "点击日期选择器，可选择任意历史日期查看数据。"
            },
            {
                "title": "refresh按钮",
                "abstract": "增量同步数据。从数据库最新记录时间同步到当前时间，速度快。"
            },
            {
                "title": "filter按钮",
                "abstract": "按分类筛选显示数据。可选择只显示特定分类（如工作、学习）的时间趋势。分类在 Category 页面管理。"
            },
            {
                "title": "sync Data按钮",
                "abstract": "时间范围同步。可指定起止日期从 ActivityWatch 同步数据。注意：会覆盖已存在的数据。但只要map cache不变，得到的数据也不会变化"
            }
        ]
      },
      {
        "id": "todays-focus",
        "title": "Today's Focus（待办事项）",
        "abstract": "显示当日待办任务，可快速跳转到目标管理页面。",
        "keywords": ["待办事项", "TodoList", "任务"],
        "items": ["展开按钮"],
        "content": [
            {
                "title": "展开按钮（>号）",
                "abstract": "点击右上方或右下方的 > 号，跳转到 Goals 页面的 TodoList 选项卡，可进行完整的任务管理。"
            }
        ]
      },
      {
        "id": "time-overview",
        "title": "Time Overview（时间概览）",
        "abstract": "展示当日时间分配，包含旭日图和按小时分布的柱状图。",
      },
      {
        "id": "activity-details",
        "title": "Activity Details（活动详情）",
        "abstract": "Top Apps:显示当日使用时长最多的应用列表，按时长降序排列;Top Titles:显示当日出现频率最高的窗口标题列表，便于了解具体工作内容。",
        "keywords": ["Top Apps", "Top Titles", "应用排行"],
      }
  ]
}
```

## TimeLine时间线
```json
{
  "id": "timeline",
  "title": "时间线",
  "abstract": "按时间顺序展示详细活动记录，支持缩略图模式和详细视图模式，支持添加自定义备注。",
  "keywords": ["时间线", "活动记录", "缩略图", "分类修改", "时间块", "备注"],
  "items": ["顶部工具栏", "缩略图模式", "详细视图模式", "自定义备注"],
  "content": [
      {
        "id": "timeline-toolbar",
        "title": "顶部工具栏",
        "abstract": "视图控制按钮。",
        "keywords": ["数据源", "缩放", "过滤"],
        "items": ["数据源筛选", "缩放控制", "过滤按钮", "缩略图开关"],
        "content": [
            {
                "title": "数据源筛选",
                "abstract": "可选择 All Sources（全部）、PC Only（仅电脑）、Mobile Only（仅移动端）筛选数据来源。目前只支持PC端。固定按钮为All Sources，不可修改"
            },
            {
                "title": "缩放控制",
                "abstract": "在时间线主轴上滚动鼠标滚轮可放大/缩小视图，点击重置按钮恢复默认比例。"
            },
            {
                "title": "过滤按钮",
                "abstract": "设置时长过滤。输入分钟数后只显示大于该时长的活动记录，隐藏短时间碎片。"
            },
            {
                "title": "缩略图开关",
                "abstract": "右上角的开关切换缩略图模式和详细视图模式。开启显示按小时的色块概览，关闭显示详细活动列表。"
            }
        ]
      },
      {
        "id": "thumbnail-mode",
        "title": "缩略图模式",
        "abstract": "按小时显示分类占比的色块预览，点击可查看统计信息。有时间粒度、分类筛选、Top N分类筛选显示等",
        "keywords": ["缩略图", "色块", "统计信息", "饼图"],
        "items": ["时间段下拉菜单", "分类下拉菜单", "Top N下拉菜单", "缩略图交互"],
        "content": [
            {
                "title": "时间段下拉菜单",
                "abstract": "选择缩略图的时间粒度（如1小时、30分钟），控制每个色块代表的时间长度。"
            },
            {
                "title": "分类下拉菜单",
                "abstract": "选择主分类或子分类层级。当选择主分类时，只显示主分类级别的色块；当选择子分类时，只显示子分类级别的色块。"
            },
            {
                "title": "Top N下拉菜单",
                "abstract": "选择显示前N个分类（如Top 3、Top 5），其余归为其他类别。"
            },
            {
                "title": "缩略图交互",
                "abstract": "点击缩略图中的某个色块，右侧面板显示该时段的统计信息：包含旭日图（分类占比）和柱状图（时间分布）。"
            }
        ]
      },
      {
        "id": "detail-view-mode",
        "title": "详细视图模式",
        "abstract": "显示每条活动记录的详细信息，支持修改分类。",
        "keywords": ["活动记录", "分类修改", "时间块"],
        "items": ["时间线滚轮缩放", "时间块交互", "分类修改", "撤销/无修改按钮"],
        "content": [
            {
                "title": "时间线滚轮缩放",
                "abstract": "在左侧时间线主轴上滚动鼠标滚轮可放大/缩小视图，便于查看密集的活动记录。"
            },
            {
                "title": "时间块交互",
                "abstract": "点击任意时间块，右侧面板显示该活动的详细信息：应用名、窗口标题、时间范围、时长、当前分类。"
            },
            {
                "title": "分类修改",
                "abstract": "在右侧面板中选择新的主分类和子分类，修改后自动保存。可用于修正AI分类错误。建议在category页面管理分类。"
            }
        ]
      },
      {
        "id": "custom-block",
        "title": "自定义备注",
        "abstract": "在时间线左侧标签区手动添加备注。",
        "keywords": ["备注", "自定义时间块", "离线活动", "手动记录"],
        "items": ["添加备注", "编辑备注", "备注显示"],
        "content": [
            {
                "title": "添加备注",
                "abstract": "将鼠标移动到时间线左侧的标签区域，会出现一个跟随鼠标的添加按钮（显示时间和+号）。点击该按钮打开编辑弹窗，填写内容后保存即可创建备注。"
            },
            {
                "title": "编辑备注",
                "abstract": "点击已创建的备注色块或左侧标签，打开编辑弹窗。弹窗分为左右两栏：左侧设置内容、时间范围和颜色；右侧可选择绑定待办事项、主分类和子分类。支持删除操作。"
            },
            {
                "title": "备注显示",
                "abstract": "备注以半透明色块显示在时间线背景层，左侧有颜色标识线。标签区域显示备注内容摘要，若绑定了待办事项还会显示待办内容。"
            }
        ]
      }
  ]
}
```

## Category分类管理
```json
{
  "id": "category",
  "title": "分类管理",
  "abstract": "管理分类层级结构、审核AI分类结果、配置应用映射缓存、修改分类结果。",
  "keywords": ["分类", "类别", "审核", "映射缓存", "Map Cache"],
  "items": ["Category Settings", "Data Review", "Map Cache"],
  "content": [
      {
        "id": "category-settings",
        "title": "Category Settings（分类设置）",
        "abstract": "管理分类层级结构，包括添加、编辑、删除分类，以及颜色配置。",
        "keywords": ["分类设置", "颜色", "添加分类", "删除分类"],
        "items": ["颜色选择", "修改名称", "禁用类别", "删除类别", "添加类别"],
        "content": [
            {
                "title": "颜色选择",
                "abstract": "主分类可自由选择颜色，子分类会自动生成同色系的衍生颜色，无需单独设置。"
            },
            {
                "title": "修改名称按钮",
                "abstract": "点击分类名称旁的编辑按钮，可修改分类名称。修改后自动保存。"
            },
            {
                "title": "禁用类别按钮",
                "abstract": "禁用分类后，AI 将不再使用该分类进行新数据分类，但历史数据保留，仍可正常显示。"
            },
            {
                "title": "删除类别按钮",
                "abstract": "删除分类后，该分类下所有关联的数据分类信息将被同步删除。请谨慎操作。"
            },
            {
                "title": "添加类别按钮",
                "abstract": "点击添加按钮可创建新的主分类或子分类。新分类创建后即可用于数据分类。"
            }
        ]
      },
      {
        "id": "data-review",
        "title": "Data Review（数据审核）",
        "abstract": "审核和修正AI的自动分类结果，支持单条修改和批量修改。",
        "keywords": ["数据审核", "分类修改", "批量修改"],
        "items": ["单条修改", "批量修改", "注意事项"],
        "content": [
            {
                "title": "单条修改",
                "abstract": "点击某条记录，通过下拉菜单选择正确的主分类和子分类，修改后自动保存。"
            },
            {
                "title": "批量修改",
                "abstract": "勾选多条记录后，可批量修改分类或批量删除。适用于同类型数据的快速处理。"
            },
            {
                "title": "注意事项",
                "abstract": "在此处修改只影响当前记录。若同一应用/标题后续仍可能分类错误，建议到 Map Cache 页面修改映射关系，确保后续数据自动使用正确分类。"
            }
        ]
      },
      {
        "id": "map-cache",
        "title": "Map Cache（映射缓存）",
        "abstract": "管理应用到分类的映射关系，修改后影响后续所有匹配数据的分类。",
        "keywords": ["映射缓存", "单用途", "多用途", "缓存"],
        "items": ["单用途与多用途", "映射修改", "同步到日志", "常见问题"],
        "content": [
            {
                "title": "单用途与多用途",
                "abstract": "单用途应用（如VS Code）只按应用名匹配；多用途应用（如Chrome浏览器）需按应用名+窗口标题匹配，因为同一应用可能用于不同用途。"
            },
            {
                "title": "映射修改",
                "abstract": "修改映射缓存中的分类后，后续所有匹配该应用/标题的新数据将自动使用修改后的分类，无需AI重新分类。"
            },
            {
                "title": "同步到日志",
                "abstract": "修改映射后，可选择'同步到日志'更新所有匹配的历史记录，使历史数据也使用新分类。"
            },
            {
                "title": "常见问题：找不到修改/删除按钮",
                "abstract": "如果看不到修改或删除按钮，请缩小浏览器界面或调整窗口大小，按钮可能因屏幕宽度不足而被隐藏。"
            }
        ]
      }
  ]
}
```

## Goals目标管理
```json
{
  "id": "goals",
  "title": "目标管理",
  "abstract": "Goals 页面是个人目标与任务规划的核心枢纽，包含待办事项、计划安排、目标设定、奖励追踪等功能模块。",
  "keywords": ["目标", "待办事项", "计划", "任务", "TodoList", "Goal", "Plan", "Reward"],
  "items": ["页面顶部", "To do list", "Plan", "Goal", "Reward", "Being"],
  "content": [
      {
        "id": "goals-header",
        "title": "页面顶部",
        "abstract": "点击标语旁的编辑图标（铅笔），可修改属于自己的个性化标语。输入完成后按回车或点击其他区域保存。",
        "keywords": ["标语"],
      },
      {
        "id": "todolist",
        "title": "To do list（待办事项）",
        "abstract": "管理每日待办任务，支持任务创建、完成标记、目标关联和跨日显示。",
        "keywords": ["待办", "任务", "TodoList", "跨日", "今日重点", "link to goal"],
        "items": ["创建任务", "Link to Goal", "跨日按钮", "今日重点"],
        "content": [
            {
                "title": "创建任务",
                "abstract": "在任务输入区域输入任务描述，按回车或点击添加按钮创建新任务。"
            },
            {
                "title": "Link to Goal（关联目标）",
                "abstract": "创建任务时可选择关联到某个目标。关联后，该任务的完成情况会在 Reward 视图中累计显示，便于追踪目标进度。"
            },
            {
                "title": "跨日按钮",
                "abstract": "开启跨日功能后，该任务在完成之前会在每天的待办列表中持续显示；完成后只会显示在创建当天的记录中。适用于长期任务。"
            },
            {
                "title": "今日重点",
                "abstract": "今日重点内容应在周计划（Plan → Week → Focus Intent）中设置和修改，设置后会自动同步到 TodoList 的今日重点区域显示。"
            },
        ]
      },
      {
        "id": "plan",
        "title": "Plan（计划）",
        "abstract": "规划周期性工作安排，包含月计划和周计划两个层级。",
        "keywords": ["计划", "月计划", "周计划", "Focus Intent", "Execution"],
        "items": ["月计划界面", "周计划界面"],
        "content": [
            {
                "title": "月计划界面",
                "abstract": "规划每周的重点工作。在此设置的规划内容会显示在对应周的周计划界面中，便于分解和执行。"
            },
            {
                "title": "周计划界面",
                "abstract": "详细设置每日计划，包含两个核心功能区。",
                "items": ["Focus Intent（每日专注意图）", "Execution（todolist设置）"],
                "content": [
                    {
                        "title": "Focus Intent（每日专注意图）",
                        "abstract": "在每天的 Focus Intent 区域编写当日专注内容。编写的内容会自动同步显示到 TodoList 的今日重点区域。"
                    },
                    {
                        "title": "Execution（todolist设置）",
                        "abstract": "可在此快速创建和删除每天的具体待办任务，与 TodoList 数据互通。"
                    }
                ]
            }
        ]
      },
      {
        "id": "goal",
        "title": "Goal（目标）",
        "abstract": "创建和管理个人目标，支持目标分类绑定、进度追踪和详细描述。目标绑定分类后可影响AI自动分类的判断。",
        "keywords": ["目标", "目标管理", "分类绑定", "AI分类优先", "Mission"],
        "items": ["目标列表", "目标详情", "分类绑定功能"],
        "details": {
            "核心功能": "目标分类绑定是连接目标管理与AI分类系统的关键桥梁",
            "注意事项": "1. 合理使用分类绑定可大幅提升AI分类准确度 2. 合理的Goal名称对于分类很关键"
        },
        "content": [
            {
                "title": "目标列表",
                "abstract": "展示所有目标卡片，显示目标状态、分类、创建日期、预计时长等信息。",
                "items": ["新建目标", "目标卡片", "删除目标"],
                "content": [
                    {
                        "title": "新建目标（New Mission）",
                        "abstract": "点击右上角 New Mission 按钮创建新目标。新目标会立即进入详情编辑页面。"
                    },
                    {
                        "title": "目标卡片",
                        "abstract": "每个目标以卡片形式展示，显示状态徽章（进行中/已完成/已归档）、分类标签、名称摘要、创建时间和预计时长。点击卡片右下角箭头进入详情编辑。"
                    },
                    {
                        "title": "删除目标",
                        "abstract": "将鼠标悬停在目标卡片上，右上角会显示删除按钮。点击后确认即可删除。"
                    }
                ]
            },
            {
                "title": "目标详情",
                "abstract": "编辑目标的完整信息，支持自动保存和 Markdown 格式描述。",
                "items": ["标题与摘要", "元数据设置", "内容编辑", "保存方式"],
                "content": [
                    {
                        "title": "标题与摘要",
                        "abstract": "在页面顶部直接编辑目标标题和简短摘要，摘要用于在目标卡片上快速预览。"
                    },
                    {
                        "title": "元数据设置",
                        "abstract": "点击'信息'展开元数据区域，可设置：目标日期（预计完成时间）、预计时长（小时）、卡片颜色、完成状态、关联分类。"
                    },
                    {
                        "title": "内容编辑",
                        "abstract": "支持 Markdown 格式。点击右上角'编辑'/'预览'按钮切换模式，或双击预览区域进入编辑。可详细描述目标规划、里程碑和动机。"
                    },
                    {
                        "title": "保存方式",
                        "abstract": "支持三种保存方式：1) 按 Ctrl+S 静默保存（显示保存成功提示）；2) 点击右上角'保存'按钮；3) 点击'返回'按钮时自动保存。"
                    }
                ]
            },
            {
                "id": "goal-category-binding",
                "title": "分类绑定功能（重要）",
                "abstract": "将目标与分类建立关联，影响AI自动分类的判断逻辑。这是目标管理与时间追踪数据整合的核心机制。",
                "keywords": ["分类绑定", "AI分类优先", "目标关联分类", "智能分类"],
                "details": {
                    "位置": "目标卡片上的分类按钮，或目标详情的'信息 → 分类'",
                    "功能": "建立目标与分类的关联，目前只实现单向绑定，goal to category",
                    "注意事项": "每个目标只能绑定一个分类（主分类+可选子分类）"
                },
                "items": ["绑定方法", "AI分类优先机制", "最佳实践"],
                "content": [
                    {
                        "title": "绑定方法",
                        "abstract": "在目标详情页面点击'信息'展开'信息'区域点击'分类'，打开分类选择弹窗。先选择主分类，再可选择子分类，点击 Apply 应用。"
                    },
                    {
                        "title": "AI分类优先机制",
                        "abstract": "当目标绑定了某个分类后，AI 在分类新数据时会优先判断该数据是否与此目标相关。如果数据内容（应用名、窗口标题等）符合该目标的上下文，AI 会直接使用目标绑定的分类，跳过常规分类判断流程。这确保与特定目标相关的活动能够准确归类。"
                    },
                    {
                        "title": "最佳实践",
                        "abstract": "示例：创建'学习 Python'目标并绑定'学习 → 编程'分类后，当你使用 Python 相关工具（如 PyCharm、Python 文档网页）时，AI 会优先将这些活动归类到'学习 → 编程'，而不是可能的'工作 → 开发'。建议为每个主要目标设置明确的分类绑定。"
                    }
                ]
            }
        ]
      },
      {
        "id": "reward",
        "title": "Reward（奖励追踪）",
        "abstract": "展示目标完成进度和相关任务统计，可查看关联任务的累计完成情况。",
        "keywords": ["奖励", "进度", "统计", "累计"]
      },
      {
        "id": "being",
        "title": "Being（存在意义）",
        "abstract": "探索个人价值观和人生意义的反思空间（功能开发中）。",
        "keywords": ["价值观", "意义", "反思", "Being"]
      }
  ]
}
```

## Usage使用量统计
```json
{
  "id": "usage",
  "title": "使用量统计",
  "abstract": "展示 AI 服务的 Token 消耗量和成本统计。所有成本为基于输入输出 Token 数量的估算值。",
  "keywords": ["Token", "使用量", "成本", "API调用", "统计"],
  "items": ["Token Usage", "Data Processing", "Other Usage", "7-Day Usage Trend"],
  "details": {
      "注意事项": "Cost（成本）是依据输入 Token 和输出 Token 数量乘以设定单价的估算值，非实际账单金额"
  },
  "content": [
      {
        "id": "token-usage",
        "title": "Token Usage（Token 使用量）",
        "abstract": "显示今日和累计的 Token 使用量，可设置输入输出 Token 单价（每1k），自动计算总成本。环形图展示输入输出 Token 占比。"
      },
      {
        "id": "data-processing",
        "title": "Data Processing（数据处理）",
        "abstract": "显示 AI 分类处理的记录数统计，包括：Records Processed（处理记录数）、Today Tokens/Cost（今日消耗）、Avg Tokens/Cost（每条记录平均消耗）。"
      },
      {
        "id": "other-usage",
        "title": "Other Usage（其他用量）",
        "abstract": "统计非分类 API 调用（如 AI 对话）产生的 Token 消耗和成本。与分类用量分开统计，便于区分不同功能的资源消耗。"
      },
      {
        "id": "usage-trend",
        "title": "7-Day Usage Trend（7天趋势图）",
        "abstract": "柱状图展示过去一周的 Token 消耗量和成本变化趋势。可切换查看 Tokens 数量或 Cost 成本视图。"
      }
  ]
}
```

## 推荐使用方法
```json
{
  "id": "recommended-workflow",
  "title": "推荐使用方法",
  "abstract": "本系统的最佳实践指南，帮助用户快速上手并充分发挥系统价值。",
  "keywords": ["使用方法", "最佳实践", "工作流", "推荐"],
  "items": ["分类设置建议", "Goals页面使用方法"],
  "content": [
      {
        "id": "category-setup-guide",
        "title": "分类设置建议",
        "abstract": "合理的分类结构是 AI 精准分类的基础。推荐使用清晰、互斥的主分类。",
        "keywords": ["分类", "主分类", "设置建议"],
        "items": ["推荐分类方案", "自定义分类要求"],
        "content": [
            {
                "title": "推荐分类方案",
                "abstract": "方案一：工作、学习、娱乐、其他（四分法）；方案二：工作/学习、娱乐、其他（三分法，适合工作学习边界模糊的用户）。这两种方案经过验证，AI 分类准确度较高。"
            },
            {
                "title": "自定义分类要求",
                "abstract": "若采用其他分类名称，需满足以下要求：1) 分类之间界限明确，避免语义重叠（如同时设置'学习'和'自我提升'会导致 AI 难以判断）；2) 分类名称清晰无歧义，使用常见词汇（如用'娱乐'而非'休闲放松'）；3) 各分类名称不能重复或过于相似。"
            }
        ]
      },
      {
        "id": "goals-workflow",
        "title": "Goals页面使用方法",
        "abstract": "根据目标时间跨度选择不同的规划方式，从简单的待办事项到完整的目标管理体系。",
        "keywords": ["目标", "规划", "工作流", "短期", "中长期"],
        "items": ["短期打算", "中长期打算", "长期打算"],
        "content": [
            {
                "title": "短期打算（1-3天）",
                "abstract": "对于近期需要完成的小任务，直接在 To do list 中创建任务即可。如需追踪，可开启跨日功能确保任务不会遗漏。"
            },
            {
                "title": "中长期打算（1周-数月）",
                "abstract": "建议按以下流程设置：第一步，在 Goal 界面创建目标，明确目标名称和描述，绑定相关分类；第二步，在 Reward 界面设置完成该目标后的奖励，增强完成动力；第三步，在 Plan 界面进行初步规划，分解为周/月阶段目标；第四步，在每日 TodoList 中制定具体执行任务，逐步推进目标完成。"
            },
            {
                "title": "长期打算（数年）",
                "abstract": "功能规划中，敬请期待。"
            }
        ]
      }
  ]
}
```

## 常见问题
```json
{
  "id": "faq",
  "title": "常见问题",
  "abstract": "使用过程中常见问题的解答与解决方案。",
  "keywords": ["FAQ", "常见问题", "疑问", "解决方案"],
  "items": ["错误删除数据", "找不到编辑按钮", "数据来源", "AI分类不准确"],
  "content": [
      {
        "id": "faq-data-recovery",
        "title": "Q1: 错误删除数据怎么办？",
        "abstract": "可通过重新同步恢复数据。点击首页 Activity Summary 区域的 Sync Data 按钮，选择需要恢复的日期范围，重新从 ActivityWatch 同步数据。注意：该操作会覆盖选定日期范围内的现有数据，但只要 Map Cache（映射缓存）未更改，重新同步后的分类结果与原数据保持一致。",
        "keywords": ["删除", "恢复", "同步", "数据丢失"]
      },
      {
        "id": "faq-button-hidden",
        "title": "Q2: 找不到 Map Cache 的编辑/删除按钮怎么办？",
        "abstract": "这通常是浏览器窗口宽度不足导致按钮被隐藏。解决方法：1) 缩小浏览器页面缩放比例（Ctrl + 减号键）；2) 或最大化浏览器窗口；3) 或调整屏幕分辨率。按钮位于每条映射记录的右侧。",
        "keywords": ["按钮", "隐藏", "缩放", "Map Cache"]
      },
      {
        "id": "faq-data-source",
        "title": "Q3: 数据从哪里来？",
        "abstract": "电脑使用数据来自 ActivityWatch（https://activitywatch.net/），一款开源的自动时间追踪软件。使用前请确保：1) 已安装 ActivityWatch，并在本系统设置中配置了正确的 ActivityWatch 数据库路径；2) 已启动 aw-server（服务端）和 aw-watcher-windows（Windows 活动监控器）；3) ActivityWatch 在后台持续运行以采集数据。",
        "keywords": ["ActivityWatch", "数据来源", "安装", "配置"]
      },
      {
        "id": "faq-classification-error",
        "title": "Q4: AI 分类不准确怎么办？",
        "abstract": "可通过以下两种方式修正。方式一（单条修正）：进入分类管理 → Data Review 页面，找到分类错误的记录，选择正确的分类，系统自动保存。方式二（批量修正）：进入分类管理 → Map Cache 页面，找到对应的应用映射，修改分类后点击'同步到日志'，将更新所有匹配的历史记录。建议优先使用方式二，可一次性修正同一应用的所有记录并确保后续数据分类正确。",
        "keywords": ["分类错误", "修正", "Data Review", "Map Cache"]
      }
  ]
}
```

## AI数据分类流程
```json
{
  "id": "classification-flow",
  "title": "AI数据分类流程",
  "abstract": "系统对 ActivityWatch 采集的活动数据进行智能分类的完整流程。按优先级依次执行：缓存匹配 → Goal 匹配 → AI 分类。",
  "keywords": ["分类流程", "AI分类", "Goal匹配", "智能分类", "Map Cache"],
  "items": ["缓存匹配", "Goal匹配", "AI分类流程"],
  "content": [
      {
        "id": "cache-matching",
        "title": "第0步：缓存匹配",
        "abstract": "系统首先检查 Map Cache 中是否存在该应用的映射记录。如果存在，直接使用缓存中的分类结果，无需调用 AI。这类分类速度最快、成本为零、结果稳定。",
        "keywords": ["缓存匹配", "Map Cache", "快速分类"]
      },
      {
        "id": "goal-matching",
        "title": "第1步：Goal 匹配",
        "abstract": "若缓存未命中，系统检查活动是否与已设置的 Goal 相关。如果活动内容（应用名、窗口标题）与某个 Goal 的上下文匹配，则直接使用该 Goal 绑定的分类，跳过后续 AI 分类流程。这确保与特定目标相关的活动能够精准归类。",
        "keywords": ["Goal", "目标匹配", "优先分类"]
      },
      {
        "id": "ai-classification",
        "title": "第2步：AI 分类流程",
        "abstract": "若缓存和 Goal 均未命中，系统调用 AI 进行智能分类。",
        "keywords": ["AI分类", "智能分析", "LLM"],
        "items": ["单用途应用分类", "多用途应用分类"],
        "content": [
            {
                "title": "单用途应用分类",
                "abstract": "系统获取应用的描述信息，结合 app 名称进行分类判断。例如：VS Code 始终归类为开发工具相关类别。分类结果存入 Map Cache。"
            },
            {
                "title": "多用途应用分类",
                "abstract": "对于浏览器等多用途应用，分类逻辑更复杂：1) 短时间活动：结合 app 描述、app 名称和 title 进行分类；2) 长时间活动：先分析 title 语义内容，再结合 app 描述、app 名称、title 及 title 分析结果进行综合分类判断。分类完成后结果存入 Map Cache 供后续快速匹配。"
            }
        ]
      }
  ]
}
```
