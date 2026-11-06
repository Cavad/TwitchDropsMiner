"""Local desktop tray controls and deduplicated Windows notifications."""

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from desktop.planning import NotificationTracker


class SystemTrayController(QObject):
    def __init__(self, window, icon):
        super().__init__(window)
        self.window = window
        self.available = QSystemTrayIcon.isSystemTrayAvailable()
        self.tracker = NotificationTracker()
        self.hidden_notice_shown = False
        self.icon = None
        if self.available:
            self.icon = QSystemTrayIcon(icon, window)
            self.menu = QMenu(window)
            self.menu.addAction("Open miner", self.restore)
            self.pause_action = self.menu.addAction("Pause mining", window._toggle_pause)
            self.pause_action.setEnabled(False)
            self.menu.addAction("Hide to tray", window._hide_to_tray)
            self.menu.addSeparator()
            self.menu.addAction("Quit and stop mining", window._request_quit)
            self.icon.setContextMenu(self.menu)
            self.icon.setToolTip("Twitch Drops Miner · Starting")
            self.icon.activated.connect(self._activated)
            self.icon.messageClicked.connect(self.restore)
            self.icon.show()

    def _activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.restore()

    def restore(self):
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

    def hide_window(self) -> bool:
        if not self.available:
            return False
        self.window.hide()
        if not self.hidden_notice_shown:
            self.notify("Miner is running in the tray", "Open the tray icon to resume the window. Use Quit to stop mining.")
            self.hidden_notice_shown = True
        return True

    def notify(self, title, message):
        if self.icon is not None and self.window.preferences.values["notifications"]:
            self.icon.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 6000)

    def update(self, data):
        for title, message in self.tracker.update(data):
            self.notify(title, message)
        if self.icon is not None:
            paused = data.get("pause", {}).get("paused", False)
            self.pause_action.setText("Resume mining" if paused else "Pause mining")
            self.pause_action.setEnabled(bool(data.get("logged_in")) and self.window.engine_ready)
            phase = data.get("connection", {}).get("phase", "starting")
            self.icon.setToolTip(f"Twitch Drops Miner · {'Paused' if paused else phase.replace('_', ' ').title()}")

    def stop(self):
        if self.icon is not None:
            self.icon.hide()
