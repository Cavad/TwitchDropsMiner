"""Packaged smoke check with temporary data, blank browser pages and no credentials."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Any


def run(report_path: str, *, interactive: bool = True) -> int:
    if not interactive:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from desktop.engine import MinerEngine
    from desktop.window import MainWindow

    report: dict[str, Any] = {"frozen": bool(getattr(__import__("sys"), "frozen", False)),
                              "browser_mode": "manual_handoff" if interactive else "protocol_only", "checks": []}
    target = Path(report_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    result = 1
    with tempfile.TemporaryDirectory(prefix="tdm-desktop-verification-") as directory:
        os.environ["TDM_DESKTOP_HOME"] = directory
        os.environ["TDM_DATA_DIR"] = str(Path(directory) / "data")
        try:
            from src.auth.login_helper import NativeChrome, NativeFirefox
            from src.auth.server_renewal import OwnedChromium
            from src.auth.session_bundle import SessionError
            from src.auth.session_controller import SessionController

            async def browser_checks():
                class BlankChrome(NativeChrome):
                    LOGIN_URL = "about:blank"

                chrome = BlankChrome()
                chrome.background_capture = True
                # Hosted runners have no interactive user desktop for WM_CLOSE.
                # Exercise the same owned capture protocol and reject blank auth;
                # the normal local check retains the complete manual handoff.
                chrome._capturing = not interactive
                async with chrome as browser:
                    assert browser.process and browser.process.poll() is None
                    profile = browser.profile
                    if interactive:
                        await browser.finish_login()
                    try:
                        await browser.wait_authenticated(timeout=60)
                        raise AssertionError("Blank browser must not authenticate")
                    except SessionError as error:
                        assert error.code == "HELPER_LOGIN_MISSING", f"Chrome blank handoff: {error.code}"
                    assert browser._capturing and browser._verified
                assert profile is not None and not profile.exists()
                report["checks"].append("native_browser_start_and_cleanup" if interactive else "native_browser_protocol_and_cleanup")
                try:
                    firefox = NativeFirefox.find_firefox()
                except Exception:
                    firefox = None
                if firefox:
                    class BlankFirefox(NativeFirefox):
                        LOGIN_URL = "about:blank"

                    firefox_browser = BlankFirefox(firefox)
                    firefox_browser.background_capture = True
                    firefox_browser._capturing = not interactive
                    async with firefox_browser as browser:
                        assert browser.process and browser.process.poll() is None
                        firefox_profile = browser.profile
                        if interactive:
                            await browser.finish_login()
                        try:
                            await browser.wait_authenticated(timeout=60)
                            raise AssertionError("Blank browser must not authenticate")
                        except SessionError as error:
                            assert error.code == "HELPER_FIREFOX_LOGIN", f"Firefox blank handoff: {error.code}"
                        assert browser._capturing and browser._verified
                    assert firefox_profile is not None and not firefox_profile.exists()
                    report["checks"].append("firefox_browser_start_and_cleanup" if interactive else "firefox_browser_protocol_and_cleanup")
                async with (
                    OwnedChromium(SessionController._browser_executable(), background=True).start() as targets,
                    targets.target() as page,
                ):
                    value = await page.command("Runtime.evaluate", {"expression": "1+1", "returnByValue": True})
                    assert value["result"]["value"] == 2
                report["checks"].append("renewal_browser_protocol_and_cleanup")

            asyncio.run(browser_checks())
            application = QApplication.instance() or QApplication([])
            engine = MinerEngine()
            window = MainWindow(engine)
            # Check native tray lifecycle using only this temporary verification window.
            # No startup registry changes and no user notifications are made.
            window.preferences.values["notifications"] = False
            if window.system_tray.available:
                assert window.system_tray.hide_window()
                assert window.isHidden()
                window.system_tray.restore()
                assert not window.isHidden()
                window.hide()
                report["checks"].append("native_tray_hide_and_restore")
            window._render_connection({"phase": "loading", "message": "Loading campaigns…"})
            assert window.connection_progress.value() == 3
            window.navigate(5)
            assert window.pages.currentIndex() == 5
            window.navigate(0)
            report["checks"].append("connection_progress_and_queue_navigation")
            stage = {"settings_sent": False, "settings_saved": False, "snapshot": False}
            timed_out = []

            def snapshot(data):
                stage["snapshot"] = True
                assert not data["logged_in"]
                if not stage["settings_sent"]:
                    stage["settings_sent"] = True
                    engine.submit("settings", {"games_to_watch": ["Desktop verification game"], "priority_list_only": True})
                elif stage["settings_saved"] and data["settings"]["games_to_watch"] == ["Desktop verification game"]:
                    report["checks"].append("engine_snapshot_and_settings_roundtrip")
                    window.grab().save(str(target.with_suffix(".png")))
                    engine.stop()

            def finished(name, success, message):
                if name == "settings":
                    if not success:
                        report["error"] = message
                        engine.stop()
                    stage["settings_saved"] = success

            def fatal(message):
                report["error"] = message
                engine.stop()

            def timeout():
                timed_out.append(True)
                engine.stop()

            engine.snapshot.connect(snapshot)
            engine.command_finished.connect(finished)
            engine.fatal.connect(fatal)
            engine.finished.connect(application.quit)
            timer = QTimer()
            timer.setSingleShot(True)
            timer.timeout.connect(timeout)
            timer.start(45000)
            engine.start()
            application.exec()
            engine.wait()
            if timed_out:
                raise TimeoutError("Desktop engine check timed out")
            if "error" in report or not stage["settings_saved"] or not stage["snapshot"]:
                raise RuntimeError("Desktop engine check did not complete")
            assert (Path(directory) / "data" / "settings.json").exists()
            report["checks"].append("graceful_shutdown_and_persistent_settings")
            result = 0
        except Exception as error:
            report["error"] = f"{type(error).__name__}: {error}"
        finally:
            report["success"] = result == 0
            target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return result
