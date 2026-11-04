# -*- mode: python ; coding: utf-8 -*-
# Receita do PyInstaller para gerar "Finance Control.app" no macOS.
# Uso (feito automaticamente por Criar_App_Mac.command):
#     pyinstaller --noconfirm --clean packaging/FinanceControl.spec
import os
import sys

from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))  # noqa: F821 (definido pelo PyInstaller)
sys.path.insert(0, ROOT)
from backend import config  # noqa: E402

hidden = []
for package in ("frontend", "backend.services", "backend.utils"):
    hidden += collect_submodules(package)
hidden += collect_submodules("PIL")
hidden += ["backend.config", "database", "PIL._tkinter_finder"]

a = Analysis(
    [os.path.join(ROOT, "backend", "main.py")],
    pathex=[ROOT],
    binaries=[],
    datas=[(os.path.join(ROOT, "locales"), "locales"),
           (os.path.join(ROOT, "assets", "fonts"), os.path.join("assets", "fonts"))],
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=["pytest", "numpy", "pandas", "matplotlib"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FinanceControl",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=os.path.join(ROOT, "assets", "icon.icns"),
)

coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="FinanceControl")

app = BUNDLE(
    coll,
    name="Finance Control.app",
    icon=os.path.join(ROOT, "assets", "icon.icns"),
    bundle_identifier="local.financecontrol.app",
    version=config.APP_VERSION,
    info_plist={
        "CFBundleName": "Finance Control",
        "CFBundleDisplayName": "Finance Control",
        "CFBundleShortVersionString": config.APP_VERSION,
        "CFBundleVersion": config.APP_VERSION,
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "10.13",
        "NSRequiresAquaSystemAppearance": True,
        "NSHumanReadableCopyright": "Uso pessoal",
    },
)
