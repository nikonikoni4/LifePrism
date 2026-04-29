## 2026-04-30-screenshot-timestamp-format-mismatch

- updated_at: 2026-04-30
- path: `docs/history-bugs/2026-04-30-screenshot-timestamp-format-mismatch.md`
- 触发规则：在排查截图分析查询失败、时间戳格式不匹配、SQLite 时间范围查询返回空结果时阅读
- 内容摘要：记录了修改 screen_captures 表时间戳格式后，查询时使用 ISO 格式导致无法匹配数据库格式的 bug，以及截图数量限制和动态 chunk 大小的优化方案。

## 2026-04-25-electron-native-dialog-focus-loss

- updated_at: 2026-04-25
- path: `docs/history-bugs/2026-04-25-electron-native-dialog-focus-loss.md`
- 触发规则：在排查 Electron 应用中使用 window.confirm/alert/prompt 后输入框无法输入、焦点丢失，或 window.electronAPI undefined 错误时阅读
- 内容摘要：记录了 Electron 原生对话框导致输入框焦点丢失的已知 bug，以及 window.electronAPI 调用缺少可选链和降级方案导致的崩溃问题。包含完整的解决方案和 18 个文件的修复记录。

## 2026-04-22-multiprocessing-infinite-loop

- updated_at: 2026-04-22
- path: `docs/history-bugs/2026-04-22-multiprocessing-infinite-loop.md`
- 触发规则：在排查 Windows 打包环境下后端无限启动、端口被大量占用、multiprocessing 子进程异常行为时阅读
- 内容摘要：记录了 Windows 下 multiprocessing.Process 在 PyInstaller 打包后因缺少 freeze_support() 导致子进程重复执行主程序逻辑，引发后端无限启动循环的严重 bug。

## 2026-04-19-chain-node-menu-occlusion

- updated_at: 2026-04-19
- path: `docs/history-bugs/2026-04-19-chain-node-menu-occlusion.md`
- 触发规则：在排查包含弹窗、拖拽操作或多层嵌套列表组件导致的 z-index 层叠/遮挡等渲染错误时阅读
- 内容摘要：整理了 dnd-kit 修改 transform 引起的”层叠上下文封闭”从而致菜单被底部节点遮挡的原理，以及应用 React Portals 和 Floating UI 的标准处理方案。

