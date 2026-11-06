"""Small presentation rules shared by the desktop UI and its regression tests."""

from __future__ import annotations

import os
from pathlib import Path


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
