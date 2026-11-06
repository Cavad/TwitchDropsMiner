"""Window operations restricted to a live browser process owned by this app."""

from __future__ import annotations

import asyncio
import ctypes
from collections.abc import Callable
from ctypes import wintypes


class OwnedBrowserWindows:
    def __init__(self, owns_pid: Callable[[int], bool]):
        self.owns_pid = owns_pid

    def _apply(self, *, close: bool) -> int:
        user = ctypes.WinDLL("user32", use_last_error=True)
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
        user.EnumWindows.restype = wintypes.BOOL
        user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user.GetWindowThreadProcessId.restype = wintypes.DWORD
        user.IsWindowVisible.argtypes = [wintypes.HWND]
        user.IsWindowVisible.restype = wintypes.BOOL
        user.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user.PostMessageW.restype = wintypes.BOOL
        user.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        user.ShowWindow.restype = wintypes.BOOL
        changed = 0
        owners: dict[int, bool] = {}

        def visit(window, _value):
            nonlocal changed
            pid = wintypes.DWORD()
            if user.GetWindowThreadProcessId(window, ctypes.byref(pid)) and user.IsWindowVisible(window):
                if pid.value not in owners:
                    owners[pid.value] = self.owns_pid(pid.value)
                # Recheck immediately before mutating: never act on an exited owner.
                current = wintypes.DWORD()
                if (owners[pid.value] and user.GetWindowThreadProcessId(window, ctypes.byref(current))
                        and current.value == pid.value and self.owns_pid(current.value)):
                    if close:
                        changed += int(bool(user.PostMessageW(window, 0x0010, 0, 0)))
                    else:
                        user.ShowWindow(window, 0)
                        changed += 1
            return True

        callback = callback_type(visit)
        if not user.EnumWindows(callback, 0):
            raise OSError("Owned browser window enumeration failed")
        return changed

    def hide(self) -> int:
        return self._apply(close=False)

    def finish(self) -> int:
        # WM_CLOSE asks the app to flush storage and close normally.
        return self._apply(close=True)

    async def keep_hidden(self, alive: Callable[[], bool]) -> None:
        while alive():
            action = asyncio.create_task(asyncio.to_thread(self.hide))
            try:
                await asyncio.shield(action)
            finally:
                await self.drain(action)
            await asyncio.sleep(.2)

    @staticmethod
    async def drain(awaitable) -> None:
        action = asyncio.ensure_future(awaitable)
        interrupted = False
        while not action.done():
            try:
                await asyncio.shield(action)
            except asyncio.CancelledError:
                interrupted = True
        action.result()
        if interrupted:
            raise asyncio.CancelledError
