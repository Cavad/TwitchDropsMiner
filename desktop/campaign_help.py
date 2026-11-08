"""Read-only explanation of the miner's current campaign eligibility."""

from datetime import datetime, timezone


def explain_campaign(client, campaign_id):
    if not client._auth_state._logged_in.is_set():
        return "Connect Twitch before checking campaign eligibility."
    if not client._inventory_loaded or client._inventory_refresh_pending or client._state.name == "INVENTORY_FETCH":
        return "Campaign data is loading. Check again after the refresh finishes."
    campaign = next((entry for entry in client.inventory if entry.id == campaign_id), None)
    if campaign is None:
        return "This campaign is no longer in the current inventory. Refresh campaigns to update the list."

    now = datetime.now(timezone.utc)
    current = client.watching_channel.get_with_default(None)
    wanted = campaign.game in client.wanted_games
    mining = client.is_mining_time()
    updating_rules = client._games_update_pending or client._state.name == "GAMES_UPDATE"
    special = campaign.game.is_special()

    def supports(drop, channel):
        return channel is not None and channel.online and not channel.banned and (
            special or channel.drops_enabled
        ) and drop.can_earn(channel)

    lines = [" ".join(campaign.name.splitlines())]
    for drop in campaign.drops:
        if drop.is_claimed:
            reason = "Already claimed."
        elif not drop.is_watch_drop:
            reason = "This reward requires an action other than watching."
        elif drop.can_claim:
            reason = "Ready to claim. Check Twitch Drops Inventory if it stays here."
        elif campaign.expired or drop.ends_at <= now:
            reason = "The watch window has ended."
        elif campaign.upcoming or drop.starts_at > now:
            reason = "The watch window has not started yet."
        elif not campaign.eligible:
            reason = "Link the game account through Twitch Drops Inventory."
        elif not drop.is_mineable:
            reason = "Excluded by the miner's current reward filters or prerequisites."
        elif not drop.preconditions_met:
            parents = [parent.name for key in drop.precondition_drops
                       if (parent := campaign.get_drop(key)) is not None and not parent.is_claimed]
            reason = ("Claim these prerequisites first: " + ", ".join(parents)
                      if parents else "An earlier reward must be claimed first.")
        elif not mining:
            reason = ("Mining is paused. Select Resume mining." if client.pause_info()["paused"]
                      else "Mining is outside its scheduled hours.")
        elif updating_rules:
            reason = "The miner is applying campaign and mining rules. Check again in a moment."
        elif not wanted:
            reason = "The current mining rules exclude this game. Check the Mining list and Settings."
        elif not drop.can_earn():
            reason = "Twitch progress needs to be refreshed. Select Refresh and check again."
        elif supports(drop, current):
            reason = "The current stream is eligible. Check Now Mining for the reward Twitch is tracking."
        elif any(supports(drop, channel) for channel in client.channels.values()):
            reason = "An eligible live stream is tracked, but the miner is not watching it. Check the mining queue and game priorities."
        else:
            reason = "No eligible live stream is currently tracked for this reward."
        lines.append(" ".join(f"{drop.name}: {reason}".splitlines()))
    if len(lines) == 1:
        lines.append("Twitch lists no rewards for this campaign.")
    return "\n\n".join(lines)
