# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = []
hiddenimports += ['PySide6', 'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets']
hiddenimports += collect_submodules('firebird')
hiddenimports += collect_submodules('fdb')
hiddenimports += collect_submodules('keyring')

a = Analysis(
    ['run_app.py'],
    pathex=['.'],
    binaries=[],
    datas=[('assets/firebird-maintenance-studio.ico', 'assets')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['qt_runtime_hook.py'],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FirebirdMaintenanceStudio',
    icon='assets/firebird-maintenance-studio.ico',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FirebirdMaintenanceStudio',
)
