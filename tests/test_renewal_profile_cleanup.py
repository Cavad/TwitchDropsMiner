"""Owned renewal profiles tolerate transient locks without escaping cancellation."""

import asyncio
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.auth.server_renewal import OwnedChromium
from src.auth.session_bundle import SessionError


@pytest.mark.asyncio
async def test_cleanup_retries_temporary_file_locks_and_deletes_owned_profile(monkeypatch):
    directory = tempfile.TemporaryDirectory(prefix="tdm-test-renew-")
    path = Path(directory.name)
    cleanup = directory.cleanup
    attempted = []

    def locked():
        attempted.append(True)
        if len(attempted) < 3:
            raise PermissionError("locked temporary profile")
        cleanup()

    directory.cleanup = locked
    monkeypatch.setattr(OwnedChromium, "PROFILE_CLEANUP_DELAYS", (0, 0, 0))
    try:
        await OwnedChromium.cleanup_profile(directory)
        assert len(attempted) == 3 and not path.exists()
    finally:
        cleanup()


@pytest.mark.asyncio
async def test_cleanup_failure_is_bounded_and_does_not_expose_profile_path(monkeypatch):
    monkeypatch.setattr(OwnedChromium, "PROFILE_CLEANUP_DELAYS", (0, 0, 0))
    directory = SimpleNamespace(cleanup=Mock(side_effect=PermissionError("private browser path")))
    with pytest.raises(SessionError, match="BROWSER_STOP") as caught:
        await OwnedChromium.cleanup_profile(directory)
    assert directory.cleanup.call_count == 3
    assert "private browser path" not in str(caught.value)


@pytest.mark.asyncio
async def test_repeated_cancellation_drains_profile_cleanup_before_returning(monkeypatch):
    browser = OwnedChromium("unused")
    inside, cleanup_started, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    actual_cleanup = browser.cleanup_profile
    profiles = []

    async def cleanup(directory):
        cleanup_started.set()
        await release.wait()
        await actual_cleanup(directory)

    monkeypatch.setattr(browser, "cleanup_profile", cleanup)

    async def run():
        async with browser.profile() as path:
            profiles.append(path)
            inside.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(run())
    try:
        await inside.wait()
        task.cancel()
        await cleanup_started.wait()
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done() and profiles[0].exists()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not profiles[0].exists()
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
