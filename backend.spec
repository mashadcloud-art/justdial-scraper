# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# ── Collect data files from packages that have non-Python assets ──
datas = []
datas += collect_data_files('playwright_stealth')   # JS stealth files
datas += collect_data_files('playwright')            # Playwright driver assets
datas += collect_data_files('certifi')               # SSL certs
datas += collect_data_files('httpx')
datas += collect_data_files('anyio')

# ── Hidden imports that PyInstaller misses ──
hiddenimports = [
    'app',
    'app.main',
    'app.api',
    'app.api.sync',
    'app.api.categories',
    'app.api.pincodes',
    'app.api.gmaps',
    'app.api.simple_scrape',
    'app.api.setup',
    'app.database',
    'app.models',
    'app.schemas',
    'app.scraper',
    'config',
    'app_config',
    'psutil._psutil_windows',
    'playwright_stealth',
    'playwright_stealth.stealth',
    'anyio._backends._asyncio',
    'anyio._backends._trio',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.asyncio',
    'uvicorn.loops.uvloop',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.http.h11_impl',
    'uvicorn.protocols.http.httptools_impl',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.protocols.websockets.websockets_impl',
    'uvicorn.protocols.websockets.wsproto_impl',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'uvicorn.lifespan.off',
    'sqlalchemy.dialects.sqlite',
    'sqlalchemy.dialects.postgresql',
    'psycopg2',
    'email.mime.multipart',
    'email.mime.text',
]

a = Analysis(
    ['backend_entry.py'],
    pathex=['.', 'app'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'streamlit',
        'pandas',
        'matplotlib',
        'numpy',
        'scipy',
        'PIL',
        'tkinter',
        'PyQt5',
        'wx',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
