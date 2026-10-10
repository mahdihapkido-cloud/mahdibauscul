# weighing.spec
# این فایل را کنار main.py بگذار و بعد اجرا کن:
#   pyinstaller weighing.spec --clean

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

datas = []
datas += collect_data_files('arabic_reshaper')
datas += collect_data_files('bidi')
datas += [
    ('sounds/*',   'sounds'),
    ('fonts/*',    'fonts'),
    ('settings.json', '.'),
]

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'arabic_reshaper',
        'bidi',
        'bidi.algorithm',
        'reportlab',
        'reportlab.pdfbase.ttfonts',
        'reportlab.platypus',
        'reportlab.lib.pagesizes',
        'reportlab.lib.units',
        'reportlab.lib.styles',
        'reportlab.lib.colors',
        'openpyxl',
        'cv2',
        'PyQt6',
        'PyQt6.QtMultimedia',
        'PyQt6.QtMultimediaWidgets',
        'sqlite3',
        'json',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib'],
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
    name='WeighingSystem',
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
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='WeighingSystem',
)
