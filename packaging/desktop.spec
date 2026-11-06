from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, copy_metadata
from desktop.packaging import keep_binary

root = Path(SPECPATH).parent
metadata = copy_metadata('PySide6', recursive=True) + copy_metadata('twitch-drops-miner', recursive=True)
analysis = Analysis(
    [str(root / 'desktop_main.py')],
    pathex=[str(root)],
    binaries=[],
    datas=[(str(root / 'lang'), 'lang'), (str(root / 'web'), 'web'), (str(root / 'LICENSE'), '.'), (str(root / 'THIRD_PARTY_NOTICES.md'), '.')] + metadata,
    hiddenimports=collect_submodules('src') + ['desktop.engine', 'desktop.window'],
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['pytest', 'mypy', 'ruff', 'coverage', 'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtQml', 'PySide6.QtQuick'],
    noarchive=False,
)
analysis.binaries = [entry for entry in analysis.binaries if keep_binary(entry[0])]
archive = PYZ(analysis.pure)
executable = EXE(
    archive, analysis.scripts, analysis.binaries, analysis.datas, [],
    name='Twitch Drops Miner', debug=False, strip=False, upx=False,
    console=False, icon=str(root / 'icons' / 'desktop.ico'),
)
