"""Small presentation rules shared by the desktop UI and its regression tests."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse


def desktop_home() -> Path:
    override = os.environ.get("TDM_DESKTOP_HOME")
    if override:
        return Path(override).expanduser().resolve()
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "TwitchDropsMinerDesktop"


def normalize_games(text: str) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        name = line.strip()
        if name and name.casefold() not in seen:
            names.append(name)
            seen.add(name.casefold())
    return names


def campaign_matches(campaign: dict, query: str, category: str) -> bool:
    haystack = f"{campaign.get('name', '')} {campaign.get('game_name', '')}".casefold()
    if query.strip().casefold() not in haystack:
        return False
    return {
        "All campaigns": True,
        "Active": campaign.get("active", False),
        "Upcoming": campaign.get("upcoming", False),
        "Completed": campaign.get("finished", False),
    }.get(category, False)


def progress_percent(drop: dict | None) -> int:
    if not drop:
        return 0
    required = max(0, int(drop.get("required_minutes", 0)))
    current = max(0, int(drop.get("current_minutes", 0)))
    return min(100, int(100 * current / required)) if required else 0


def safe_link_url(url: object) -> str:
    """Return a Twitch-provided account-link URL only when it is a plain HTTPS address."""
    if not isinstance(url, str) or len(url) > 2048:
        return ""
    parsed = urlparse(url.strip())
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return ""
    return url.strip()


def game_link_status(campaigns: list[dict], game: str) -> tuple[str | None, str]:
    """Return ("linked" | "not_linked" | None, link URL) for a Mining list game.

    Linking belongs to the game account, so one linked campaign means linked.
    Badge and emote campaigns are mined without a link, so they never need one.
    Games without a current campaign have no known status.
    """
    key = game.casefold()
    current = [c for c in campaigns if str(c.get("game_name", "")).casefold() == key and not c.get("expired")]
    if not current:
        return None, ""
    if any(c.get("linked") for c in current):
        return "linked", ""
    needs_link = [
        c for c in current
        if not any(b.get("type") in ("BADGE", "EMOTE") for d in c.get("drops", []) for b in d.get("benefits", []))
    ]
    if not needs_link:
        return None, ""
    return "not_linked", next((url for c in needs_link if (url := safe_link_url(c.get("link_url")))), "")
