# -*- mode: python ; coding: utf-8 -*-
"""
LifePrism PyInstaller 配置文件

使用方法:
    pyinstaller lifeprism.spec --distpath pyinstaller-dist

输出目录:
    pyinstaller-dist/lifeprism-backend/
"""

import sys
from pathlib import Path

block_cipher = None

# 项目根目录
project_root = Path('.').resolve()

a = Analysis(
    ['lifeprism/server/main.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        # 注意：不打包 settings.yaml，打包环境使用 customData/config/config.yaml
        # 只打包必要的 Python 模块文件
        ('lifeprism/config/__init__.py', 'lifeprism/config'),
        ('lifeprism/config/crawler.py', 'lifeprism/config'),
        ('lifeprism/config/database.py', 'lifeprism/config'),
        ('lifeprism/config/settings.py', 'lifeprism/config'),
        ('lifeprism/config/settings_manager.py', 'lifeprism/config'),
    ],
    hiddenimports=[
        # FastAPI/Uvicorn 相关
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        
        # Starlette 相关
        'starlette.responses',
        'starlette.routing',
        'starlette.middleware',
        'starlette.middleware.cors',
        
        # Pydantic 相关
        'pydantic',
        'pydantic.deprecated',
        'pydantic.deprecated.decorator',
        
        # 数据库相关
        'sqlite3',
        'aiosqlite',
        
        # 其他可能需要的模块
        'multipart',
        'python_multipart',
        'email_validator',
        'httptools',
        'watchfiles',
        'websockets',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除不需要的模块以减小体积
        'tkinter',
        'unittest',
        'test',
        'tests',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='lifeprism-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # 显示控制台窗口便于调试，生产环境可改为 False
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 可以添加图标: 'frontend/public/branding/lifeprism.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='lifeprism-backend',
)
