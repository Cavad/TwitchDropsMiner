"""Run the existing asyncio miner away from the native Qt event loop."""

from __future__ import annotations

import asyncio
import copy
import logging
import socket
import sys
from contextlib import suppress
from typing import Any, cast

from PySide6.QtCore import QThread, Signal

from desktop.mining_health import MiningHealth
from desktop.planning import MiningPlanner
from desktop.preferences import DesktopPreferences
from desktop.recap import OvernightRecap


class MinerEngine(QThread):
    LOGIN_TIMEOUT_SECONDS = 300
    snapshot = Signal(dict)
    ready = Signal()
    notice = Signal(str)
    fatal = Signal(str)
    login_phase = Signal(str)
    login_finished = Signal(bool, str)
    command_finished = Signal(str, bool, str)
    exported = Signal(str)
    connection_changed = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.loop = None
        self.client: Any = None
        self.port = 0
        self.stopping = False
        self.login_task = None
        self.jobs = set()
        self.active_login_browser = None
        self.preferences = DesktopPreferences()
        self.connection: dict[str, Any] = {"phase": "starting", "message": "Starting the local miner…", "code": ""}
        self.recovering = False
        self.mining_health = MiningHealth()
        self.overnight_recap = OvernightRecap()
        self.connection_error = None

    def _set_connection(self, phase, message, diagnostic=None, attempt=0):
        self.connection = {"phase": phase, "message": message, "attempt": attempt,
                           "code": diagnostic.code if diagnostic else "",
                           "diagnostic": diagnostic.to_dict() if diagnostic else None}
        self.connection_changed.emit(dict(self.connection))

    def _session_progress(self, phase, diagnostic, attempt):
        if phase == "validated":
            self.connection_error = None
            self._set_connection("loading", "Session verified. Loading campaign data…")
        elif phase == "retrying":
            self._set_connection("recovering", "Retrying fresh session verification without another sign-in…", diagnostic, attempt)
        elif phase in ("server_issuance", "issued_validation", "renewal_issuance", "renewal_validation", "captured_validation"):
            self._set_connection("verifying", "Verifying account and campaign access…")
        elif phase == "failed":
            self.connection_error = diagnostic

    def _report_login(self, phase):
        if phase in ("login", "chromium_login", "firefox_login"):
            self._set_connection("signing_in", "Complete Twitch sign-in, then choose Finish sign-in.")
        elif phase in ("capturing", "sending"):
            self._set_connection("verifying", "Verifying the session and campaign access automatically…")
        self.login_phase.emit(phase)

    def run(self):
        try:
            asyncio.run(self._serve())
        except Exception:
            logging.getLogger("TwitchDrops.desktop").exception("Desktop engine failed")
            self.fatal.emit("The miner could not start. Check the local log, then restart the app.")
        finally:
            self.loop = None

    async def _serve(self):
        import truststore
        import uvicorn

        from src.config.settings import Settings
        from src.core.client import Twitch
        from src.i18n import _
        from src.web import app as webapp
        from src.web.gui_manager import WebGUIManager

        truststore.inject_into_ssl()
        self.loop = asyncio.get_running_loop()
        settings = Settings()
        _.set_language(settings.language or "English")
        self.client = Twitch(settings)
        cast(Any, self.client).desktop_deadline_queue = self.preferences.values["automatic_queue"]
        self.client.session_controller.on_progress = self._session_progress
        if sys.platform == "win32":
            # Use a normal owned browser for SDK verification, kept out of view.
            # Fresh proofs still pass the same account and campaign validation.
            cast(Any, self.client.session_controller.issuer.browser).background = True
        self.client.gui = WebGUIManager(self.client)
        webapp.set_managers(self.client.gui, self.client)
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        listener.bind(("127.0.0.1", 0))
        self.port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(
            webapp.socket_app, host="127.0.0.1", port=self.port,
            log_level="warning", access_log=False, log_config=None,
        ))
        server_task = asyncio.create_task(server.serve(sockets=[listener]))
        miner_task = None
        ticker = None
        try:
            async with asyncio.timeout(20):
                while not server.started:
                    if server_task.done():
                        await server_task
                        raise RuntimeError("Local service did not start")
                    await asyncio.sleep(.05)
            miner_task = asyncio.create_task(self.client.run())
            ticker = asyncio.create_task(self._publish_loop())
            self.ready.emit()
            if self.stopping:
                self.client.close()
            done, _pending = await asyncio.wait(
                (server_task, miner_task), return_when=asyncio.FIRST_COMPLETED,
            )
            for task in done:
                await task
            if not self.stopping:
                self.fatal.emit("The miner stopped. Close and reopen the app to reconnect.")
        finally:
            self.stopping = True
            tasks = [task for task in (self.login_task, ticker, *self.jobs) if task]
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            self.client.close()
            if miner_task:
                try:
                    await asyncio.wait_for(asyncio.shield(miner_task), 30)
                except (TimeoutError, Exception):
                    miner_task.cancel()
                    await asyncio.gather(miner_task, return_exceptions=True)
            server.should_exit = True
            with suppress(TimeoutError):
                await asyncio.wait_for(server_task, 8)
            if not server_task.done():
                server_task.cancel()
                await asyncio.gather(server_task, return_exceptions=True)
            try:
                await self.client.shutdown()
            finally:
                self.overnight_recap.flush()
                settings.save()
                listener.close()

    def _snapshot(self) -> dict:
        gui = self.client.gui
        session = self.client.session_controller.status()
        logged_in = self.client._auth_state._logged_in.is_set()
        busy = self.recovering or self.login_task is not None and not self.login_task.done()
        if not busy:
            diagnostic = session.get("renewal_diagnostic") or (self.connection_error.to_dict() if self.connection_error else None)
            if diagnostic:
                self.connection = {"phase": "attention", "message": "Session verification needs attention. Retry the saved session or sign in again.",
                                   "code": diagnostic["code"], "diagnostic": diagnostic}
            elif logged_in:
                loaded = (bool(getattr(self.client, "_inventory_loaded", False))
                          and not getattr(self.client, "_inventory_refresh_pending", False)
                          and getattr(getattr(self.client, "_state", None), "name", "") != "INVENTORY_FETCH")
                self.connection = {"phase": "ready" if loaded else "loading", "code": "",
                                   "message": "Connected. Eligible campaigns are up to date." if loaded else "Connected. Loading campaign data…"}
            elif self.client.session_controller.session.seed() is not None:
                self.connection = {"phase": "recovering", "code": "", "message": "Restoring the saved session…"}
            else:
                self.connection = {"phase": "signed_out", "code": "", "message": "Sign in to connect Twitch."}
        can_recover = self.client.session_controller.session.seed() is not None and not session.get("renewal_requires_login")
        progress = gui.progress.get_current_drop()
        queue = MiningPlanner.build(self.client)
        mining_health = self.mining_health.update(
            self.client, logged_in=logged_in, ready=not busy and self.connection["phase"] == "ready",
            progress=progress, queue=queue,
        )
        progress = gui.progress.get_current_drop()
        history = self.client.drop_history.get_entries(limit=500)
        recap = self.overnight_recap.sample(
            self.client, account=getattr(self.client._auth_state, "user_id", None) if logged_in else None,
            state=mining_health.get("state"), progress=progress, queue=queue, history=history,
            ready=not busy and self.connection["phase"] == "ready",
        )
        return copy.deepcopy({
            "status": gui.status.get(),
            "login": gui.login.get_status(),
            "session": session,
            "connection": {**self.connection, "can_recover": can_recover},
            "logged_in": logged_in,
            "pause": self.client.pause_info(),
            "progress": progress,
            "overnight_recap": recap,
            "mining_health": mining_health,
            "channels": gui.channels.get_channels(),
            "campaigns": gui.inv.get_campaigns(),
            "settings": gui.settings.get_settings(),
            "lines": gui.output.get_history()[-250:],
            "history": history,
            "total_claimed": self.client.drop_history.total_count,
            "queue": queue,
        })

    async def _publish_loop(self):
        while True:
            self.snapshot.emit(self._snapshot())
            await asyncio.sleep(2)

    def submit(self, name: str, payload=None):
        loop = self.loop
        if not loop or self.stopping:
            self.command_finished.emit(name, False, "The miner is not ready yet.")
            return

        def enqueue():
            if self.stopping:
                return
            task = asyncio.create_task(self._dispatch(name, payload))
            self.jobs.add(task)
            task.add_done_callback(self.jobs.discard)

        with suppress(RuntimeError):
            loop.call_soon_threadsafe(enqueue)

    async def _dispatch(self, name: str, payload):
        from src.auth.session_bundle import SessionError

        try:
            if name == "login":
                if self.recovering:
                    raise SessionError("BUSY")
                if self.login_task and not self.login_task.done():
                    return
                choice = (payload or {}).get("browser", "auto")
                if choice not in ("auto", "chrome", "chromium", "firefox"):
                    raise ValueError("Unknown sign-in browser")
                self.login_task = asyncio.create_task(self._login(choice))
            elif name == "recover":
                if self.recovering or self.login_task is not None and not self.login_task.done():
                    raise SessionError("BUSY")
                await self._recover()
            elif name == "desktop_policy":
                self.client.desktop_deadline_queue = bool(payload)
                self.client.request_games_update()
            elif name == "cancel_login":
                if self.login_task and not self.login_task.done():
                    self.login_task.cancel()
                    await asyncio.gather(self.login_task, return_exceptions=True)
                else:
                    await self.client.cancel_helper()
            elif name == "finish_login":
                browser = self.active_login_browser
                # Closing the sign-in window manually can advance the helper before
                # Qt's queued Finish click reaches the engine.
                if browser is not None:
                    await browser.finish_login()
            elif name == "settings":
                self.client.gui.settings.update_settings(payload)
                self.notice.emit("Settings saved.")
            elif name == "pause":
                self.client.set_paused(bool(payload))
            elif name == "refresh":
                if not self.client.request_inventory_refresh():
                    raise ValueError("Miner is stopping")
                self.notice.emit("Refreshing campaigns from Twitch…")
            elif name == "logout":
                if self.login_task and not self.login_task.done():
                    self.login_task.cancel()
                    await asyncio.gather(self.login_task, return_exceptions=True)
                await self.client.logout()
                self.connection_error = None
                self.notice.emit("Signed out. Your settings and history are saved.")
            elif name == "export":
                self.exported.emit(self.client.drop_history.to_csv())
            else:
                raise ValueError("Unknown command")
            self.snapshot.emit(self._snapshot())
            self.command_finished.emit(name, True, "")
        except SessionError as error:
            if name == "finish_login" and error.code == "HELPER_BROWSER":
                guidance = "Close the Twitch sign-in window normally to continue. If it is unresponsive, cancel and try another browser."
            else:
                from src.auth.helper_errors import HelperDiagnostics

                _, guidance = HelperDiagnostics.describe(error.code)
            self.command_finished.emit(name, False, f"{guidance} ({error.code})")
        except Exception:
            logging.getLogger("TwitchDrops.desktop").exception("Desktop command failed: %s", name)
            self.command_finished.emit(name, False, "The action could not finish. Please try again.")

    async def _login(self, browser_choice="auto"):
        from src.auth.helper_errors import HelperDiagnostics
        from src.auth.login_helper import BrowserSelection, NativeLoginHelper
        from src.auth.session_bundle import SessionError

        success = False
        admitted = False
        self.connection_error = None
        self._set_connection("signing_in", "Opening the sign-in browser…")
        message = "Sign-in cancelled. You can reconnect whenever you are ready."
        try:
            async with asyncio.timeout(self.LOGIN_TIMEOUT_SECONDS):
                await self.client.enable_helper(lambda: not self.stopping)
                admitted = True

                def create_browser():
                    browser = BrowserSelection.create(browser_choice)
                    browser.background_capture = True
                    return browser

                helper = NativeLoginHelper(
                    f"http://127.0.0.1:{self.port}", report=self._report_login,
                    browser_factory=create_browser,
                )
                helper.browser_changed = lambda browser: setattr(self, "active_login_browser", browser)
                await helper.run()
            success = True
            self.connection_error = None
            self._set_connection("loading", "Connected. Loading eligible campaigns…")
            message = "Twitch connected. Checking your eligible campaigns…"
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            from src.auth.session_diagnostics import SessionDiagnostic

            self.connection_error = SessionDiagnostic(code="HELPER_LOGIN_TIMEOUT", stage="browser_login", reason="timeout")
            message = "Sign-in timed out. You can retry, or select Firefox if Twitch's code page keeps spinning."
        except SessionError as error:
            if (not admitted and error.code == "HELPER_STATE"
                    and (self.client._auth_state._logged_in.is_set()
                         or self.client.session_controller.session.status()["state"] == "ready")):
                # Restoring the saved session can win the race with a new login
                # request. The validated session belongs to the existing flow.
                success = True
                message = "Twitch session restored. Checking your eligible campaigns…"
                self._set_connection("loading", message)
            else:
                self.connection_error = error.diagnostic
                code, guidance = HelperDiagnostics.describe(error.code)
                if error.code == "CATALOG" and error.diagnostic.reason == "integrity":
                    message = "Twitch rejected the session verification. The app could not connect; campaign data has not been loaded. Please retry later. (SESSION_CATALOG)"
                else:
                    message = f"{guidance} ({code})"
        except Exception:
            logging.getLogger("TwitchDrops.desktop").exception("Desktop login failed")
            self.connection_error = SessionError("HELPER_FAILED", stage="browser_login", reason="unexpected_exception").diagnostic
            message = "Sign-in could not finish. Close its browser window and try again."
        finally:
            self.active_login_browser = None
            if not success and not self.stopping:
                try:
                    await asyncio.wait_for(self.client.cancel_helper(), timeout=10)
                except Exception:
                    logging.getLogger("TwitchDrops.desktop").warning("Sign-in admission cleanup did not finish")
            self.login_finished.emit(success, message)

    async def _recover(self):
        from src.auth.recovery import SessionRecovery
        from src.auth.session_bundle import SessionError

        controller = self.client.session_controller
        if controller.session.seed() is None:
            raise SessionError("SDK_SEED")
        self.recovering = True
        self.connection_error = None
        try:
            async with asyncio.timeout(180):
                for attempt in range(len(SessionRecovery.DELAYS) + 1):
                    self._set_connection("recovering", "Revalidating the saved session without a sign-in browser…", attempt=attempt)
                    try:
                        await controller.renew_once()
                        self.connection_error = None
                        self._set_connection("loading", "Connection recovered. Loading campaigns…")
                        self.client.request_inventory_refresh()
                        return
                    except SessionError as error:
                        self.connection_error = error.diagnostic
                        if attempt >= len(SessionRecovery.DELAYS) or not SessionRecovery.retryable(error):
                            raise
                        await asyncio.sleep(SessionRecovery.DELAYS[attempt])
        except TimeoutError:
            self.connection_error = SessionError("SDK_TIMEOUT", stage="renewal_issuance", reason="timeout").diagnostic
            raise SessionError("SDK_TIMEOUT", stage="renewal_issuance", reason="timeout") from None
        finally:
            self.recovering = False

    def stop(self):
        self.stopping = True
        loop = self.loop
        if loop and self.client:
            with suppress(RuntimeError):
                loop.call_soon_threadsafe(self.client.close)
