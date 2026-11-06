# Windows desktop edition

This local desktop edition adds a native Qt interface to the existing miner. Its
interface is in English; the mining engine retains the existing locale system.
The upstream project's Docker dashboard and its support scope are unchanged.

## Run

Double-click `dist/Twitch Drops Miner.exe`. Python and Docker are bundled or
unnecessary at runtime. Install Chrome or Chromium for renewal; Chrome, Chromium or
Firefox can be used for sign-in.

Choose **Connect Twitch**, complete sign-in and Twitch verification in the separate
browser, then choose **Finish sign-in** in the app. This asks only the owned sign-in
window to close normally. Campaign discovery and session validation then run in the
background; no campaign page needs to be browsed or clicked. Manually closing that
sign-in window still works. Passwords and verification codes are entered only at Twitch.
If sign-in fails, the app shows the helper's existing error guidance and allows retry. Cancel waits for owned-browser cleanup before reenabling sign-in. A five-minute timeout prevents an unbounded wait. Windows profile cleanup retries transient file locks off the miner loop, for at most 7.75 seconds of retry delays. The overview scrolls vertically when long error messages or narrow windows need more room.

Set your game priorities in **Settings**, then choose **Save changes**. Drag to reorder
or use the move buttons. Reward preferences and the refresh interval are also editable.
**Campaigns** shows actual reward progress. **History** exports the full local claim
history as Excel-compatible UTF-8 CSV. **Activity** shows recent engine messages.

Keep the PC awake while mining. Tray mode keeps the miner running with its window
hidden. Closing stops mining unless **Minimize and Close to tray** is enabled;
**Quit and stop mining** always shuts it down. Only one desktop instance can use a
data directory. See the [desktop guide](../docs/windows-desktop.md) for queue forecasts,
notifications and optional Windows startup.

Data lives in `%LOCALAPPDATA%/TwitchDropsMinerDesktop/data`; logs are in the sibling
`logs` directory. The packaged executable never persists credentials in its temporary
extraction directory. The existing source checkout's data is kept separately.

## Build and verify

From the project's activated `env/`, after installing the locked core dependencies:

```powershell
python -m pip install -r packaging/desktop-requirements.txt -r packaging/login-helper-requirements.txt
python -m pytest tests/test_desktop.py
python -m ruff check src/ desktop/ desktop_main.py tests/test_desktop.py
python -m PyInstaller --noconfirm --clean packaging/desktop.spec
& '.\dist\Twitch Drops Miner.exe' --verify-build C:\path\to\verification.json
```

The packaged smoke mode uses temporary data and blank browser pages. It checks the
native browser's launch and cleanup, renewal browser protocol, engine startup, a saved
settings roundtrip, and graceful shutdown. It does not log into Twitch or claim drops.
Run it with a working directory outside the source checkout to test resource bundling.

The miner runs in a QThread with its own asyncio loop. GUI actions are queued into
that loop. The existing helper protocol uses a listener reserved on an ephemeral
127.0.0.1 port; no LAN listener or browser control port is published by this edition.
GUI snapshots contain public session state and the existing masked settings projection.
A save revision counter preserves edits made while an earlier save is in flight.

The desktop uses a normal, hidden Windows browser for fresh SDK issuance rather than
the headless mode used by the default source runner. Capture windows are hidden only
after the owned browser has been verified and the manual sign-in window has closed.
Window ownership is checked by live PID; Firefox also validates its launcher child and
executable. Background window workers drain before process cleanup. Default Linux,
macOS and standalone-helper behavior is unchanged. The normal miner loop fetches
campaign data automatically after validation; the desktop remains on Overview.

Fresh issuance, account/catalog validation, and atomic persistence are still mandatory.
Twitch can reject the freshly issued session even after the manual browser signs in.
Local smoke checks do not establish live Twitch acceptance.

The app's original code retains the repository MIT license. Qt for Python is provided
by PySide6; see its bundled licenses and the Qt for Python licensing documentation:
https://doc.qt.io/qtforpython-6/licenses.html
