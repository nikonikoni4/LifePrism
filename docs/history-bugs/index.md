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

