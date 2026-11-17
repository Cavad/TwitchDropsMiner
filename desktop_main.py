"""Launch the Windows desktop edition, including its owned miner lifecycle."""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler


ENGINE_STOP_WAIT_MS = 20_000


def install_lifecycle(application, window) -> None:
    """Quit only on an explicit request, and stop cleanly when Windows signs out."""
    # Tray mode hides the window; Qt would otherwise quit when any dialog closes while
    # hidden, and would never quit when the hidden window itself is closed.
    application.setQuitOnLastWindowClosed(False)
    application.commitDataRequest.connect(window.prepare_session_end)


def stop_engine(engine, wait_ms: int = ENGINE_STOP_WAIT_MS) -> bool:
    """Stop the engine thread; return False if it is still running after ``wait_ms``."""
    if not engine.isRunning():
        return True
    engine.stop()
    return bool(engine.wait(wait_ms))


def main() -> int:
    # Windowed PyInstaller builds have no standard streams.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115 - process-lifetime stream
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115 - process-lifetime stream

    if (len(sys.argv) == 3 or len(sys.argv) == 4 and sys.argv[3] == "--ci") and sys.argv[1] == "--verify-build":
        from desktop.verify import run

        return run(sys.argv[2], interactive=len(sys.argv) == 3)

    from PySide6.QtCore import QLockFile, QTimer
    from PySide6.QtWidgets import QApplication, QMessageBox

    from desktop.engine import MinerEngine
    from desktop.model import desktop_home
    from desktop.window import MainWindow, application_icon

    home = desktop_home()
    home.mkdir(parents=True, exist_ok=True)
    (home / "data").mkdir(exist_ok=True)
    (home / "logs").mkdir(exist_ok=True)
    os.environ["TDM_DATA_DIR"] = str(home / "data")
    application = QApplication(sys.argv)
    application.setApplicationName("Twitch Drops Miner Desktop")
    application.setOrganizationName("TwitchDropsMinerDesktop")
    application.setWindowIcon(application_icon())
    lock = QLockFile(str(home / "desktop.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        QMessageBox.information(None, "Twitch Drops Miner", "The desktop miner is already running. Switch to its existing window.")
        return 0
    handler = RotatingFileHandler(home / "logs" / "desktop.log", maxBytes=2*1024*1024, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)
    engine = MinerEngine()
    window = MainWindow(engine)
    install_lifecycle(application, window)
    window.show()
    if "--start-in-tray" in sys.argv:
        QTimer.singleShot(0, window._hide_to_tray)
    if sys.platform == "win32":
        import ctypes

        with_dark_caption = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(int(window.winId()), 20, ctypes.byref(with_dark_caption), ctypes.sizeof(with_dark_caption))
    engine.start()
    result = application.exec()
    if not stop_engine(engine):
        # Never leave a windowless process behind: a stuck engine thread would keep it alive.
        logging.getLogger("TwitchDrops.desktop").error("Engine thread did not stop; forcing exit")
        lock.unlock()
        logging.shutdown()
        os._exit(result or 1)
    lock.unlock()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
