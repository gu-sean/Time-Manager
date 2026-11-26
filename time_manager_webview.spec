# -*- mode: python ; coding: utf-8 -*-
# main.py 를 진입점으로 TimeManager.exe 빌드
# - 이름을 바꾸면 installer/TimeManager.iss, version_info.txt 도 함께 수정

from PyInstaller.utils.hooks import collect_dynamic_libs

from PyInstaller.depend import bindepend


def _safe_get_paths_for_parent_directory_preservation():
    import pathlib
    import site
    import sys

    excluded_paths = {
        pathlib.Path(sys.base_prefix),
        pathlib.Path(sys.base_prefix).resolve(),
        pathlib.Path(sys.prefix),
        pathlib.Path(sys.prefix).resolve(),
    }
    discovered_paths = set()

    for raw_path in site.getsitepackages():
        if not raw_path:
            continue

        path = pathlib.Path(raw_path)
        try:
            candidates = (path, path.resolve())
        except OSError:
            candidates = (path,)

        for candidate in candidates:
            try:
                if candidate.is_dir() and candidate not in excluded_paths:
                    discovered_paths.add(candidate)
            except OSError:
                continue

    return sorted(discovered_paths, key=lambda item: len(item.parents), reverse=True)


bindepend._get_paths_for_parent_directory_preservation = _safe_get_paths_for_parent_directory_preservation


a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=collect_dynamic_libs("uiautomation"),
    datas=[("rules.json", "."), ("webui/dist", "webui/dist"), ("assets/icon.ico", "assets")],
    hiddenimports=["pystray._win32", "PIL._tkinter_finder", "winotify"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name="TimeManager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/icon.ico",
    version="version_info.txt",
)
