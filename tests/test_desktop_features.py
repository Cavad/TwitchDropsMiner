"""Native queue budgets, local preferences, and deduplicated notifications."""

import json
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from desktop.planning import MiningPlanner, NotificationTracker
from desktop.preferences import DesktopPreferences, StartupRegistration
from src.auth.recovery import SessionRecovery
from src.auth.session_bundle import SessionError
from src.services.inventory_service import InventoryService


@pytest.mark.parametrize(("code", "reason", "retry"), [
    ("CATALOG", "integrity", True), ("CATALOG", "catalog_shape", False),
    ("CATALOG", "service", True), ("SDK_TIMEOUT", "timeout", True),
    ("REQUEST", "connection", True), ("REQUEST", "tls", False),
    ("AUTH", "service", False), ("ACCOUNT_MISMATCH", "service", False),
    ("STALE", "timeout", False), ("FILE", "service", False),
])
def test_recovery_only_retries_recoverable_failures(code, reason, retry):
    assert SessionRecovery.retryable(SessionError(code, reason=reason)) is retry


def test_preferences_boolean_projection_and_atomic_save(tmp_path):
    path = tmp_path / "prefs.json"
    path.write_text(json.dumps({"notifications": False, "start_at_login": "yes", "other": True}))
    prefs = DesktopPreferences(path)
    assert not prefs.values["notifications"] and not prefs.values["start_at_login"]
    options = {**prefs.values, "automatic_queue": False}
    prefs.save(options)
    assert DesktopPreferences(path).values == options
    assert not path.with_suffix(".tmp").exists()
    with pytest.raises(ValueError):
        prefs.save({**options, "notifications": 1})


@pytest.mark.parametrize("failure", ["mkdir", "replace"])
def test_preferences_roll_back_startup_on_storage_failure(tmp_path, monkeypatch, failure):
    prefs = DesktopPreferences(tmp_path / "parent" / "prefs.json")
    original = dict(prefs.values)
    configure = Mock()
    monkeypatch.setattr(StartupRegistration, "configure", configure)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    if failure == "mkdir":
        prefs.path.parent.write_text("directory is blocked")
    else:
        monkeypatch.setattr("desktop.preferences.os.replace", Mock(side_effect=OSError("disk")))
    with pytest.raises(OSError):
        prefs.save({**original, "start_at_login": True})
    assert [call.args[0] for call in configure.call_args_list] == [True, False]
    assert prefs.values == original


def test_startup_is_explicit_and_packaged_only(tmp_path, monkeypatch):
    configure = Mock()
    monkeypatch.setattr(StartupRegistration, "configure", configure)
    monkeypatch.delattr(sys, "frozen", raising=False)
    prefs = DesktopPreferences(tmp_path / "prefs.json")
    prefs.save(dict(prefs.values))
    configure.assert_not_called()
    with pytest.raises(OSError, match="packaged"):
        prefs.save({**prefs.values, "start_at_login": True})
    configure.assert_not_called()


def test_startup_registration_uses_own_quoted_hkcu_value(tmp_path, monkeypatch):
    exe = tmp_path / "Miner app.exe"
    exe.touch()
    registry = SimpleNamespace(HKEY_CURRENT_USER=1, KEY_SET_VALUE=2, REG_SZ=3,
                               CreateKeyEx=Mock(), SetValueEx=Mock(), DeleteValue=Mock())
    registry.CreateKeyEx.return_value.__enter__ = Mock(return_value="owned-key")
    registry.CreateKeyEx.return_value.__exit__ = Mock(return_value=False)
    monkeypatch.setitem(sys.modules, "winreg", registry)
    monkeypatch.setattr(sys, "platform", "win32")
    StartupRegistration.configure(True, exe)
    registry.CreateKeyEx.assert_called_with(1, StartupRegistration.KEY, 0, 2)
    registry.SetValueEx.assert_called_once_with("owned-key", StartupRegistration.NAME, 0, 3, f'"{exe.resolve()}" --start-in-tray')
    StartupRegistration.configure(False)
    registry.DeleteValue.assert_called_once_with("owned-key", StartupRegistration.NAME)


def test_notification_baseline_claim_dedup_and_repeated_attention():
    tracker = NotificationTracker()
    old = {"id": "old", "drop_name": "Old", "game": "Game"}
    new = {"id": "new", "drop_name": "New", "game": "Game"}
    assert tracker.update({"history": [old]}) == []
    assert tracker.update({"history": [new, new, old]}) == [("Reward claimed", "New · Game")]
    assert tracker.update({"history": [new, old]}) == []
    failure = {"connection": {"phase": "attention", "code": "AUTH", "message": "Reconnect"}}
    assert len(tracker.update(failure)) == 1
    assert tracker.update(failure) == []
    tracker.update({"connection": {"phase": "ready"}})
    assert len(tracker.update(failure)) == 1


def planning_client():
    now = datetime(2026, 11, 6, tzinfo=timezone.utc)
    def drop(name, minutes, parents=()):
        return SimpleNamespace(id=name, name=name, remaining_minutes=minutes,
                               total_remaining_minutes=minutes + (20 if parents else 0),
                               precondition_drops=parents, is_claimed=False,
                               starts_at=now, ends_at=now + timedelta(hours=5), can_earn=lambda: not parents)
    first, second, third = drop("first", 20), drop("second", 30, ("first",)), drop("third", 10, ("first",))
    drops = {item.id: item for item in (first, second, third)}
    campaign = SimpleNamespace(id="c", name="Campaign", starts_at=now, ends_at=now + timedelta(hours=5), get_drop=drops.get)
    tree = [{"game_name": "Game", "campaigns": [{"id": "c", "drops": [{"id": "second"}, {"id": "third"}]}]}]
    return SimpleNamespace(gui=SimpleNamespace(get_wanted_game_tree=lambda: tree), inventory=[campaign],
                           desktop_deadline_queue=True, settings=SimpleNamespace(reward_priority=[])), now, drops


def test_forecast_includes_shared_prerequisite_once_and_waits_for_start():
    client, now, drops = planning_client()
    rows = MiningPlanner.build(client, now)
    assert [row["estimated_finish"] for row in rows] == [(now + timedelta(minutes=50)).isoformat(), (now + timedelta(minutes=60)).isoformat()]
    drops["third"].starts_at = now + timedelta(hours=6)
    rows = MiningPlanner.build(client, now)
    assert rows[0]["fits"] and not rows[1]["fits"]
    assert datetime.fromisoformat(rows[1]["estimated_finish"]) == now + timedelta(hours=6, minutes=10)
    assert rows[0]["chain_minutes"] == 50


def test_native_active_campaign_obeys_game_preference_then_deadline():
    now = datetime.now(timezone.utc)
    def campaign(game, deadline, minutes):
        return SimpleNamespace(game=game, ends_at=now + timedelta(hours=deadline), remaining_minutes=minutes, can_earn=lambda _: True)
    soon = campaign("preferred", 1, 40)
    later = campaign("preferred", 2, 5)
    fallback = campaign("fallback", .5, 1)
    excluded = campaign("excluded", .1, 0)
    client = SimpleNamespace(settings=SimpleNamespace(reward_priority=[]), inventory=[excluded, later, fallback, soon],
                             wanted_games=["preferred", "fallback"], desktop_deadline_queue=True,
                             watching_channel=SimpleNamespace(get_with_default=lambda _: object()))
    assert InventoryService(client).get_active_campaign() is soon
    client.wanted_games = ["fallback", "preferred"]
    assert InventoryService(client).get_active_campaign() is fallback


def test_native_queue_switches_to_earlier_deadline_channel_without_overriding_game_preferences():
    from src.services.channel_service import ChannelService
    from src.services.watch_service import WatchService
    from tests.test_priority_fallback import _campaign, _channel, _settings

    now = datetime.now(timezone.utc)
    settings = _settings("Preferred", "Fallback", priority_list_only=True)
    soon = _campaign("soon", "Preferred", settings=settings, acl=(100,), ends_at=now + timedelta(hours=1))
    later = _campaign("later", "Preferred", settings=settings, acl=(200,), ends_at=now + timedelta(hours=5))
    fallback = _campaign("fallback", "Fallback", game_id=2, settings=settings, acl=(300,), ends_at=now + timedelta(minutes=30))
    client = soon._twitch
    client.inventory = [later, soon, fallback]
    client.wanted_games = [soon.game, fallback.game]
    client.desktop_deadline_queue = True
    client._channel_service = ChannelService(client)
    channels = [_channel(client, identifier, {"id": str(game), "name": name})
                for identifier, game, name in ((100, 1, "Preferred"), (200, 1, "Preferred"), (300, 2, "Fallback"))]
    assert sorted(channels, key=client._channel_service.get_mining_priority) == channels
    client.watching_channel.get_with_default.return_value = channels[1]
    assert WatchService(client).should_switch(channels[0])
    client.watching_channel.get_with_default.return_value = channels[0]
    assert not WatchService(client).should_switch(channels[2])
    soon.can_earn = lambda _: False
    assert client._channel_service.get_mining_priority(channels[1]) < client._channel_service.get_mining_priority(channels[0])
