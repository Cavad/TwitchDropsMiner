"""Watchdog for the desktop miner, driven by Twitch-confirmed watch minutes."""

from __future__ import annotations

from datetime import datetime, timezone
from time import monotonic


class MiningHealth:
    REFRESH_AFTER = 300
    SWITCH_AFTER = 180
    ALERT_AFTER = 300

    def __init__(self):
        self.account = None
        self.target = None
        self.minutes = 0
        self.channel = None
        self.since = None
        self.confirmed_at = None
        self.stage = "watching"

    def update(self, client, *, logged_in, ready, progress, queue):
        if not logged_in:
            self.__init__()
            return {"state": "signed_out"}

        account = getattr(client._auth_state, "user_id", None)
        if account != self.account:
            self.__init__()
            self.account = account

        if not client.is_mining_time():
            self.since = None
            state = "paused" if client.pause_info()["paused"] else "scheduled"
            return self._status(state)
        if not ready or client._games_update_pending:
            self.since = None
            return self._status("refreshing" if self.stage == "refreshing" else "loading")

        channel = client.watching_channel.get_with_default(None)
        if channel is None or not client.can_watch(channel):
            self.since = None
            return self._status(self._idle_reason(client, queue))

        now = monotonic()
        if self.target is not None:
            previous = client._drops.get(self.target[1])
            if previous is not None and previous.campaign.id == self.target[0]:
                minutes = previous.real_current_minutes
                if minutes > self.minutes:
                    self.confirmed_at = datetime.now(timezone.utc).isoformat()
                    self.since, self.stage = now, "watching"
                self.minutes = minutes

        drop = client._drops.get((progress or {}).get("drop_id"))
        if (drop is None or drop.campaign.game not in client.wanted_games
                or not self._drop_can_progress(drop, channel)):
            drop = next((
                candidate for campaign in client.inventory
                if campaign.game in client.wanted_games
                and (candidate := campaign.first_drop) is not None
                and self._drop_can_progress(candidate, channel)
            ), None)
            if drop is None:
                self.since = None
                return self._status("acquiring", channel=channel)

        target = (drop.campaign.id, drop.id)
        if target != self.target:
            self.target, self.minutes = target, drop.real_current_minutes
            self.since, self.stage = now, "watching"

        if self.since is None:
            self.since = now
        broadcast = self._broadcast(channel)
        if broadcast != self.channel:
            self.channel = broadcast
            self.since = now
        elapsed = now - self.since

        if self.stage == "watching" and elapsed >= self.REFRESH_AFTER:
            if client.request_inventory_refresh():
                self.stage, self.since = "refreshing", now
        elif self.stage == "refreshing" and elapsed >= self.SWITCH_AFTER:
            alternate = None
            if not client.is_manual_mode() and not client.gui.has_pending_channel_selection():
                alternate = min(
                    (candidate for candidate in client.channels.values()
                     if candidate.id != channel.id
                     and client.can_watch(candidate) and self._drop_can_progress(drop, candidate)),
                    key=client._channel_service.get_mining_priority, default=None,
                )
            if alternate is not None:
                client.watch(alternate)
                client.restart_watching()
                self.channel = self._broadcast(alternate)
                self.stage, self.since = "switched", now
                channel = alternate
            else:
                self.stage = "stalled"
        elif self.stage == "switched" and elapsed >= self.ALERT_AFTER:
            self.stage = "stalled"

        return self._status(self.stage, channel=channel, client=client)

    @staticmethod
    def _drop_can_progress(drop, channel):
        return (channel.drops_enabled or drop.campaign.game.is_special()) and drop.can_earn(channel)

    @staticmethod
    def _broadcast(channel):
        return channel.id, getattr(channel._stream, "broadcast_id", None), channel.game

    def _status(self, state, *, channel=None, client=None):
        result = {"state": state, "confirmed_at": self.confirmed_at}
        if channel is not None:
            result["channel"] = channel.name
        if client is not None:
            result["selection"] = (
                "manual" if client.is_manual_mode() or client.gui.has_pending_channel_selection()
                else "automatic"
            )
        return result

    @staticmethod
    def _idle_reason(client, queue):
        settings = client.settings
        selected = {name.casefold() for name in settings.games_to_watch}
        if settings.priority_list_only and not selected:
            return "empty_list"
        if any(row["can_earn_now"] for row in queue):
            if any(client.can_watch(channel) for channel in client.channels.values()):
                return "selecting"
            return "no_live_channel"
        if queue:
            return "waiting_reward"
        now = datetime.now(timezone.utc)
        if any(campaign.active and not campaign.eligible
               and (not settings.priority_list_only or campaign.game.name.casefold() in selected)
               and any(drop.ends_at > now for drop in campaign.mineable_watch_drops)
               for campaign in client.inventory):
            return "link_account"
        return "no_rewards"
