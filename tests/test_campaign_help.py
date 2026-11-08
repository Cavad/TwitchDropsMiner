from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

from desktop.campaign_help import explain_campaign


def setup_campaign():
    now = datetime.now(timezone.utc)
    game = SimpleNamespace(is_special=lambda: False)
    drop = SimpleNamespace(name="Reward", is_claimed=False, is_watch_drop=True, can_claim=False,
                           starts_at=now - timedelta(hours=1), ends_at=now + timedelta(hours=1),
                           is_mineable=True, preconditions_met=True, precondition_drops=[],
                           can_earn=Mock(return_value=True))
    campaign = SimpleNamespace(id="campaign", name="Campaign", game=game, drops=[drop],
                               expired=False, upcoming=False, eligible=True, get_drop=Mock())
    client = SimpleNamespace(
        _auth_state=SimpleNamespace(_logged_in=SimpleNamespace(is_set=lambda: True)),
        _inventory_loaded=True, _inventory_refresh_pending=False, _games_update_pending=False, _state=SimpleNamespace(name="IDLE"),
        inventory=[campaign], wanted_games=[game], is_mining_time=lambda: True,
        watching_channel=SimpleNamespace(get_with_default=Mock(return_value=None)), channels={},
    )
    return client, campaign, drop


def test_campaign_help_distinguishes_unlinked_and_prerequisites():
    client, campaign, drop = setup_campaign()
    campaign.eligible = False
    assert "Link the game account" in explain_campaign(client, campaign.id)
    campaign.eligible = True
    drop.preconditions_met = False
    drop.precondition_drops = ["prior"]
    campaign.get_drop.return_value = SimpleNamespace(name="Earlier reward", is_claimed=False)
    assert "Claim these prerequisites first: Earlier reward" in explain_campaign(client, campaign.id)


def test_campaign_help_distinguishes_current_other_and_banned_streams():
    client, campaign, drop = setup_campaign()
    stream = SimpleNamespace(online=True, banned=False, drops_enabled=True)
    client.channels = {1: stream}
    assert "miner is not watching it" in explain_campaign(client, campaign.id)
    client.watching_channel.get_with_default.return_value = stream
    assert "current stream is eligible" in explain_campaign(client, campaign.id)
    stream.banned = True
    assert "No eligible live stream" in explain_campaign(client, campaign.id)
    stream.banned = False
    drop.can_earn.side_effect = lambda channel=None: channel is None
    assert "No eligible live stream" in explain_campaign(client, campaign.id)


def test_campaign_help_prefers_claimable_status_and_guards_loading_and_missing():
    client, campaign, drop = setup_campaign()
    campaign.expired = True
    drop.can_claim = True
    assert "Ready to claim" in explain_campaign(client, campaign.id)
    client._inventory_refresh_pending = True
    assert "loading" in explain_campaign(client, campaign.id)
    client._inventory_refresh_pending = False
    assert "no longer in the current inventory" in explain_campaign(client, "gone")



def test_campaign_help_does_not_report_excluded_during_policy_update():
    client, campaign, _ = setup_campaign()
    client.wanted_games = []
    client._state.name = "GAMES_UPDATE"
    assert "applying campaign and mining rules" in explain_campaign(client, campaign.id)
    client._state.name = "IDLE"
    assert "exclude this game" in explain_campaign(client, campaign.id)
