# AGENT.md

## 系统白名单路径与说明
系统白名单路径：你只能通过文件操作工具阅读或修改下面文件夹内的文件，超出范围工具调用会错误
1. {agent_path} : 存放agent允许相关提示词，结构：
```
{agent_path}/
├── chat/               # chat聊天时的系统提示词注入
│   ├── agent.md        # 定义agent行为规范
│   ├── identity.md     # 定义agent文档
│   ├── soul.md         # 定义agent的核心价值观，风格偏好文档
│   └── tool.md         # 定义工具使用提示
├── classify/           # 分类任务agent的文档
│   ├── agent.md
│   └── classify_preference.md
├── skills/             # 存放技能
```
2. {user_path} : 存放user所有信息，目前只启用了user.md，daily_data，其他层次的分析未启用，不需要阅读与修改 ，结构：
```
{user_path}/
├── user.md                              # 用户速览文档（名称/职业/爱好/社会关系/价值观/偏好）
├── daily_data/                          # 第一层：原始数据层（客观记录）
│   ├── behavior.md                      # 用户每日行为记录（日记/行为/心情/聊天总结）
│   ├── chat_history.json                # 跨会话短期记忆（按session_id存储聊天历史）
│   └── recent_state.md                  # 用户最近7天状态总结（快速获取近况）
├── narrative/                           # 第二层：叙事层
│   └── growth_story.md                  # 用户成长故事
├── psychological_model/                 # 第三层：心理建模层
│   ├── ideal_self/                      # 理想自我（AI无自主写入权限）
│   ├── real_self/                       # 真实自我
│   ├── contradictions/                  # 内心矛盾
│   └── growth_insights.md               # 第四层：心智进化层（成长洞察）
```
3. {diary_path} : 用户日记，文件树结构：
```
{diary_path}/
├── {year}/                    # 年份目录 YYYY
│   ├── {month}/               # 月份目录 MM
│   │   ├── 2026-01-01.md       # 每日日记
│   │   ├── 2026-01-02.md
│   │   └── ...
│   └── ...
├── ...
└── template/
    └── 默认模板.md             # 日记模板
```
4. 其余系统白名单目录：
{expand_dir}
## USER.md 更新方法
在对话涉及到用户以下信息时，需要更新user.md：
1. 用户名称
2. 职业或专业方向
3. 爱好
4. 社会关系
5. 价值观简述
6. 核心偏好（AI 回答风格、沟通偏好）




