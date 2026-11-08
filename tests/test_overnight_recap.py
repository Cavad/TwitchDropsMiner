"""Behavioral coverage for local overnight accounting and storage."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from desktop.recap import OvernightRecap


@pytest.fixture
def setup(tmp_path):
    start = datetime(2026, 11, 7, 22).astimezone(timezone.utc)
    campaign = SimpleNamespace(id="campaign", name="Campaign", active=True,
                               starts_at=start, ends_at=start + timedelta(seconds=10),
                               mining_finished=False)
    drop = SimpleNamespace(id="drop", campaign=campaign, is_claimed=False, real_current_minutes=7)
    client = SimpleNamespace(inventory=[campaign], _drops={drop.id: drop})
    return start, client, drop, OvernightRecap(tmp_path)


def observe(recap, client, start, offset, *, account=1, state="watching", history=(), ready=True):
    return recap.sample(client, account=account, state=state, progress={"drop_id": "drop"},
                        queue=[{"id": "drop"}], history=history, ready=ready,
                        now=start + timedelta(seconds=offset), tick=offset)


def test_records_observed_activity_and_never_counts_optimistic_minutes(setup):
    start, client, drop, recap = setup
    observe(recap, client, start, 0)
    drop.extra_current_minutes = 20
    assert observe(recap, client, start, 2)["watch_minutes"] == 0
    drop.real_current_minutes = 8
    assert observe(recap, client, start, 4)["watch_minutes"] == 1
    drop.real_current_minutes = 7
    observe(recap, client, start, 6, state="no_live_channel")
    history = [{"claimed_at": (start + timedelta(seconds=7)).isoformat()}]
    report = observe(recap, client, start, 8, state="no_live_channel", history=history)
    assert report["waiting_ms"] == 2000
    assert report["claimed"] == 1
    drop.real_current_minutes = 8
    report = observe(recap, client, start, 10, history=history)
    assert report["watch_minutes"] == 1
    assert report["claimed"] == 1
    assert report["expired"] == ["Campaign"]


def test_completed_campaign_and_sleep_gap_are_not_reported_as_unfinished(setup):
    start, client, drop, recap = setup
    observe(recap, client, start, 0, state="no_live_channel")
    observe(recap, client, start, 8, state="no_live_channel")
    drop.campaign.mining_finished = True
    assert observe(recap, client, start, 10)["expired"] == []
    drop.real_current_minutes = 100
    report = observe(recap, client, start, 100)
    assert report["waiting_ms"] == 10_000
    assert report["watch_minutes"] == 0


def test_restart_and_account_switch_keep_reports_separate(setup, tmp_path):
    start, client, drop, recap = setup
    observe(recap, client, start, 0)
    drop.real_current_minutes += 1
    observe(recap, client, start, 2)
    recap.flush()
    restarted = OvernightRecap(tmp_path)
    assert observe(restarted, client, start, 4)["watch_minutes"] == 1
    assert observe(restarted, client, start, 6, account=2)["watch_minutes"] == 0
    assert observe(restarted, client, start, 8, account=None) == {}
    assert observe(restarted, client, start, 10)["watch_minutes"] == 1
    assert not list(tmp_path.glob("*.tmp"))


def test_recovers_from_corrupt_storage_and_rolls_over_at_local_22(setup, tmp_path):
    start, client, _, recap = setup
    (tmp_path / "overnight-recap-1.json").write_text("invalid JSON", encoding="utf-8")
    first = observe(recap, client, start, 0)
    morning = datetime(2026, 11, 8, 9).astimezone(timezone.utc)
    assert observe(recap, client, morning, 0)["start"] == first["start"]
    next_night = datetime(2026, 11, 8, 22).astimezone(timezone.utc)
    assert observe(recap, client, next_night, 0)["start"] == next_night.isoformat()


def test_gap_and_wall_clock_rollback_do_not_add_wait_or_duplicate_claims(setup):
    start, client, _, recap = setup
    observe(recap, client, start, 0, state="no_live_channel")
    history = [{"claimed_at": (start + timedelta(seconds=1)).isoformat()}]
    assert observe(recap, client, start, 2, history=history)["claimed"] == 1
    observe(recap, client, start, 0, state="no_live_channel", history=history)
    report = observe(recap, client, start, 30, history=history)
    assert report["claimed"] == 1
    assert report["waiting_ms"] == 2000
    assert report["expired"] == []


def test_counts_confirmed_progress_when_gui_moves_to_the_next_reward(setup):
    start, client, drop, recap = setup
    observe(recap, client, start, 0)
    drop.real_current_minutes += 1
    other = SimpleNamespace(id="other", is_claimed=False, real_current_minutes=25)
    client._drops[other.id] = other
    report = recap.sample(client, account=1, state="watching", progress={"drop_id": "other"},
                          queue=[], history=[], ready=True, now=start + timedelta(seconds=2), tick=2)
    assert report["watch_minutes"] == 1


def test_short_refresh_crossing_deadline_keeps_campaign_observation(setup):
    start, client, _, recap = setup
    observe(recap, client, start, 7)
    observe(recap, client, start, 9, ready=False, state="refreshing")
    observe(recap, client, start, 11, ready=False, state="refreshing")
    assert observe(recap, client, start, 13)["expired"] == ["Campaign"]
