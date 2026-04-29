from __future__ import annotations

import shutil
import struct
import sys
from functools import lru_cache
from pathlib import Path


SUBSYSTEM_GUI = 2
SUBSYSTEM_CONSOLE = 3


def resolve_windows_redirector_path() -> Path | None:
    if not sys.platform.startswith("win"):
        return None

    try:
        import mitmproxy_windows

        path = Path(mitmproxy_windows.executable_path())
    except Exception:
        return None

    if not path.exists():
        return None
    return path


def read_pe_subsystem(path: Path) -> int:
    with path.open("rb") as f:
        dos_header = f.read(64)
        if len(dos_header) < 64:
            raise ValueError("PE 文件头长度异常")
        pe_offset = struct.unpack_from("<I", dos_header, 0x3C)[0]
        f.seek(pe_offset + 4 + 20 + 68)
        raw = f.read(2)
        if len(raw) < 2:
            raise ValueError("PE Optional Header 长度异常")
        return struct.unpack("<H", raw)[0]


def patch_pe_subsystem(path: Path, subsystem: int) -> None:
    with path.open("r+b") as f:
        dos_header = f.read(64)
        if len(dos_header) < 64:
            raise ValueError("PE 文件头长度异常")
        pe_offset = struct.unpack_from("<I", dos_header, 0x3C)[0]
        f.seek(pe_offset + 4 + 20 + 68)
        f.write(struct.pack("<H", subsystem))


@lru_cache(maxsize=1)
def ensure_windows_redirector_gui_subsystem() -> tuple[bool, str]:
    path = resolve_windows_redirector_path()
    if path is None:
        return False, "未找到 windows-redirector.exe"

    try:
        current = read_pe_subsystem(path)
    except Exception as e:
        return False, f"读取 windows-redirector.exe 子系统失败: {e}"

    if current == SUBSYSTEM_GUI:
        return True, f"windows-redirector 已是 GUI 子系统: {path}"

    if current != SUBSYSTEM_CONSOLE:
        return False, f"windows-redirector 子系统未知({current}): {path}"

    backup_path = path.with_name(f"{path.stem}.console{path.suffix}")
    try:
        if not backup_path.exists():
            shutil.copy2(path, backup_path)
        patch_pe_subsystem(path, SUBSYSTEM_GUI)
        patched = read_pe_subsystem(path)
    except Exception as e:
        return False, f"修补 windows-redirector 子系统失败: {e}"

    if patched != SUBSYSTEM_GUI:
        return False, f"修补后子系统仍异常({patched}): {path}"

    return True, f"已将 windows-redirector 改为 GUI 子系统: {path}"
