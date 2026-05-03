# CLAUDE.md

## 按需加载文档

### 文档介绍

文档是作为项目的核心资产，通过阅读这些文件能够快速了解项目情况，同时必须遵守文档处理相关规则，这对于项目维护与构建极其重要。


| 文档类型 | 路径 | 文档说明 |
|---------|------|------|
| **架构地图** | `docs/ARCHITECTURE.md` | 顶层导航,说明主要模块、层级和依赖关系 |
| **启动文档** | `docs/RUN.md` | 如何启动系统,包括启动指令、端口、运行前提 |
| **编码规则** | `docs/coding-rules/` | 编写代码时必须遵守的规范、约束、触发场景 |
| **文档规则** | `docs/docs-rules/` | 编写 docs 时必须遵守的规范、约束、触发场景 |
| **权威参考** | `docs/authority/` | 系统中特定且关键的实现知识,用于承接不适合放在 `rules` 里的重要实现事实 |
| **产品规格** | `docs/specs/` | 对于正式 `spec`,承载业务意图、业务规则、领域概念,以及规范性技术契约 |
| **架构决策** | `docs/design-decisions/` | 记录对于长期具有重要的作用的修改决定 |
| **自动生成** | `docs/generated/` | 代码镜像,不手工维护正文,用于快速了解当前实现事实及 CI 结果 |
| **执行计划** | `docs/plans/` | 执行过程中的任务分解和执行记录,也是历史执行资产 |
| **重要bug历史记录**  | `docs/history-bugs`      | 存放可复用的bug经验   
| **临时内容** | `docs/temp/` | 非正式文档，暂时无法归类的内容、草稿、临时记录，默认不读取，只写入 |
| **superpower文件夹** | `docs/superpowers/` | superpower 插件下skill专用的文件夹，包括`docs/superpower/specs` 和 `docs/superpower/plans` |
| **文档地图** | `docs/<文件夹>/index.md` | 除temp文件夹以外，其余文件都有index.md导航文件，会存放该文件夹下所有文档的索引 |

<docs-read-rules>

1. **按需加载**：在你决定阅读某个具体文件夹内容之前**必须阅读导航文件index.md**按需加载具体文件
2. **任务涉及代码修改时**：必须阅读`docs/coding-rules/index.md`，按需加载当前任务所涉及到的规则
3. **需要编写文档进入docs时**：必须阅读`docs/docs-rules/index.md`和`docs/docs-rules/docs-write-rules.md`
4. **编写功能前**：需要阅读`docs/specs/index.md`，查看当前是否已经存在spec，按需加载具体的spec来了解该功能情况
5. **如果你是minimax模型**：必须阅读`docs/coding-rules/other-model-rules`
6. **修复bug时**: 可以阅读`docs\history-bugs\index.md`来获取历史bug解决方法

</<docs-read-rules>>

## 核心规则

1. **先方案后编码**：编写任何代码之前，先描述方案等待批准。需求不明确时先提问。

2. **拆分大任务**：修改超过 3 个文件时，先分解为更小的任务。

3. **列出风险**：编码后列出可能的问题。

4. **困难bug排查**: 对于困难的bug，涉及到多个区域，或难以排查的bug，应该优先编写debug进行测试进行快速排查

5. **Bug 先测试**：修 bug 先写复现测试，再修复直到通过。

6. **记录教训**：每次被纠正后，在 `docs/temp/temp_lecture_record/temp_lecture_record.md` 记录经验教训



