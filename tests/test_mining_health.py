"""Regression tests for the desktop-only watch watchdog."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from desktop.mining_health import MiningHealth
from desktop.planning import NotificationTracker


@pytest.fixture
def miner(monkeypatch):
    clock = SimpleNamespace(now=0)
    monkeypatch.setattr("desktop.mining_health.monotonic", lambda: clock.now)
    game = SimpleNamespace(name="Example game", is_special=lambda: False)
    channel = SimpleNamespace(id=1, name="First stream", game=game, drops_enabled=True, _stream=SimpleNamespace(broadcast_id=1))
    alternate = SimpleNamespace(id=2, name="Second stream", game=game, drops_enabled=True, _stream=SimpleNamespace(broadcast_id=1))
    campaign = SimpleNamespace(id="campaign", game=game)
    drop = SimpleNamespace(id="drop", campaign=campaign, real_current_minutes=0,
                           extra_current_minutes=0, can_earn=Mock(return_value=True))
    campaign.first_drop = drop
    client = SimpleNamespace(
        _auth_state=SimpleNamespace(user_id=1), _games_update_pending=False,
        _drops={drop.id: drop}, wanted_games=[game], inventory=[],
        watching_channel=SimpleNamespace(get_with_default=Mock(return_value=channel)),
        channels={1: channel, 2: alternate}, can_watch=Mock(return_value=True),
        get_active_campaign=Mock(return_value=campaign),
        is_mining_time=Mock(return_value=True), pause_info=Mock(return_value={"paused": True}),
        is_manual_mode=Mock(return_value=False), request_inventory_refresh=Mock(return_value=True),
        gui=SimpleNamespace(has_pending_channel_selection=Mock(return_value=False)),
        _channel_service=SimpleNamespace(get_mining_priority=lambda channel: channel.id),
        watch=Mock(), restart_watching=Mock(),
        settings=SimpleNamespace(games_to_watch=["Example game"], priority_list_only=True),
    )
    client.watch.side_effect = lambda candidate: setattr(client.watching_channel.get_with_default, "return_value", candidate)
    return clock, client, drop, alternate


def sample(health, client, *, ready=True, logged_in=True, queue=()):
    return health.update(client, ready=ready, logged_in=logged_in,
                         progress={"drop_id": "drop"}, queue=queue)


def test_only_confirmed_progress_resets_watchdog_and_then_recovers(miner):
    clock, client, drop, alternate = miner
    health = MiningHealth()
    assert sample(health, client)["confirmed_at"] is None
    drop.extra_current_minutes = 4
    clock.now = 299
    assert sample(health, client)["state"] == "watching"
    drop.real_current_minutes = 1
    assert sample(health, client)["confirmed_at"]
    clock.now += 300
    assert sample(health, client)["state"] == "refreshing"
    client.request_inventory_refresh.assert_called_once()
    clock.now += 600
    assert sample(health, client, ready=False)["state"] == "refreshing"
    assert sample(health, client)["state"] == "refreshing"
    clock.now += 180
    assert sample(health, client)["state"] == "switched"
    client.watch.assert_called_once_with(alternate)
    client.restart_watching.assert_called_once()
    clock.now += 300
    stalled = sample(health, client)
    assert stalled["state"] == "stalled"
    tracker = NotificationTracker()
    assert len(tracker.update({"mining_health": stalled})) == 1
    assert tracker.update({"mining_health": stalled}) == []
    drop.real_current_minutes = 2
    assert sample(health, client)["state"] == "watching"


@pytest.mark.parametrize("manual", [False, True])
def test_switch_respects_reward_eligibility_and_manual_selection(miner, manual):
    clock, client, drop, alternate = miner
    client.is_manual_mode.return_value = manual
    if not manual:
        drop.can_earn.side_effect = lambda channel: channel.id != alternate.id
    health = MiningHealth()
    sample(health, client)
    clock.now = 300
    sample(health, client)
    clock.now = 480
    assert sample(health, client)["state"] == "stalled"
    client.watch.assert_not_called()


def test_pause_and_identity_change_do_not_carry_old_progress(miner):
    clock, client, drop, _ = miner
    health = MiningHealth()
    sample(health, client)
    drop.real_current_minutes = 1
    assert sample(health, client)["confirmed_at"]
    clock.now = 299
    client.is_mining_time.return_value = False
    assert sample(health, client)["state"] == "paused"
    clock.now = 3000
    client.is_mining_time.return_value = True
    assert sample(health, client)["state"] == "watching"
    client.request_inventory_refresh.assert_not_called()
    client._auth_state.user_id = 2
    assert sample(health, client)["confirmed_at"] is None


def test_idle_explains_no_channels_and_empty_strict_list(miner):
    _, client, _, _ = miner
    health = MiningHealth()
    client.watching_channel.get_with_default.return_value = None
    client.can_watch.return_value = False
    assert sample(health, client, queue=[{"can_earn_now": True}])["state"] == "no_live_channel"
    client.settings.games_to_watch = []
    assert sample(health, client, queue=[{"can_earn_now": True}])["state"] == "empty_list"


def test_pending_channel_selection_prevents_automatic_switch(miner):
    clock, client, _, _ = miner
    health = MiningHealth()
    sample(health, client)
    clock.now = 300
    sample(health, client)
    client.gui.has_pending_channel_selection.return_value = True
    clock.now = 480
    assert sample(health, client)["selection"] == "manual"
    client.watch.assert_not_called()


def test_same_reward_can_use_eligible_alternate_category(miner):
    clock, client, drop, alternate = miner
    drop.campaign.game.is_special = lambda: True
    alternate.game = SimpleNamespace(name="Different streamed category")
    alternate.drops_enabled = False
    health = MiningHealth()
    sample(health, client)
    clock.now = 300
    sample(health, client)
    clock.now = 480
    assert sample(health, client)["state"] == "switched"
    client.watch.assert_called_once_with(alternate)


def test_confirmation_survives_rollover_to_next_reward(miner):
    _, client, drop, _ = miner
    health = MiningHealth()
    sample(health, client)
    drop.real_current_minutes = 5
    next_drop = SimpleNamespace(id="next", campaign=drop.campaign, real_current_minutes=0,
                                can_earn=Mock(return_value=True))
    client._drops[next_drop.id] = next_drop
    assert health.update(client, logged_in=True, ready=True, progress={"drop_id": "next"},
                         queue=[])["confirmed_at"]


def test_new_broadcast_on_same_channel_gets_fresh_grace_period(miner):
    clock, client, _, _ = miner
    health = MiningHealth()
    sample(health, client)
    clock.now = 300
    client.channels[1]._stream.broadcast_id += 1
    assert sample(health, client)["state"] == "watching"
    client.request_inventory_refresh.assert_not_called()
