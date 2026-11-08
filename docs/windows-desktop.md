# Windows desktop edition

This Windows fork packages the miner and a native desktop interface into
`Twitch Drops Miner.exe` (desktop r9). Download the ZIP from this fork's
[Releases](https://github.com/Cavad/TwitchDropsMiner/releases), extract it and run the
executable from a permanent, writable folder.
Close any older miner instance first. Python and Docker are not needed to run it.

## Connect Twitch

1. Choose a sign-in browser and select **Connect Twitch**. Use Firefox if the Twitch
   verification screen does not finish in Chrome.
2. Complete Twitch authentication yourself in the separate browser window.
3. Select **Finish sign-in**, or close that sign-in window. The app automatically
   captures and verifies the session, then retrieves eligible campaigns. You do not
   need to visit the Twitch campaign page.

The Overview shows sign-in, verification, campaign loading, and ready states.
Transient issuance or campaign-integrity/service failures get up to three fresh
verification attempts. Each attempt still checks the account and campaign response;
a captured session alone is not treated as a successful connection. Permanent
identity, authorization, storage, and stale-operation errors are not retried.

When a saved session is available and can be renewed, **Retry saved session** performs
fresh verification without another interactive sign-in. Twitch can still reject a
session. An error code with a stage and reason identifies where verification failed;
retrying does not guarantee acceptance by Twitch.

## Automatic queue and estimates

The **Mining queue** uses the existing eligibility, account-link, benefit, and game
preference rules. Selected game priorities remain first; eligible fallback games
follow the miner's deadline order. Desktop automatic mode favors earlier-expiring
campaigns within a game. Existing explicit reward-priority and temporary game-order
rules retain precedence. The miner discovers campaigns and switches eligible live
channels automatically. No manual Twitch campaign browsing is required.

Use **Settings** to order games. Disable **Mine only games in this list** to permit
other eligible games after the selected games. An empty strict list can leave the
miner idle. **Prioritize campaigns nearing expiry** is enabled by default and can
be disabled under **Desktop behavior**.

Watch-time estimates include unclaimed prerequisites. Budgeted finish times allocate
each prerequisite once in the displayed queue. **May fit** means the continuous
watch-time budget finishes before the deadline; **At risk** means it does not.
Times use the PC's local timezone. These are sequential planning estimates:
pauses, mining schedules, offline streams, changing eligibility and Twitch delays
can extend them, while simultaneous campaign progress can shorten them.

## Tray, notifications and Windows startup

- The **Tray** button hides the window while the miner continues running. The tray
  menu opens the window, pauses/resumes mining, or quits and stops the miner.
- **Minimize and Close to tray** is off by default. When enabled, those actions keep
  the miner running. **Quit and stop mining** still shuts it down. If no system tray
  is available, the app stays accessible and closing stops the engine.
- Local notifications for newly claimed rewards and session issues are enabled by
  default. Existing history does not produce a burst of old notifications. Repeated
  snapshots of the same claim or session failure are deduplicated. Windows notification
  settings may suppress display.
- **Launch when I sign into Windows** is off by default and available in the EXE.
  Enabling it registers this executable for the current Windows user and launches it
  in the tray at sign-in. Save it in a permanent folder before enabling this option.
  Disable the option before moving or deleting the executable.
- Select **Save desktop options** to apply these options. Mining preferences use the
  separate **Save changes** action. Unsaved drafts are retained while hidden in the tray.

## Data and verification limits

Settings, history and session files remain under
`%LOCALAPPDATA%\TwitchDropsMinerDesktop\data`. Desktop preferences live in the parent
folder; logs live in its `logs` folder. Keep session files private.

The packaged smoke check uses temporary data and blank browser profiles. The local
interactive check covers browser handoff and native tray hide/restore. On hosted
GitHub runners, which have no interactive user desktop, `--verify-build report.json
--ci` checks owned blank-browser protocols and cleanup without trying to close a
manual sign-in window. Both modes check local settings, engine startup and shutdown.
The report identifies the browser mode. Neither mode authenticates to Twitch or
verifies live drop accrual. Native unit tests also cover Finish sign-in ownership.
Additional local blank-profile Firefox manual-handoff checks have encountered
browser-start and timeout failures. A passing hosted protocol check does not
establish that this interactive path is reliable on every Windows computer.
The executable is not code signed.

## Build on GitHub

The **Windows desktop EXE** Actions workflow runs on pushes to
`codex/windows-desktop`, or manually through **Run workflow**. It first runs the
full core regression suite on Linux, then native Qt/recovery/selection tests and
the EXE build on Windows x64 using Python 3.12. Core runtime dependencies come from
the unchanged `uv.lock`; desktop and packaging versions are pinned separately.

After a successful run, its **Twitch-Drops-Miner-Desktop-Windows-x64** artifact
contains the desktop ZIP and `SHA256SUMS`. The ZIP includes the EXE, usage guide,
license notices, build-verification report and source-commit/run provenance.
Downloading Actions artifacts requires a GitHub login; published release assets
can be downloaded normally. The workflow does not need Twitch credentials or
publisher secrets and does not log into Twitch.

## Watch progress and recovery

The overview shows the last time watch minutes increased in Twitch data since
connecting. The progress bar may also include locally estimated watch minutes.
After five minutes without confirmed progress on an eligible stream, the miner
refreshes the inventory. If progress remains unchanged for another three minutes
of eligible watching, it tries one alternate channel for the same reward, when
available. It preserves manual channel selections. If no alternate is available
or progress still does not advance after five more minutes, the overview and
optional tray notification flag the stall. Paused and scheduled-off time does
not count toward the watchdog.

When the miner is idle, the overview distinguishes campaign loading, an empty
strict Mining list, missing account links, and a lack of eligible live streams.
If Twitch session verification fails, **Copy diagnostics** copies fixed error
codes and status fields without copying session files, usernames, or raw logs.

## Overnight recap

Open **Activity** to see the current or most recent overnight window, from
22:00 to 08:00 in the PC's local time. The recap shows observed increases in
Twitch-confirmed minutes for the current reward, claims recorded by this miner,
time waiting for eligible live streams, and campaigns observed expiring with
unfinished rewards in the queue. Parallel reward progress is not added together.
Time when the app was closed, asleep or disconnected does not count as waiting.
Activity is saved locally per Twitch account and is collected from this desktop
version onward.

Use the date selector in **Activity** to revisit recorded nights from the last
seven local overnight windows, including the current or most recent night.
Existing r8 recap data is included if it falls within that period.

## Campaign troubleshooting

In **Campaigns**, select **Why am I not earning this?** for a reward-by-reward
check of the watch window, account link, prerequisites, mining rules, and
eligible streams currently tracked by the miner. A tracked eligible stream is
an opportunity to earn progress. Check **Now Mining** for the current reward.
