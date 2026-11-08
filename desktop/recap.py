"""Local overnight activity summaries for the desktop miner."""

from __future__ import annotations

import json
import logging
import os
from contextlib import suppress
from datetime import datetime, time, timedelta, timezone
from time import monotonic
from typing import NamedTuple

from desktop.model import desktop_home


logger = logging.getLogger("TwitchDrops.desktop")


class CampaignEnd(NamedTuple):
    deadline: datetime
    name: str


class OvernightRecap:
    """Summarize 22:00 to 08:00 local time using observed activity only."""

    SAMPLE_GAP = 8
    SAVE_INTERVAL = 60
    MAX_CAMPAIGNS = 200

    def __init__(self, root=None):
        self.root = root or desktop_home()
        self.account = None
        self.path = None
        self.report = {}
        self.previous = None
        self.watched = {}
        self.previous_drop = None
        self.claim_watermark = None
        self.campaigns = {}
        self.dirty = False
        self.last_save = monotonic()

    @staticmethod
    def window(now):
        local = now.astimezone()
        night = local.date() if local.hour >= 22 else local.date() - timedelta(days=1)
        start = datetime.combine(night, time(22)).astimezone(timezone.utc)
        end = datetime.combine(night + timedelta(days=1), time(8)).astimezone(timezone.utc)
        return start, end

    def _account_changed(self, account):
        self.flush()
        self.account = account
        self.path = self.root / f"overnight-recap-{account}.json" if account is not None else None
        self.report = {}
        self.previous = None
        self.watched.clear()
        self.previous_drop = None
        self.claim_watermark = None
        self.campaigns.clear()
        self.dirty = False
        if self.path is None:
            return
        try:
            if self.path.stat().st_size > 256_000:
                return
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if (isinstance(raw, dict) and isinstance(raw.get("start"), str)
                    and all(type(raw.get(key)) is int and raw[key] >= 0
                            for key in ("watch_minutes", "claimed", "waiting_ms"))
                    and type(raw.get("observed")) is bool
                    and isinstance(raw.get("expired"), dict)
                    and len(raw["expired"]) <= self.MAX_CAMPAIGNS
                    and all(isinstance(name, str) for name in raw["expired"].values())):
                self.report = {key: raw[key] for key in ("start", "watch_minutes", "claimed", "waiting_ms", "expired", "observed")}
        except (OSError, ValueError, RecursionError):
            pass

    def sample(self, client, *, account, state, progress, queue, history, ready, now=None, tick=None):
        account = account if type(account) is int and account > 0 else None
        if account != self.account:
            self._account_changed(account)
        if account is None:
            return {}

        now = now or datetime.now(timezone.utc)
        tick = monotonic() if tick is None else tick
        start, end = self.window(now)
        key = start.isoformat()
        previous = self.previous
        self.previous = (now, tick, state)
        if self.report.get("start") != key:
            self.flush()
            self.report = {"start": key, "watch_minutes": 0, "claimed": 0, "waiting_ms": 0, "expired": {}, "observed": False}
            self.watched.clear()
            self.previous_drop = None
            self.campaigns.clear()

        def in_window(stamp):
            return start <= stamp < end

        continuous = False
        if previous is not None:
            prior_time, prior_tick, prior_state = previous
            elapsed = tick - prior_tick
            continuous = 0 <= elapsed <= self.SAMPLE_GAP and 0 <= (now - prior_time).total_seconds() <= self.SAMPLE_GAP
            if continuous and prior_state == "no_live_channel":
                seconds = (min(now, end) - max(prior_time, start)).total_seconds()
                self._increment("waiting_ms", round(min(elapsed, max(0, seconds)) * 1000))
            since = self.claim_watermark or prior_time
            if since < end and now >= start:
                for entry in history:
                    try:
                        claimed_at = datetime.fromisoformat(entry["claimed_at"])
                        if since < claimed_at <= now and in_window(claimed_at):
                            self._increment("claimed", 1)
                    except (KeyError, TypeError, ValueError):
                        continue
            if continuous and ready:
                due = {campaign_id: observation for campaign_id, observation in self.campaigns.items()
                       if 0 <= (now - observation.deadline).total_seconds() <= 60
                       and in_window(observation.deadline)}
                if due:
                    finished = {campaign.id for campaign in client.inventory
                                if campaign.id in due and campaign.mining_finished}
                    expired = self.report["expired"]
                    for campaign_id, observation in due.items():
                        if (len(expired) < self.MAX_CAMPAIGNS and campaign_id not in finished
                                and campaign_id not in expired):
                            expired[campaign_id] = observation.name
                            self.dirty = True
        self.claim_watermark = max(self.claim_watermark or now, now)

        if ready and in_window(now):
            if state in ("watching", "refreshing", "switched", "stalled"):
                self._sample_watch(client, progress, continuous)
            else:
                self.previous_drop = None
            self._sample_campaigns(client, queue, now)
        else:
            self.previous_drop = None
            if not continuous or not in_window(now) or state not in ("loading", "refreshing"):
                self.campaigns.clear()

        if in_window(now) and ready and not self.report["observed"]:
            self.report["observed"] = True
            self.dirty = True
        if self.dirty and tick - self.last_save >= self.SAVE_INTERVAL:
            self.flush()
        return {**self.report, "end": end.isoformat(), "expired": sorted(self.report["expired"].values())}

    def _sample_watch(self, client, progress, continuous):
        if continuous and self.previous_drop is not None:
            prior = client._drops.get(self.previous_drop)
            if prior is not None and not prior.is_claimed:
                minutes = prior.real_current_minutes
                previous = self.watched[prior.id]
                self._increment("watch_minutes", max(0, minutes - previous))
                self.watched[prior.id] = max(previous, minutes)

        drop = client._drops.get((progress or {}).get("drop_id"))
        if drop is None or drop.is_claimed:
            self.previous_drop = None
            return
        minutes = drop.real_current_minutes
        self.watched[drop.id] = max(self.watched.get(drop.id, minutes), minutes)
        self.previous_drop = drop.id

    def _sample_campaigns(self, client, queue, now):
        self.campaigns = {}
        for row in queue:
            drop = client._drops.get(row["id"])
            if drop is None or drop.is_claimed:
                continue
            campaign = drop.campaign
            if campaign.active and campaign.starts_at <= now < campaign.ends_at:
                self.campaigns[campaign.id] = CampaignEnd(campaign.ends_at, campaign.name[:256])

    def _increment(self, key, amount):
        if amount:
            self.report[key] += amount
            self.report["observed"] = True
            self.dirty = True

    def flush(self):
        if not self.dirty or self.path is None:
            return
        self.last_save = monotonic()
        temporary = self.path.with_suffix(".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(json.dumps(self.report), encoding="utf-8")
            os.replace(temporary, self.path)
        except OSError:
            logger.warning("Could not save the overnight recap")
            with suppress(OSError):
                temporary.unlink(missing_ok=True)
        else:
            self.dirty = False
