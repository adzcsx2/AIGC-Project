"""Windows read leases that deny external writes and replacement without copying media."""

from __future__ import annotations

import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO


def _windows_read_fd(path: str, _flags: int) -> int:
    import ctypes
    import msvcrt
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    create.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes = (wintypes.HANDLE,)
    close.restype = wintypes.BOOL
    # GENERIC_READ, FILE_SHARE_READ, OPEN_EXISTING. No WRITE or DELETE sharing:
    # readers coexist, while an existing writer or a later rename/write conflicts.
    handle = create(path, 0x80000000, 1, None, 3, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        error = ctypes.get_last_error()
        if error in (32, 33):
            raise ValueError("文件正被写入或替换，无法保护当前版本；请关闭写入程序后重试")
        raise ctypes.WinError(error)
    try:
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except BaseException:
        close(handle)
        raise
    try:
        os.set_inheritable(descriptor, False)
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


@contextmanager
def guarded_read(path: str | Path) -> Iterator[BinaryIO]:
    """Hold the same immutable file version until the consumer finishes.

    This is a mandatory Windows sharing restriction, not an advisory lock.
    Other platforms fail closed rather than silently copying entire media or
    claiming that cooperative flock protects against arbitrary external writers.
    """
    if os.name != "nt":
        raise ValueError("不复制媒体的审片读取保护目前仅支持 Windows；当前平台无法安全审片")
    path = Path(path).resolve(strict=True)
    with open(path, "rb", opener=_windows_read_fd) as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("审片读取保护只接受普通文件")
        current = path.stat()
        if path.resolve(strict=True) != path or (current.st_dev, current.st_ino) != (
            info.st_dev,
            info.st_ino,
        ):
            raise ValueError("文件路径在建立读取保护时已变化，请重试")
        yield stream
