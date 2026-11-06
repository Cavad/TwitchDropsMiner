"""Launch the Windows desktop edition, including its owned miner lifecycle."""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler


def main() -> int:
    # Windowed PyInstaller builds have no standard streams.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115 - process-lifetime stream
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115 - process-lifetime stream

    if len(sys.argv) == 3 and sys.argv[1] == "--verify-build":
        from desktop.verify import run

        return run(sys.argv[2])

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
    window.show()
    if "--start-in-tray" in sys.argv:
        QTimer.singleShot(0, window._hide_to_tray)
    if sys.platform == "win32":
        import ctypes

        with_dark_caption = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(int(window.winId()), 20, ctypes.byref(with_dark_caption), ctypes.sizeof(with_dark_caption))
    engine.start()
    result = application.exec()
    if engine.isRunning():
        engine.stop()
        engine.wait()
    lock.unlock()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
