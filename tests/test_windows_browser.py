"""Owned-window actions never touch unrelated browser windows."""

import asyncio
import ctypes
import sys
import threading
from contextlib import asynccontextmanager
from ctypes import wintypes
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.auth.windows_browser import OwnedBrowserWindows


@pytest.mark.parametrize("action", ["finish", "hide"])
def test_window_operations_only_touch_live_owned_pids(monkeypatch, action):
    def pid(window, target):
        ctypes.cast(target, ctypes.POINTER(wintypes.DWORD)).contents.value = {10: 123, 20: 456}[window]
        return 1

    user = SimpleNamespace(
        EnumWindows=Mock(side_effect=lambda callback, _: callback(10, 0) and callback(20, 0)),
        GetWindowThreadProcessId=Mock(side_effect=pid), IsWindowVisible=Mock(return_value=True),
        PostMessageW=Mock(return_value=True), ShowWindow=Mock(return_value=True),
    )
    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **k: user, raising=False)
    monkeypatch.setattr(ctypes, "WINFUNCTYPE", lambda *a: lambda callback: callback, raising=False)
    assert getattr(OwnedBrowserWindows(lambda value: value == 123), action)() == 1
    if action == "finish":
        user.PostMessageW.assert_called_once_with(10, 0x0010, 0, 0)
        user.ShowWindow.assert_not_called()
    else:
        user.ShowWindow.assert_called_once_with(10, 0)
        user.PostMessageW.assert_not_called()


@pytest.mark.asyncio
async def test_hiding_worker_is_drained_before_cancellation_returns(monkeypatch):
    started, release = threading.Event(), threading.Event()
    windows = OwnedBrowserWindows(lambda _: True)

    def hide():
        started.set()
        assert release.wait(5)

    monkeypatch.setattr(windows, "hide", hide)
    task = asyncio.create_task(windows.keep_hidden(lambda: True))
    assert await asyncio.to_thread(started.wait, 2)
    task.cancel()
    await asyncio.sleep(.02)
    assert not task.done()
    task.cancel()
    await asyncio.sleep(.02)
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
@pytest.mark.skipif(sys.platform != "win32", reason="Windows handoff ownership")
async def test_finish_request_cannot_close_replacement_capture_browser(monkeypatch):
    from src.auth import login_helper

    browser = login_helper.NativeChrome()
    manual = Mock(pid=123, poll=Mock(return_value=None))
    captured = Mock(pid=456, poll=Mock(return_value=None))
    browser.process = manual

    def finish(windows):
        assert windows.owns_pid(123)
        browser._capturing = True
        browser.process = captured
        assert not windows.owns_pid(123)
        assert not windows.owns_pid(456)
        return 1

    monkeypatch.setattr(OwnedBrowserWindows, "finish", finish)
    await browser.finish_login()


@pytest.mark.asyncio
@pytest.mark.skipif(sys.platform != "win32", reason="Windows SDK hider lifecycle")
async def test_sdk_process_is_stopped_after_repeated_cancellation_while_hider_drains(monkeypatch, tmp_path):
    from src.auth.server_renewal import OwnedChromium

    started, release = threading.Event(), threading.Event()
    entered = asyncio.Event()
    process = SimpleNamespace(pid=123, returncode=None)
    browser = OwnedChromium("synthetic-browser", background=True)

    def hide(_windows):
        started.set()
        assert release.wait(5)

    monkeypatch.setattr(OwnedBrowserWindows, "hide", hide)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", AsyncMock(return_value=process))
    stopped = AsyncMock()
    monkeypatch.setattr(browser, "finish_stop", stopped)

    async def use():
        async with browser.process(["synthetic-browser"], tmp_path):
            entered.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(use())
    await entered.wait()
    assert await asyncio.to_thread(started.wait, 2)
    task.cancel()
    await asyncio.sleep(.01)
    task.cancel()
    await asyncio.sleep(.01)
    assert not task.done()
    stopped.assert_not_awaited()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    stopped.assert_awaited_once_with(process)


@pytest.mark.asyncio
@pytest.mark.skipif(sys.platform != "win32", reason="Windows hidden normal browser startup")
async def test_desktop_verifier_uses_normal_browser_but_default_still_uses_headless(monkeypatch):
    from src.auth.server_renewal import OwnedChromium

    seen = []

    @asynccontextmanager
    async def process(args, profile, **options):
        seen.append((args, options))
        yield SimpleNamespace(returncode=None, pid=123)

    for background in (False, True):
        browser = OwnedChromium("chromium", background=background)
        monkeypatch.setattr(browser, "process", process)
        monkeypatch.setattr(browser, "wait_ready", AsyncMock(return_value="http://127.0.0.1:12345"))
        async with browser.start():
            pass
        args, options = seen[-1]
        assert ("--headless=new" in args) is not background
        if background:
            assert options["startupinfo"].wShowWindow == 0
            assert "--window-position=-32000,-32000" in args
