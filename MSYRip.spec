# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — MSY Rip.

Derleme:
    pyinstaller MSYRip.spec
Sonuç:
    dist/MSYRip/MSYRip.exe  (+ _internal klasörü)
"""
import sys
import os
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

hiddenimports = collect_submodules('PIL') + collect_submodules('numpy') + collect_submodules('tifffile')

# 15/11/2026: PyQt6 platform eklentileri (qwindows.dll) otomatik alinmiyordu
# -> "DLL load failed while importing QtWidgets" hatasi. Elle ekle.
_qt_plugins = []
_binaries = []
try:
    import PyQt6
    _pyqt_dir = os.path.dirname(PyQt6.__file__)
    _plugins = os.path.join(_pyqt_dir, 'Qt6', 'plugins')
    if os.path.isdir(_plugins):
        for root, dirs, files in os.walk(_plugins):
            for f in files:
                if f.endswith('.dll'):
                    src = os.path.join(root, f)
                    rel = os.path.relpath(root, _plugins)
                    dst = os.path.join('PyQt6', 'Qt6', 'plugins', rel)
                    _binaries.append((src, dst))
except Exception:
    pass

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=_binaries,
    datas=[('resources/profiles/Renk Profili.icc', 'resources/profiles'),
           ('version.json', '.'),
           ('core/masks/mask101.bin', 'core/masks'),
           ('core/masks/mask102.bin', 'core/masks')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'pandas'],
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
    name='MSYRip',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # GUI uygulaması — konsol yok
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resources/msyrip.ico' if __import__('os').path.exists('resources/msyrip.ico') else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MSYRip',
)
