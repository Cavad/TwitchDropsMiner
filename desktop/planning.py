"""Queue presentation and explicitly optimistic reward-time forecasts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


class MiningPlanner:
    @classmethod
    def _chain(cls, campaign, drop, visiting=frozenset()):
        if drop.id in visiting or drop.is_claimed:
            return []
        chain = []
        for parent_id in sorted(drop.precondition_drops):
            parent = campaign.get_drop(parent_id)
            if parent is not None:
                chain.extend(cls._chain(campaign, parent, visiting | {drop.id}))
        chain.append(drop)
        return chain

    @staticmethod
    def duration(minutes: int) -> str:
        minutes = max(0, minutes)
        hours, remainder = divmod(minutes, 60)
        return f"{hours}h {remainder:02}m" if hours else f"{remainder}m"

    @staticmethod
    def build(client, now: datetime | None = None) -> list[dict]:
        now = now or datetime.now(timezone.utc)
        tree = client.gui.get_wanted_game_tree()
        by_id = {campaign.id: campaign for campaign in client.inventory}
        rows = []
        cursor = now
        planned = {}
        for game in tree:
            # Within a game, show earlier deadlines first; saved game order remains authoritative.
            campaigns = game["campaigns"]
            if getattr(client, "desktop_deadline_queue", False) and not getattr(client.settings, "reward_priority", []):
                campaigns = sorted(campaigns, key=lambda entry: by_id[entry["id"]].ends_at)
            for entry in campaigns:
                campaign = by_id[entry["id"]]
                for item in entry["drops"]:
                    drop = campaign.get_drop(item["id"])
                    if drop is None:
                        continue
                    chain_minutes = max(0, drop.total_remaining_minutes)
                    remaining = max(0, drop.remaining_minutes)
                    for required in MiningPlanner._chain(campaign, drop):
                        key = (campaign.id, required.id)
                        if key not in planned:
                            cursor = max(cursor, campaign.starts_at, required.starts_at)
                            cursor += timedelta(minutes=max(0, required.remaining_minutes))
                            planned[key] = cursor
                    eta = planned.get((campaign.id, drop.id), cursor)
                    rows.append({
                        "id": drop.id, "game": game["game_name"], "campaign": campaign.name,
                        "reward": drop.name, "remaining_minutes": remaining,
                        "chain_minutes": chain_minutes, "deadline": drop.ends_at.isoformat(),
                        "estimated_finish": eta.isoformat(), "fits": eta <= drop.ends_at,
                        "can_earn_now": drop.can_earn(),
                    })
        return rows


class NotificationTracker:
    def __init__(self):
        self.seen: set[str] | None = None
        self.attention = None
        self.stalled = False

    def update(self, data: dict) -> list[tuple[str, str]]:
        entries = data.get("history", [])
        current = {str(entry["id"]) for entry in entries if entry.get("id")}
        messages = []
        if self.seen is not None:
            for entry in entries:
                if entry.get("id") and str(entry["id"]) not in self.seen:
                    messages.append(("Reward claimed", f"{entry.get('drop_name', 'Reward')} · {entry.get('game', '')}"))
                    self.seen.add(str(entry["id"]))
            self.seen.update(current)
            if len(self.seen) > 3000:
                self.seen = current
        else:
            self.seen = current
        connection = data.get("connection", {})
        if connection.get("phase") == "attention":
            key = connection.get("code", "session")
            if key != self.attention:
                messages.append(("Twitch session needs attention", connection.get("message", "Open the miner to recover your connection.")))
                self.attention = key
        elif connection.get("phase") == "ready":
            self.attention = None
        state = data.get("mining_health", {}).get("state")
        if state == "stalled" and not self.stalled:
            messages.append(("Twitch watch progress stalled", "Open the miner to check the active reward and channel."))
            self.stalled = True
        elif state in ("signed_out", "watching", "switched"):
            self.stalled = False
        return messages
