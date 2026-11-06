"""Behavioral checks for the optional native Windows desktop edition."""

import asyncio
import copy
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest


pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QObject, Signal
from PySide6.QtWidgets import QApplication, QPushButton

from desktop.engine import MinerEngine
from desktop.model import campaign_matches, desktop_home, normalize_games, progress_percent
from desktop.packaging import keep_binary
from desktop.window import MainWindow


class FakeEngine(QObject):
    snapshot = Signal(dict)
    ready = Signal()
    notice = Signal(str)
    fatal = Signal(str)
    login_phase = Signal(str)
    login_finished = Signal(bool, str)
    command_finished = Signal(str, bool, str)
    exported = Signal(str)
    finished = Signal()

    def __init__(self):
        super().__init__()
        self.commands = []

    def submit(self, name, payload=None):
        self.commands.append((name, copy.deepcopy(payload)))

    def isRunning(self):
        return False


@pytest.mark.parametrize("ci", [False, True])
def test_packaged_verification_cli_routes_without_launching_miner(monkeypatch, tmp_path, ci):
    import desktop_main
    from desktop import verify

    report = str(tmp_path / "report.json")
    arguments = ["desktop_main.py", "--verify-build", report] + (["--ci"] if ci else [])
    monkeypatch.setattr(sys, "argv", arguments)
    run = Mock(return_value=0)
    monkeypatch.setattr(verify, "run", run)
    assert desktop_main.main() == 0
    run.assert_called_once_with(report, interactive=not ci)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def snapshot():
    return {
        "logged_in": False,
        "settings": {
            "games_to_watch": ["First game"], "games_available": ["First game", "Second game"],
            "priority_list_only": True, "minimum_refresh_interval_minutes": 30,
            "mining_benefits": dict.fromkeys(("BADGE", "EMOTE", "DIRECT_ENTITLEMENT", "UNKNOWN"), True),
        },
        "campaigns": [], "history": [], "lines": [],
    }


@pytest.fixture
def window(app):
    engine = FakeEngine()
    widget = MainWindow(engine)
    engine.ready.emit()
    engine.snapshot.emit(snapshot())
    yield widget, engine
    widget.close()
    widget.deleteLater()
    app.processEvents()


def test_desktop_data_is_not_written_inside_bundle(monkeypatch, tmp_path):
    monkeypatch.setenv("TDM_DESKTOP_HOME", str(tmp_path / "desktop"))
    assert desktop_home() == tmp_path / "desktop"
    data_dir = tmp_path / "private-data"
    environment = {**os.environ, "TDM_DATA_DIR": str(data_dir)}
    result = subprocess.run(
        [sys.executable, "-c", "from src.config.paths import DATA_DIR; print(DATA_DIR)"],
        cwd=Path(__file__).resolve().parents[1], env=environment,
        capture_output=True, text=True, check=True,
    )
    assert Path(result.stdout.strip()) == data_dir
    assert data_dir.is_dir()


def test_game_and_campaign_rules_do_not_invent_progress():
    assert normalize_games(" First\nfirst\n Second \n\n") == ["First", "Second"]
    assert progress_percent(None) == 0
    assert progress_percent({"current_minutes": 900, "required_minutes": 60}) == 100
    assert progress_percent({"current_minutes": 5, "required_minutes": 0}) == 0
    assert progress_percent({"current_minutes": 15, "required_minutes": 60}) == 25
    campaign = {"name": "Weekend", "game_name": "Example", "active": True, "finished": False}
    assert campaign_matches(campaign, "EXAMPLE", "Active")
    assert not campaign_matches(campaign, "wrong", "All campaigns")
    assert not campaign_matches(campaign, "", "Completed")
    assert campaign_matches({**campaign, "finished": True}, "", "Completed")


@pytest.mark.parametrize("name", ["icuuc.dll", "PySide6\\ICUUC.dll", "ucrtbase.dll", "api-ms-win-crt-runtime-l1-1-0.dll"])
def test_packaging_never_shadows_windows_icu_or_api_runtime(name):
    assert not keep_binary(name)
    assert keep_binary("PySide6\\Qt6Core.dll")
    assert keep_binary("python312.dll")


def test_login_controls_prevent_duplicate_start_and_recover_after_failure(window):
    widget, engine = window
    widget.connect_button.click()
    widget.connect_button.click()
    assert engine.commands == [("login", {"browser": "auto"})]
    assert not widget.connect_button.isEnabled()
    engine.login_phase.emit("login")
    assert "Finish sign-in" in widget.login_hint.text()
    engine.login_finished.emit(False, "Browser missing. Install Chrome.")
    assert widget.connect_button.isEnabled()
    assert not widget.login_busy
    assert widget.banner_text.text() == "Browser missing. Install Chrome."
    widget.connect_button.click()
    assert len(engine.commands) == 2


def test_successful_login_renders_actual_snapshot_and_changes_primary_action(window):
    widget, engine = window
    data = snapshot()
    data.update(logged_in=True, total_claimed=3, progress={"drop_name": "Test reward", "game_name": "First game", "current_minutes": 15, "required_minutes": 60})
    engine.snapshot.emit(data)
    assert widget.metrics[1].text() == "3"
    assert widget.mining_title.text() == "Test reward"
    assert widget.mining_progress.value() == 25
    widget.connect_button.click()
    assert widget.pages.currentIndex() == 0
    assert not engine.commands
    widget.pause_button.click()
    assert engine.commands[-1] == ("pause", True)


@pytest.mark.parametrize("success", [True, False])
def test_save_acknowledgement_preserves_edits_made_while_save_pending(window, success):
    widget, engine = window
    widget.game_picker.setCurrentText("Saved game")
    widget._add_game()
    widget.save_button.click()
    submitted = engine.commands[-1][1]
    assert submitted["games_to_watch"] == ["First game", "Saved game"]
    widget.game_picker.setCurrentText("Later edit")
    widget._add_game()
    data = snapshot()
    if success:
        data["settings"]["games_to_watch"] = submitted["games_to_watch"]
    engine.snapshot.emit(data)
    engine.command_finished.emit("settings", success, "Failed" if not success else "")
    assert widget._game_names() == ["First game", "Saved game", "Later edit"]
    assert widget.settings_dirty
    assert widget.save_button.isEnabled()
    widget.save_button.click()
    assert engine.commands[-1][1]["games_to_watch"][-1] == "Later edit"


def test_successful_save_clears_dirty_only_after_confirmed_snapshot(window):
    widget, engine = window
    widget.game_picker.setCurrentText("Second game")
    widget._add_game()
    widget.save_button.click()
    data = snapshot()
    data["settings"]["games_to_watch"] = ["First game", "Second game"]
    engine.snapshot.emit(data)
    engine.command_finished.emit("settings", True, "")
    assert not widget.settings_dirty
    assert not widget.save_button.isEnabled()
    assert widget._game_names() == ["First game", "Second game"]


def test_campaign_text_is_plain_and_addition_preserves_draft_settings(window):
    widget, engine = window
    widget.game_picker.setCurrentText("Unsaved game")
    widget._add_game()
    widget._add_campaign_game("Campaign game")
    assert widget._game_names() == ["First game", "Unsaved game", "Campaign game"]
    assert widget.pages.currentIndex() == 4
    assert not engine.commands
    widget._add_campaign_game("CAMPAIGN GAME")
    assert widget.games_list.count() == 3


def add_buttons(widget):
    # Rebuilt cards are released with deleteLater(); flush them before inspecting.
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    return [button for button in widget.findChildren(QPushButton)
            if button.text().startswith("Add to mining list")]


def test_campaign_add_action_follows_saved_mining_list(window):
    widget, engine = window
    data = snapshot()
    data["campaigns"] = [{"game_name": "Second game", "name": "November", "drops": [], "active": True}]
    engine.snapshot.emit(data)
    assert len(add_buttons(widget)) == 1
    widget._add_campaign_game("Second game")
    widget.save_button.click()
    assert all(not button.isEnabled() for button in add_buttons(widget))
    saved = copy.deepcopy(data)
    saved["settings"]["games_to_watch"] = ["First game", "SECOND GAME"]
    engine.snapshot.emit(saved)
    engine.command_finished.emit("settings", True, "")
    # Campaign data is unchanged; the saved list alone must remove the stale action.
    assert add_buttons(widget) == []
    engine.snapshot.emit(data)
    assert len(add_buttons(widget)) == 1
    assert add_buttons(widget)[0].isEnabled()


def test_export_uses_entire_backend_content_and_reports_unwritable_path(window, tmp_path):
    widget, engine = window
    widget.export_path = tmp_path / "history.csv"
    engine.exported.emit("\ufeffgame,reward\nExample,Reward\n")
    assert (tmp_path / "history.csv").read_text(encoding="utf-8").startswith("\ufeffgame,reward")
    widget.export_path = tmp_path / "not-created" / "history.csv"
    engine.exported.emit("content")
    assert "Could not save" in widget.banner_text.text()


def test_startup_failure_disables_actions(window):
    widget, engine = window
    engine.fatal.emit("Startup failed")
    assert not widget.connect_button.isEnabled()
    assert not widget.pause_button.isEnabled()
    assert not widget.save_button.isEnabled()
    assert widget.banner_text.text() == "Startup failed"


@pytest.mark.asyncio
async def test_native_login_uses_validated_helper_and_reports_success(monkeypatch, app):
    from src.auth import login_helper

    engine = MinerEngine()
    engine.port = 12345
    enabled = []

    async def enable(authorized):
        assert authorized()
        enabled.append(True)

    class Helper:
        def __init__(self, destination, report, browser_factory):
            assert destination == "http://127.0.0.1:12345"
            self.report = report

        async def run(self):
            assert enabled
            self.report("capturing")

    engine.client = SimpleNamespace(enable_helper=enable)
    monkeypatch.setattr(login_helper, "NativeLoginHelper", Helper)
    outcomes = []
    engine.login_finished.connect(lambda success, message: outcomes.append(success))
    await engine._login()
    assert outcomes == [True]


@pytest.mark.asyncio
async def test_cancelling_login_drains_helper_before_disabling_admission(monkeypatch, app):
    from src.auth import login_helper

    engine = MinerEngine()
    entered = asyncio.Event()
    cleaned = []

    class Helper:
        def __init__(self, *args, **kwargs):
            pass

        async def run(self):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleaned.append(True)

    async def cancel():
        assert cleaned

    engine.client = SimpleNamespace(enable_helper=AsyncMock(), cancel_helper=cancel)
    monkeypatch.setattr(login_helper, "NativeLoginHelper", Helper)
    engine._snapshot = Mock(return_value={})
    engine.login_task = asyncio.create_task(engine._login())
    await entered.wait()
    await engine._dispatch("cancel_login", None)
    assert cleaned == [True]
    assert engine.login_task.done()


def test_native_layout_fits_supported_window_sizes(window, app):
    widget, _engine = window
    for width, height in ((1280, 860), (1000, 720)):
        widget.resize(width, height)
        widget.show()
        app.processEvents()
        assert widget.connect_button.geometry().width() >= 190
        assert widget.pages.width() > 650
        assert widget.status_line.geometry().bottom() <= widget.centralWidget().height()


def test_long_login_error_and_waiting_hint_do_not_overlap_controls(window, app):
    from PySide6.QtCore import QPoint

    widget, engine = window
    widget.resize(1000, 720)
    widget.show()
    widget.connect_button.click()
    widget.show_notice("The temporary browser profile could not be deleted. " * 4, persistent=True)
    engine.login_phase.emit("login")
    app.processEvents()
    copy_bottom = widget.hero_copy.mapTo(widget.centralWidget(), QPoint(0, widget.hero_copy.height())).y()
    button_top = widget.connect_button.mapTo(widget.centralWidget(), QPoint(0, 0)).y()
    button_bottom = widget.connect_button.mapTo(widget.centralWidget(), QPoint(0, widget.connect_button.height())).y()
    hint_top = widget.login_hint.mapTo(widget.centralWidget(), QPoint(0, 0)).y()
    assert copy_bottom < button_top
    assert button_bottom < hint_top
    assert widget.hero_copy.height() >= widget.hero_copy.heightForWidth(widget.hero_copy.width())
    assert widget.overview_scroll.verticalScrollBar().maximum() > 0
    assert widget.overview_scroll.widget().width() <= widget.overview_scroll.viewport().width()


def test_new_login_clears_previous_error_and_cancel_is_not_reentrant(window):
    widget, engine = window
    widget.show_notice("Previous cleanup failed", persistent=True)
    widget.connect_button.click()
    assert widget.banner.isHidden()
    widget.cancel_login.click()
    widget.cancel_login.click()
    assert sum(name == "cancel_login" for name, _ in engine.commands) == 1
    assert not widget.connect_button.isEnabled()
    assert not widget.cancel_login.isEnabled()
    engine.login_finished.emit(False, "Sign-in cancelled")
    assert widget.connect_button.isEnabled()
    engine.login_phase.emit("login")
    assert not widget.login_busy
    assert widget.connect_button.text() == "Connect Twitch  →"


def test_user_can_select_firefox_and_retry_after_failed_login(window):
    widget, engine = window
    widget.login_browser.setCurrentIndex(widget.login_browser.findData("firefox"))
    widget.connect_button.click()
    assert engine.commands[-1] == ("login", {"browser": "firefox"})
    assert not widget.login_browser.isEnabled()
    engine.login_finished.emit(False, "Sign-in did not complete")
    assert widget.login_browser.isEnabled()
    widget.connect_button.click()
    assert engine.commands[-1] == ("login", {"browser": "firefox"})


def test_finish_signin_starts_automatic_handoff_without_navigating_campaigns(window):
    widget, engine = window
    widget.connect_button.click()
    engine.login_phase.emit("login")
    assert not widget.finish_login.isHidden()
    widget.finish_login.click()
    widget.finish_login.click()
    assert sum(name == "finish_login" for name, _ in engine.commands) == 1
    assert not widget.finish_login.isEnabled()
    engine.login_phase.emit("capturing")
    assert widget.finish_login.isHidden()
    assert "automatically" in widget.login_hint.text()
    data = snapshot()
    data.update(logged_in=True, campaigns=[{"game_name": "Example", "name": "Sample", "active": True, "drops": []}])
    engine.snapshot.emit(data)
    engine.login_finished.emit(True, "Connected")
    assert widget.pages.currentIndex() == 0
    assert widget.metrics[0].text() == "1"


def test_progress_recovery_action_and_queue_keep_current_page(window):
    widget, engine = window
    widget.navigate(5)
    widget._render_connection({"phase": "attention", "message": "Retry verification", "can_recover": True,
                               "diagnostic": {"code": "CATALOG", "stage": "issued_validation", "reason": "integrity"}})
    assert not widget.recover_button.isHidden()
    assert "issued_validation" in widget.connection_message.text()
    widget.recover_button.click()
    assert engine.commands[-1] == ("recover", None)
    widget._render_connection({"phase": "loading", "message": "Loading"})
    assert widget.connection_progress.value() == 3 and widget.recover_button.isHidden()
    row = {"id": "one", "game": "Game", "campaign": "Campaign", "reward": "Reward", "chain_minutes": 65,
           "estimated_finish": "2026-11-06T14:30:01+00:00", "deadline": "2026-11-06T16:00:00+00:00", "fits": True}
    widget._render_queue([row])
    assert widget.queue_table.item(0, 2).text() == "1h 05m"
    assert widget.queue_table.item(0, 5).text() == "May fit"
    signature = widget.queue_signature
    widget._render_queue([{**row, "estimated_finish": "2026-11-06T14:30:03+00:00"}])
    assert widget.queue_signature == signature and widget.pages.currentIndex() == 5


def test_close_to_tray_keeps_engine_running_and_explicit_quit_stops(window, monkeypatch):
    from PySide6.QtGui import QCloseEvent

    widget, engine = window
    engine.isRunning = lambda: True
    engine.stop = Mock()
    widget.preferences.values["close_to_tray"] = True
    widget.system_tray.available = True
    widget.system_tray.hide_window = Mock(return_value=True)
    event = QCloseEvent()
    widget.closeEvent(event)
    assert not event.isAccepted() and not widget.closing
    engine.stop.assert_not_called()
    widget.system_tray.hide_window.assert_called_once()
    widget.force_quit = True
    widget.closeEvent(QCloseEvent())
    engine.stop.assert_called_once()
    assert widget.closing
    engine.isRunning = lambda: False


def test_no_tray_never_hides_window_and_close_stops_engine(window):
    from PySide6.QtGui import QCloseEvent

    widget, engine = window
    widget.system_tray.available = False
    widget.system_tray.hide_window = Mock(return_value=False)
    widget._hide_to_tray()
    assert "tray" in widget.banner_text.text().lower()
    engine.isRunning = lambda: True
    engine.stop = Mock()
    widget.preferences.values["close_to_tray"] = True
    widget.closeEvent(QCloseEvent())
    engine.stop.assert_called_once()
    engine.isRunning = lambda: False


def test_desktop_options_save_is_local_and_updates_queue_policy(window, tmp_path):
    from desktop.preferences import DesktopPreferences

    widget, engine = window
    widget.preferences = DesktopPreferences(tmp_path / "desktop.json")
    widget.desktop_options["automatic_queue"].setChecked(False)
    widget._save_desktop_options()
    assert not widget.desktop_options_dirty
    assert engine.commands[-1] == ("desktop_policy", False)
    assert not DesktopPreferences(tmp_path / "desktop.json").values["automatic_queue"]


@pytest.mark.asyncio
async def test_saved_recovery_retries_then_refreshes_without_login_browser(app, monkeypatch):
    from src.auth.recovery import SessionRecovery
    from src.auth.session_bundle import SessionError

    monkeypatch.setattr(SessionRecovery, "DELAYS", (0, 0))
    engine = MinerEngine()
    controller = SimpleNamespace(session=SimpleNamespace(seed=lambda: object()),
                                 renew_once=AsyncMock(side_effect=[SessionError("CATALOG", reason="integrity"), {}]))
    engine.client = SimpleNamespace(session_controller=controller, request_inventory_refresh=Mock())
    await engine._recover()
    assert controller.renew_once.await_count == 2
    engine.client.request_inventory_refresh.assert_called_once()
    assert not engine.recovering and engine.connection_error is None
    assert engine.connection["phase"] == "loading" and engine.active_login_browser is None


@pytest.mark.asyncio
async def test_saved_recovery_does_not_retry_account_failure_and_clears_busy(app):
    from src.auth.session_bundle import SessionError

    engine = MinerEngine()
    renew = AsyncMock(side_effect=SessionError("ACCOUNT_MISMATCH"))
    engine.client = SimpleNamespace(session_controller=SimpleNamespace(session=SimpleNamespace(seed=lambda: object()), renew_once=renew))
    with pytest.raises(SessionError, match="ACCOUNT_MISMATCH"):
        await engine._recover()
    renew.assert_awaited_once()
    assert not engine.recovering and engine.connection_error.code == "ACCOUNT_MISMATCH"


@pytest.mark.parametrize(("pending", "state", "expected"), [(True, "IDLE", "loading"), (False, "INVENTORY_FETCH", "loading"), (False, "IDLE", "ready")])
def test_cached_inventory_does_not_report_ready_during_refresh(app, monkeypatch, pending, state, expected):
    from desktop.planning import MiningPlanner

    engine = MinerEngine()
    gui = Mock()
    gui.status.get.return_value = "Status"
    gui.login.get_status.return_value = {}
    gui.progress.get_current_drop.return_value = None
    gui.channels.get_channels.return_value = []
    gui.inv.get_campaigns.return_value = []
    gui.settings.get_settings.return_value = {}
    gui.output.get_history.return_value = []
    engine.client = SimpleNamespace(gui=gui, _auth_state=SimpleNamespace(_logged_in=SimpleNamespace(is_set=lambda: True)),
                                     _inventory_loaded=True, _inventory_refresh_pending=pending, _state=SimpleNamespace(name=state),
                                     session_controller=SimpleNamespace(status=lambda: {}, session=SimpleNamespace(seed=lambda: None)),
                                     pause_info=lambda: {}, drop_history=SimpleNamespace(get_entries=lambda **kwargs: [], total_count=0))
    monkeypatch.setattr(MiningPlanner, "build", lambda _: [])
    assert engine._snapshot()["connection"]["phase"] == expected


@pytest.mark.asyncio
async def test_finish_handoff_only_calls_active_owned_browser_and_does_not_authenticate(app):
    engine = MinerEngine()
    browser = SimpleNamespace(finish_login=AsyncMock())
    engine.active_login_browser = browser
    engine._snapshot = Mock(return_value={})
    outcomes = []
    engine.login_finished.connect(lambda *args: outcomes.append(args))
    await engine._dispatch("finish_login", None)
    browser.finish_login.assert_awaited_once()
    assert not outcomes


@pytest.mark.asyncio
async def test_login_timeout_drains_browser_and_revokes_admission_before_ui_reset(monkeypatch, app):
    from src.auth import login_helper

    engine = MinerEngine()
    engine.LOGIN_TIMEOUT_SECONDS = .02
    events = []

    class Helper:
        def __init__(self, *args, **kwargs):
            pass

        async def run(self):
            try:
                await asyncio.Event().wait()
            finally:
                events.append("browser-cleaned")

    async def cancel():
        events.append("admission-revoked")

    engine.client = SimpleNamespace(enable_helper=AsyncMock(), cancel_helper=cancel)
    monkeypatch.setattr(login_helper, "NativeLoginHelper", Helper)
    engine.login_finished.connect(lambda success, message: events.append((success, message)))
    await engine._login()
    assert events[:2] == ["browser-cleaned", "admission-revoked"]
    assert events[2][0] is False and "timed out" in events[2][1]


@pytest.mark.asyncio
async def test_native_helper_uses_selected_browser_without_skipping_session_flow(monkeypatch, app):
    from src.auth import login_helper

    engine = MinerEngine()
    engine.client = SimpleNamespace(enable_helper=AsyncMock(), cancel_helper=AsyncMock())
    select = Mock(return_value=SimpleNamespace())
    monkeypatch.setattr(login_helper.BrowserSelection, "create", select)

    class Helper:
        def __init__(self, destination, report, browser_factory):
            self.browser_factory = browser_factory

        async def run(self):
            assert self.browser_factory() is select.return_value

    monkeypatch.setattr(login_helper, "NativeLoginHelper", Helper)
    await engine._login("firefox")
    select.assert_called_once_with("firefox")
    engine.client.enable_helper.assert_awaited_once()
    engine.client.cancel_helper.assert_not_awaited()
