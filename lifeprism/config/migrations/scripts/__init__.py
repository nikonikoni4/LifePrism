"""
Config 迁移脚本注册表

显式注册所有迁移脚本（不做文件系统扫描，兼容 PyInstaller 打包）。
新增迁移时在此处 import 并追加到对应列表。
"""
from . import s001_baseline, p001_baseline

# settings.yaml 迁移列表（按 VERSION 升序）
SETTINGS_MIGRATIONS = [
    s001_baseline,
]

# providers.yaml 迁移列表（按 VERSION 升序）
PROVIDERS_MIGRATIONS = [
    p001_baseline,
]
