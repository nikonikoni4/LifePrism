# customData 用户数据迁移方案（v2）

## 背景

### 问题 1：用户数据丢失

当前 customData 放在安装目录 `resources/customData` 下，NSIS 重装时会清空整个安装目录，导致用户数据（数据库、计划书 MD、配置等）丢失。

### 问题 2：NSIS `RMDir /r $INSTDIR` 的安全隐患

electron-builder 的 NSIS 卸载脚本中，`uninstaller.nsh` 无条件执行：

```nsh
RMDir /r $INSTDIR
```

**没有任何保护机制**：
- 不检查 `$INSTDIR` 是否为磁盘根目录（如 `D:\`）
- 不检查是否为系统目录（如 `C:\Program Files`）
- 不验证路径深度或特征文件

如果用户将应用安装到 `D:\`，卸载时会尝试**递归删除整个 D 盘**，这不仅是本项目数据的问题，是灾难性的数据安全问题。

参考：[electron-builder Issue #3201](https://github.com/electron-userland/electron-builder/issues/3201)

## 新方案：强制子目录 + 数据分离

### 核心思路

无论用户选择什么安装路径，都**强制追加 `LifePrism` 子目录**，并在其下分离 `app`（安装文件）和 `customData`（用户数据）。

### 目录结构

```
用户选择: D:\
实际结构:
  D:\LifePrism\                ← 强制追加的子目录（根目录）
  ├── app\                     ← $INSTDIR，实际安装路径
  │   ├── LifePrism.exe
  │   ├── resources\
  │   │   ├── backend\         ← Python 后端
  │   │   └── customData\      ← 模板文件（只读，用于首次初始化）
  │   └── ...
  └── customData\              ← 用户数据（与 app 同级，不在 $INSTDIR 内）
      ├── config\              ← 用户配置
      ├── dataset\             ← 数据库文件
      ├── plan\                ← 计划书 MD 文件
      ├── workflow\            ← 工作流配置
      └── external_files\      ← 外部文件
```

### 默认路径

```
默认安装:
  C:\Program Files\LifePrism\app\           ← 安装文件
  C:\Program Files\LifePrism\customData\    ← 用户数据
```

### 安全保障

| 场景 | 行为 | 用户数据 |
|------|------|---------|
| 正常卸载 | `RMDir /r` 删除 `app\` 子目录 | customData 不受影响 |
| 重装/升级 | 先卸载 `app\`，再安装新版本 | customData 不受影响 |
| 用户装到 D:\ | 实际 $INSTDIR = `D:\LifePrism\app\` | D 盘其他文件安全 |
| 用户装到 C:\Program Files | 实际 $INSTDIR = `C:\Program Files\LifePrism\app\` | 其他程序安全 |

### 为什么这个方案能解决问题

1. **强制子目录**：`RMDir /r` 的范围被限定在 `LifePrism\app\` 内，不会波及上层
2. **数据分离**：customData 与 app 同级但不在 $INSTDIR 内，卸载不会触及
3. **无需修改 NSIS 卸载逻辑**：利用现有行为，只改安装路径结构

## 实现方案

### NSIS 自定义脚本（installer.nsh）

electron-builder 支持通过 `"nsis": { "include": "installer.nsh" }` 引入自定义脚本。

#### 需要实现的功能

1. **强制追加子目录**：用户选择 `D:\` → 实际 `$INSTDIR = D:\LifePrism\app`
2. **创建 customData 目录**：安装时在 `$INSTDIR\..\customData` 创建用户数据目录
3. **路径写入注册表**：将 customData 路径写入 `HKLM\Software\LifePrism\DataPath`
4. **首次安装初始化**：从 `$INSTDIR\resources\customData`（模板）拷贝初始文件到用户 customData

#### NSIS 脚本伪代码

```nsh
!macro customHeader
  # 定义变量
  Var CustomDataPath
!macroend

!macro customInit
  # 强制追加 LifePrism\app 子目录
  # 如果用户选择 D:\，$INSTDIR 变为 D:\LifePrism\app
  StrCpy $INSTDIR "$INSTDIR\LifePrism\app"
!macroend

!macro customInstall
  # 计算 customData 路径（$INSTDIR 的父目录的 customData 子目录）
  # D:\LifePrism\app → D:\LifePrism\customData
  Push $INSTDIR
  Call GetParentDir
  Pop $0
  StrCpy $CustomDataPath "$0\customData"

  # 创建 customData 目录
  CreateDirectory "$CustomDataPath"
  CreateDirectory "$CustomDataPath\config"
  CreateDirectory "$CustomDataPath\dataset"
  CreateDirectory "$CustomDataPath\plan"
  CreateDirectory "$CustomDataPath\workflow"
  CreateDirectory "$CustomDataPath\external_files"

  # 写入注册表
  WriteRegStr HKLM "Software\LifePrism" "DataPath" "$CustomDataPath"
  WriteRegStr HKLM "Software\LifePrism" "InstallPath" "$INSTDIR"

  # 首次安装：拷贝模板文件到 customData（如果目标不存在）
  IfFileExists "$CustomDataPath\config\config.json" +2
    CopyFiles "$INSTDIR\resources\customData\config\*.*" "$CustomDataPath\config\"

  IfFileExists "$CustomDataPath\workflow\daily_summary_plan.json" +2
    CopyFiles "$INSTDIR\resources\customData\workflow\*.*" "$CustomDataPath\workflow\"
!macroend

!macro customUnInstall
  # 卸载时不删除 customData，默认保留用户数据
  # $INSTDIR (app\) 会被 electron-builder 默认的 RMDir /r 删除
  # customData 在 $INSTDIR 外部，不受影响

  # 清理注册表
  DeleteRegKey HKLM "Software\LifePrism"

  # 清理空的父目录（LifePrism\）
  # RMDir 不带 /r 只删除空目录，如果 customData 还在则不会删除
  Push $INSTDIR
  Call un.GetParentDir
  Pop $0
  RMDir "$0"
!macroend
```

### Electron 读取路径（main.cjs）

```javascript
function getCustomDataPath() {
    if (app.isPackaged) {
        // 1. 优先从注册表读取
        try {
            const regKey = require('child_process')
                .execSync('reg query "HKLM\\Software\\LifePrism" /v DataPath', { encoding: 'utf-8' });
            const match = regKey.match(/DataPath\s+REG_SZ\s+(.+)/);
            if (match) return match[1].trim();
        } catch (e) {}

        // 2. 后备：基于安装路径推算
        // app.exe 在 LifePrism\app\ 下，customData 在 LifePrism\customData\
        const appDir = path.dirname(process.execPath);        // LifePrism\app
        const rootDir = path.dirname(appDir);                  // LifePrism
        return path.join(rootDir, 'customData');
    } else {
        return path.join(__dirname, '..', 'customData');
    }
}
```

### Python 后端路径解析

Python 后端通过环境变量 `CUSTOM_DATA_PATH` 获取路径（由 Electron 传入），后备逻辑：

```python
def _resolve_custom_data_path(self) -> Path:
    # 1. 环境变量（Electron 传入）
    custom_data_env = os.environ.get('CUSTOM_DATA_PATH')
    if custom_data_env:
        return Path(custom_data_env)

    # 2. 打包环境后备：基于 exe 位置推算
    if getattr(sys, 'frozen', False):
        # sys.executable = .../LifePrism/app/resources/backend/lifeprism-backend.exe
        backend_dir = Path(sys.executable).parent   # .../app/resources/backend
        app_dir = backend_dir.parent.parent          # .../app
        root_dir = app_dir.parent                    # .../LifePrism
        return root_dir / 'customData'

    # 3. 开发环境
    project_root = Path(__file__).parent.parent.parent
    return project_root / 'frontend' / 'customData'
```

### 路径持久化：注册表

| 注册表键 | 值 | 用途 |
|---------|------|------|
| `HKLM\Software\LifePrism\DataPath` | `D:\LifePrism\customData` | customData 路径 |
| `HKLM\Software\LifePrism\InstallPath` | `D:\LifePrism\app` | 安装路径 |

### 初始化流程

```
NSIS 安装界面
    ↓
用户选择安装路径（默认 C:\Program Files）
    ↓
NSIS 强制追加 \LifePrism\app → $INSTDIR
    ↓
安装文件到 $INSTDIR
    ↓
创建 $INSTDIR\..\customData 目录结构
    ↓
首次安装：拷贝模板文件到 customData
    ↓
写入注册表（DataPath, InstallPath）
    ↓
Electron 启动 → 从注册表读取 DataPath
    ↓
设置环境变量 CUSTOM_DATA_PATH → 启动 Python 后端
    ↓
DataInitializer 初始化数据库 + 生成示例 MD 文件
```

## 影响范围

| 文件 | 操作 | 说明 |
|------|------|------|
| `frontend/installer.nsh` | **新建** | 自定义 NSIS 脚本：强制子目录、创建 customData、写注册表 |
| `frontend/package.json` | 修改 | NSIS 配置添加 `"include": "installer.nsh"` |
| `frontend/electron/main.cjs` | 修改 | `getCustomDataPath()` 增加注册表读取 + 路径推算 |
| `lifeprism/utils/common_utils.py` | 修改 | `get_custom_data_path()` 后备路径改为基于 exe 推算 |
| `lifeprism/config/settings_manager.py` | 修改 | `_resolve_custom_data_path()` 同步修改 |
| `lifeprism/storage/data_initializer.py` | 修改 | 修复 plan 文件夹和 MD 生成 |

## 当前配置参考

### NSIS 配置

```json
// frontend/package.json → build.nsis
{
  "oneClick": false,
  "allowToChangeInstallationDirectory": true,
  "perMachine": true,
  "createDesktopShortcut": true,
  "createStartMenuShortcut": true,
  "shortcutName": "LifePrism"
}
```

### extraResources 配置

```json
// frontend/package.json → build.extraResources
[
  {
    "from": "../pyinstaller-dist/lifeprism-backend",
    "to": "backend",
    "filter": ["**/*", "!**/settings.yaml"]
  },
  {
    "from": "customData",
    "to": "customData",
    "filter": ["**/*", "!plan/*.md", "plan/示例-planDoc.md"]
  }
]
```

## 安装路径安全检查

### 必须检查：目标路径是否为空

在用户确认安装路径后、实际安装前，NSIS 脚本必须检查 `$INSTDIR`（即 `用户选择路径\LifePrism\app`）所在的父目录是否为空或不存在。

**检查逻辑**：

```
用户选择路径: D:\
实际根目录: D:\LifePrism\

检查 D:\LifePrism\ 是否存在：
  - 不存在 → 安全，继续安装
  - 存在且是本应用的旧安装 → 安全，覆盖安装
  - 存在且包含非本应用的文件 → 阻止安装，提示用户换路径
```

**判断"是否为本应用"的方法**：检查 `LifePrism\app\LifePrism.exe` 是否存在（特征文件验证）。

**NSIS 伪代码**：

```nsh
!macro customInit
  # 强制追加子目录
  StrCpy $INSTDIR "$INSTDIR\LifePrism\app"

  # 检查父目录 LifePrism\ 是否安全
  Push $INSTDIR
  Call GetParentDir
  Pop $0  # $0 = ...\LifePrism

  IfFileExists "$0\*.*" 0 pathSafe
    # 目录存在，检查是否为本应用
    IfFileExists "$0\app\LifePrism.exe" pathSafe
      # 目录存在但不是本应用 → 阻止
      MessageBox MB_OK|MB_ICONEXCLAMATION \
        "安装目录 $0 已存在且包含其他文件，请选择一个空目录或其他位置。"
      Abort
  pathSafe:
!macroend
```

### 防御场景

| 用户选择 | 实际检查路径 | 结果 |
|---------|-------------|------|
| `D:\` | `D:\LifePrism\` 不存在 | 通过，创建并安装 |
| `D:\` | `D:\LifePrism\` 存在，有 `app\LifePrism.exe` | 通过，覆盖安装 |
| `D:\` | `D:\LifePrism\` 存在，有其他文件 | 阻止，提示换路径 |
| `C:\Program Files` | `C:\Program Files\LifePrism\` 不存在 | 通过 |
| `C:\` | `C:\LifePrism\` 不存在 | 通过 |
