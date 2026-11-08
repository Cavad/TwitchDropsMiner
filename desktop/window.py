"""Native, keyboard-accessible Windows interface for the existing miner."""

from __future__ import annotations

import json
from contextlib import suppress
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QElapsedTimer, QEvent, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QGuiApplication,
    QIcon,
    QLinearGradient,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from desktop.model import campaign_matches, desktop_home, progress_percent
from desktop.planning import MiningPlanner
from desktop.preferences import DesktopPreferences
from desktop.system_tray import SystemTrayController


THEME = """
QWidget { background: #101116; color: #ececf5; font-family: 'Segoe UI'; font-size: 14px; }
QMainWindow { background: #101116; }
QLabel { background: transparent; }
QLabel[role='muted'] { color: #9294a7; }
QLabel[role='eyebrow'] { color: #85889d; font-size: 11px; font-weight: 700; letter-spacing: 2px; }
QLabel[role='title'] { color: #fafaff; font-size: 32px; font-weight: 700; }
QLabel[role='section'] { color: #f1f0fa; font-size: 18px; font-weight: 600; }
QLabel[role='metric'] { color: #f5f4ff; font-size: 32px; font-weight: 600; }
QFrame#sidebar { background: #14151c; border-right: 1px solid #252631; }
QFrame#card { background: #1a1b24; border: 1px solid #2b2c3a; border-radius: 14px; }
QFrame#hero { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #252039,stop:1 #1a1b29); border: 1px solid #493665; border-radius: 18px; }
QFrame#banner { background: #282039; border: 1px solid #493665; border-radius: 10px; }
QPushButton { background: #252631; border: 1px solid #363846; border-radius: 8px; padding: 10px 17px; font-weight: 600; min-height: 20px; }
QPushButton:hover { background: #303140; border-color: #606274; }
QPushButton:pressed { background: #1e1f29; }
QPushButton:focus { border: 2px solid #c3a6ff; }
QPushButton:disabled { color: #6c6e80; background: #20212b; border-color: #2d2e3a; }
QPushButton[role='primary'] { background: #a178f3; color: #120c20; border-color: #aa85f8; font-weight: 700; }
QPushButton[role='primary']:hover { background: #b18afc; }
QPushButton[role='primary']:disabled { background: #4d3d69; color: #a18bbd; border-color: #574370; }
QPushButton[role='nav'] { background: transparent; border: 1px solid transparent; text-align: left; color: #9ea0b2; padding: 12px 18px; }
QPushButton[role='nav']:checked { background: #2b233e; color: #d3b9ff; border-color: #443258; }
QPushButton[role='nav']:hover { background: #22232e; color: #f3edff; }
QPushButton[role='link'] { background: transparent; border: none; color: #c3a1ff; text-align: left; padding: 6px 0; }
QPushButton[role='danger'] { color: #f9a6b1; }
QLineEdit,QComboBox,QSpinBox,QListWidget,QPlainTextEdit,QTableWidget { background: #14151d; border: 1px solid #353744; border-radius: 8px; padding: 10px; selection-background-color: #604790; }
QLineEdit:focus,QComboBox:focus,QSpinBox:focus,QListWidget:focus { border-color: #a178f3; }
QComboBox QAbstractItemView { background: #22232e; color: #f0eafa; selection-background-color: #604790; }
QCheckBox { spacing: 10px; background: transparent; padding: 7px 0; }
QCheckBox::indicator { width: 18px; height: 18px; border-radius: 5px; background: #14151d; border: 1px solid #55576b; }
QCheckBox::indicator:checked { background: #a178f3; border: 4px solid #d4baff; }
QProgressBar { background: #30303e; border: none; border-radius: 4px; height: 8px; text-align: center; }
QProgressBar::chunk { background: #a178f3; border-radius: 4px; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { width: 8px; background: transparent; margin: 2px; }
QScrollBar::handle:vertical { background: #414352; border-radius: 3px; min-height: 30px; }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height: 0px; }
QTableWidget { gridline-color: #2b2c38; }
QTableWidget::item { padding: 10px; }
QHeaderView::section { background: #1d1e28; color: #989aaf; padding: 12px; border: none; border-bottom: 1px solid #353744; font-weight: 600; }
QListWidget::item { padding: 10px; border-bottom: 1px solid #292a36; }
QToolTip { background: #2b2539; color: #f1eafa; border: 1px solid #604790; padding: 7px; }
"""


def label(text: str, role: str = "", wrap: bool = False) -> QLabel:
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setProperty("role", role)
    widget.setWordWrap(wrap)
    return widget


def button(text: str, callback, role: str = "", name: str = "") -> QPushButton:
    widget = QPushButton(text)
    widget.setProperty("role", role)
    widget.setObjectName(name)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    widget.clicked.connect(callback)
    return widget


def card(name: str = "card", spacing: int = 12) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName(name)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(24, 22, 24, 22)
    layout.setSpacing(spacing)
    return frame, layout


def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()


class LootArt(QWidget):
    """Original vector artwork drawn at the native display scale."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(190, 190)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.setFixedWidth(220)
        self.setAccessibleName("Decorative reward chest")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.translate(self.width() / 2, self.height() / 2)
        p.setPen(QPen(QColor("#49355f"), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(-88, -88, 176, 176))
        p.drawEllipse(QRectF(-66, -66, 132, 132))
        p.setPen(Qt.PenStyle.NoPen)
        for x, y, radius in ((-83, -28, 4), (72, 48, 4), (33, -81, 3)):
            p.setBrush(QColor("#c5a0ff"))
            p.drawEllipse(QRectF(x-radius, y-radius, radius*2, radius*2))
        p.save()
        p.rotate(-10)
        gradient = QLinearGradient(-50, -50, 55, 60)
        gradient.setColorAt(0, QColor("#bd98ff"))
        gradient.setColorAt(1, QColor("#7447b8"))
        p.setBrush(gradient)
        p.drawRoundedRect(QRectF(-54, -39, 108, 91), 15, 15)
        p.setBrush(QColor("#ddc4ff"))
        p.drawRoundedRect(QRectF(-60, -45, 120, 33), 10, 10)
        p.setBrush(QColor("#4b2e76"))
        p.drawRoundedRect(QRectF(-12, -23, 24, 45), 7, 7)
        p.setBrush(QColor("#f4e7ff"))
        p.drawEllipse(QRectF(-4, -9, 8, 8))
        p.restore()
        p.setPen(QPen(QColor("#d6baff"), 2))
        for x, y in ((-61, 63), (71, -55)):
            p.drawLine(x-5, y, x+5, y)
            p.drawLine(x, y-5, x, y+5)


class OverviewScrollArea(QScrollArea):
    def __init__(self, artwork):
        super().__init__()
        self.artwork = artwork

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.artwork.setVisible(self.viewport().width() >= 840)


def application_icon() -> QIcon:
    pixmap = QPixmap(128, 128)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#9e75ef"))
    painter.drawRoundedRect(QRectF(3, 3, 122, 122), 29, 29)
    painter.setBrush(QColor("#1d132d"))
    painter.drawRoundedRect(QRectF(29, 43, 70, 53), 9, 9)
    painter.drawRoundedRect(QRectF(24, 33, 80, 21), 5, 5)
    painter.setBrush(QColor("#e8d5ff"))
    painter.drawRoundedRect(QRectF(57, 43, 14, 29), 4, 4)
    painter.end()
    return QIcon(pixmap)


class MainWindow(QMainWindow):
    def __init__(self, engine, preferences=None):
        super().__init__()
        self.engine = engine
        self.preferences = preferences or DesktopPreferences()
        self.force_quit = False
        self.desktop_options_dirty = False
        self.queue_signature = None
        self.data = {}
        self.engine_ready = False
        self.login_busy = False
        self.login_cancelling = False
        self.login_stage = ""
        self.login_clock = QElapsedTimer()
        self.login_timer = QTimer(self)
        self.login_timer.setInterval(1000)
        self.login_timer.timeout.connect(self._login_tick)
        self.settings_dirty = False
        self.settings_saving = False
        self.settings_revision = 0
        self.saving_revision = 0
        self.closing = False
        self.export_path = None
        self.campaign_signature = None
        self.history_signature = None
        self.console_signature = None
        self.settings_signature = None
        self.setWindowTitle("Twitch Drops Miner · Desktop")
        self.setWindowIcon(application_icon())
        self.resize(1280, 860)
        self.setMinimumSize(1000, 720)
        self.setStyleSheet(THEME)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._sidebar())
        content = QWidget()
        body = QVBoxLayout(content)
        body.setContentsMargins(32, 26, 32, 22)
        body.setSpacing(18)
        top = QHBoxLayout()
        self.breadcrumb = label("WORKSPACE  /  OVERVIEW", "eyebrow", True)
        top.addWidget(self.breadcrumb)
        top.addStretch()
        self.refresh_button = button("↻  Refresh", lambda: self.engine.submit("refresh"), name="refreshButton")
        self.pause_button = button("Ⅱ  Pause mining", self._toggle_pause, name="pauseButton")
        self.tray_button = button("Tray", self._hide_to_tray, name="hideToTrayButton")
        top.addWidget(self.tray_button)
        top.addWidget(self.refresh_button)
        top.addWidget(self.pause_button)
        body.addLayout(top)
        self.banner, banner_layout = card("banner")
        banner_layout.setContentsMargins(16, 12, 16, 12)
        self.banner_text = label("", wrap=True)
        banner_layout.addWidget(self.banner_text)
        self.banner.hide()
        body.addWidget(self.banner)
        self.pages = QStackedWidget()
        body.addWidget(self.pages, 1)
        for page in (self._overview(), self._campaigns(), self._history(), self._activity(), self._settings(), self._queue_page()):
            self.pages.addWidget(page)
        layout.addWidget(content, 1)
        self.status_line = label("Starting your local miner…", "muted")
        self.status_line.setMaximumHeight(35)
        body.addWidget(self.status_line)
        self.toast_timer = QTimer(self)
        self.toast_timer.setSingleShot(True)
        self.toast_timer.timeout.connect(self.banner.hide)
        engine.ready.connect(self._ready)
        engine.snapshot.connect(self._update)
        engine.notice.connect(self.show_notice)
        engine.fatal.connect(self._fatal)
        engine.login_phase.connect(self._login_phase)
        engine.login_finished.connect(self._login_finished)
        engine.command_finished.connect(self._command_finished)
        engine.exported.connect(self._write_export)
        engine.finished.connect(self._engine_stopped)
        if hasattr(engine, "connection_changed"):
            engine.connection_changed.connect(self._render_connection)
        self.system_tray = SystemTrayController(self, application_icon())
        self.tray_button.setEnabled(self.system_tray.available)
        self.refresh_button.setEnabled(False)
        self.pause_button.setEnabled(False)

    def _sidebar(self):
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(216)
        layout = QVBoxLayout(side)
        layout.setContentsMargins(18, 28, 18, 22)
        layout.setSpacing(8)
        logo = QHBoxLayout()
        mark = QLabel()
        mark.setPixmap(application_icon().pixmap(40, 40))
        logo.addWidget(mark)
        logo.addSpacing(5)
        logo.addWidget(label("DROPS MINER", "section"))
        layout.addLayout(logo)
        edition = label("D E S K T O P   E D I T I O N", "muted")
        edition.setStyleSheet("font-size: 9px; padding: 3px 0 25px 2px;")
        layout.addWidget(edition)
        layout.addWidget(label("YOUR WORKSPACE", "eyebrow"))
        layout.addSpacing(8)
        self.navigation = []
        for index, icon, text in ((0, '◫', 'Overview'), (5, '⇥', 'Mining queue'), (1, '◇', 'Campaigns'), (2, '◷', 'History'), (3, '≡', 'Activity'), (4, '⚙', 'Settings')):
            nav = button(f"{icon}    {text}", lambda checked=False, n=index: self.navigate(n), "nav", f"nav{text}")
            nav.setCheckable(True)
            nav.setProperty("page_index", index)
            nav.setChecked(index == 0)
            self.navigation.append(nav)
            layout.addWidget(nav)
        layout.addStretch()
        note = label("Made for quieter\nreward collecting.", "muted")
        note.setStyleSheet("font-size: 12px; line-height: 1.5;")
        layout.addWidget(note)
        layout.addSpacing(16)
        self.engine_indicator = label("●  Starting engine", "muted")
        layout.addWidget(self.engine_indicator)
        layout.addWidget(label("v2.5.0  /  Desktop r9", "muted"))
        return side

    def navigate(self, index):
        self.pages.setCurrentIndex(index)
        for nav in self.navigation:
            nav.setChecked(nav.property("page_index") == index)
        self.breadcrumb.setText(f"WORKSPACE  /  {('OVERVIEW', 'CAMPAIGNS', 'HISTORY', 'ACTIVITY', 'SETTINGS', 'MINING QUEUE')[index]}")

    def _overview(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)
        layout.addWidget(label("Your drops, on autopilot.", "title", True))
        layout.addWidget(label("A little less watching. A lot more collecting.", "muted", True))
        connection, connection_layout = card()
        connection_layout.setContentsMargins(18, 13, 18, 13)
        self.connection_steps = label("1  Sign in     →     2  Verify     →     3  Load campaigns     →     4  Ready", "muted", True)
        connection_layout.addWidget(self.connection_steps)
        self.connection_progress = QProgressBar()
        self.connection_progress.setRange(0, 4)
        self.connection_progress.setTextVisible(False)
        self.connection_progress.setAccessibleName("Connection progress")
        connection_layout.addWidget(self.connection_progress)
        connection_row = QHBoxLayout()
        self.connection_message = label("Starting the local miner…", "muted", True)
        connection_row.addWidget(self.connection_message, 1)
        self.recover_button = button("Retry saved session", lambda: self.engine.submit("recover"), name="recoverSessionButton")
        self.recover_button.hide()
        connection_row.addWidget(self.recover_button)
        self.copy_diagnostics = button("Copy diagnostics", self._copy_connection_diagnostics)
        self.copy_diagnostics.hide()
        connection_row.addWidget(self.copy_diagnostics)
        connection_layout.addLayout(connection_row)
        layout.addWidget(connection)
        hero, hero_layout = card("hero")
        hero_layout.setContentsMargins(28, 22, 18, 22)
        row = QHBoxLayout()
        details = QVBoxLayout()
        details.setSpacing(12)
        details.addWidget(label("LET THE GOOD DROPS ROLL", "eyebrow", True))
        self.hero_title = label("Make every minute count.", "section", True)
        self.hero_title.setStyleSheet("font-size: 26px; font-weight: 650;")
        details.addWidget(self.hero_title)
        self.hero_copy = label("Connect Twitch to discover campaigns, follow your\ngame priorities, and claim eligible earned rewards.", "muted", True)
        details.addWidget(self.hero_copy)
        browser_row = QHBoxLayout()
        self.login_browser_label = label("Sign-in browser", "muted", True)
        browser_row.addWidget(self.login_browser_label)
        self.login_browser = QComboBox()
        self.login_browser.setAccessibleName("Twitch sign-in browser")
        self.login_browser.addItem("Automatic", "auto")
        self.login_browser.addItem("Google Chrome", "chrome")
        self.login_browser.addItem("Firefox", "firefox")
        self.login_browser.addItem("Chromium", "chromium")
        browser_row.addWidget(self.login_browser)
        browser_row.addStretch()
        details.addLayout(browser_row)
        actions = QHBoxLayout()
        self.connect_button = button("Connect Twitch  →", self._connect_twitch, "primary", "connectTwitchButton")
        self.connect_button.setMinimumWidth(190)
        self.connect_button.setEnabled(False)
        self.cancel_login = button("Cancel", self._cancel_login, name="cancelLoginButton")
        self.cancel_login.hide()
        self.finish_login = button("Finish sign-in", self._finish_login, name="finishLoginButton")
        self.finish_login.hide()
        actions.addWidget(self.connect_button)
        actions.addWidget(self.finish_login)
        actions.addWidget(self.cancel_login)
        actions.addStretch()
        details.addLayout(actions)
        self.login_hint = label("Secure browser sign-in · Session stored on this PC", "muted", True)
        self.login_hint.setStyleSheet("font-size: 12px;")
        details.addWidget(self.login_hint)
        row.addLayout(details, 1)
        artwork = LootArt()
        row.addWidget(artwork)
        hero_layout.addLayout(row)
        layout.addWidget(hero)
        stats = QHBoxLayout()
        stats.setSpacing(14)
        self.metrics = []
        for title, caption in (("Active campaigns", "Ready to earn"), ("Rewards claimed", "Your collection so far"), ("Tracked channels", "Eligible streams discovered")):
            metric, inner = card()
            inner.setContentsMargins(20, 16, 20, 16)
            inner.setSpacing(4)
            inner.addWidget(label(title, "muted", True))
            number = label("—", "metric")
            self.metrics.append(number)
            inner.addWidget(number)
            inner.addWidget(label(caption, "muted", True))
            stats.addWidget(metric, 1)
        layout.addLayout(stats)
        bottom = QHBoxLayout()
        bottom.setSpacing(14)
        mining, mining_layout = card()
        mining_layout.addWidget(label("NOW MINING", "eyebrow"))
        self.mining_title = label("Ready when you are", "section", True)
        self.mining_detail = label("Sign in and choose your games.\nYour current reward will appear here.", "muted", True)
        self.mining_progress = QProgressBar()
        self.mining_progress.setTextVisible(False)
        self.mining_progress.setValue(0)
        self.mining_progress.setAccessibleName("Current reward progress")
        mining_layout.addWidget(self.mining_title)
        mining_layout.addWidget(self.mining_detail)
        self.mining_health = label("", "muted", True)
        mining_layout.addWidget(self.mining_health)
        mining_layout.addStretch()
        mining_layout.addWidget(self.mining_progress)
        bottom.addWidget(mining, 3)
        queue, queue_layout = card()
        queue_layout.addWidget(label("MINING LIST", "eyebrow"))
        self.queue_title = label("Your games, your order.", "section", True)
        self.queue_detail = label("Set a priority list to focus\non the rewards you want.", "muted", True)
        queue_layout.addWidget(self.queue_title)
        queue_layout.addWidget(self.queue_detail)
        queue_layout.addStretch()
        queue_layout.addWidget(button("Manage games  →", lambda: self.navigate(4), "link"))
        bottom.addWidget(queue, 2)
        layout.addLayout(bottom, 1)
        self.overview_scroll = OverviewScrollArea(artwork)
        self.overview_scroll.setWidgetResizable(True)
        self.overview_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.overview_scroll.setWidget(page)
        return self.overview_scroll

    def _queue_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        layout.addWidget(label("A smarter reward queue.", "title", True))
        layout.addWidget(label("Your selected game priorities come first. Additional eligible games follow campaign deadlines; the miner switches channels automatically.", "muted", True))
        layout.addWidget(label("Times are a sequential planning budget with continuous eligible watching. Pauses, schedules, offline streams and Twitch delays can extend them; they are not a guarantee.", "muted", True))
        self.queue_summary = label("Connect Twitch to load the eligible queue.", "muted", True)
        layout.addWidget(self.queue_summary)
        layout.addWidget(button("Configure game preferences and automatic discovery  →", lambda: self.navigate(4), "link"))
        self.queue_table = QTableWidget(0, 6)
        self.queue_table.setHorizontalHeaderLabels(["GAME", "REWARD", "WATCH TIME", "BUDGETED FINISH", "DEADLINE", "OUTLOOK"])
        self.queue_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.queue_table.verticalHeader().hide()
        self.queue_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.queue_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.queue_table.setWordWrap(True)
        layout.addWidget(self.queue_table, 1)
        return page

    def _render_connection(self, connection):
        phase = connection.get("phase", "starting")
        number = {"starting": 0, "signed_out": 0, "signing_in": 1, "verifying": 2, "recovering": 2, "loading": 3, "ready": 4, "attention": 0}.get(phase, 0)
        self.connection_progress.setValue(number)
        text = connection.get("message", "Connect Twitch to get started.")
        diagnostic = connection.get("diagnostic")
        self.visible_diagnostic = None
        if phase == "attention" and diagnostic:
            from src.auth.session_diagnostics import SessionDiagnostic

            safe = SessionDiagnostic.from_dict(diagnostic)
            self.visible_diagnostic = safe
            text = f"{self._connection_guidance(safe, connection.get('can_recover', False))} ({safe.code} · {safe.stage} · {safe.reason})"
        self.connection_message.setText(text)
        self.recover_button.setVisible(phase == "attention" and connection.get("can_recover", False))
        self.recover_button.setEnabled(not self.login_busy and phase == "attention")
        self.copy_diagnostics.setVisible(self.visible_diagnostic is not None)

    def _connection_guidance(self, diagnostic, can_recover):
        if diagnostic.code == "SAVE":
            return "The session could not be saved. Check free space and write access to the miner’s data folder, then retry."
        if diagnostic.code == "ACCOUNT_MISMATCH":
            return "Twitch returned a different account. Sign out in the miner if connected, then connect with the intended account."
        if diagnostic.code == "HELPER_FIREFOX_VERSION":
            return "Update Firefox to version 143 or later, or choose Chrome or Chromium for sign-in."
        if diagnostic.stage in ("browser_start", "browser_login", "browser_capture") or diagnostic.code.startswith("HELPER_"):
            return "Close the sign-in window normally if it is still open. To retry a failed sign-in, open Connect Twitch and try another installed browser."
        if diagnostic.reason in ("tls", "dns", "connection"):
            return "Check that Twitch opens in your browser and check your network connection. Then retry the connection."
        if can_recover:
            return "Select Retry saved session to verify your connection and reload campaigns."
        return "Sign out in the miner if connected, then use Connect Twitch to start a fresh sign-in."

    def _copy_connection_diagnostics(self):
        if self.visible_diagnostic is not None:
            data = {"desktop": "2.5.0 r9", **self.visible_diagnostic.to_dict()}
            QGuiApplication.clipboard().setText(json.dumps(data, indent=2))
            self.show_notice("Copied connection diagnostics.")

    def _render_mining_health(self, health):
        state = health.get("state")
        messages = {
            "paused": "Mining is paused. Select Resume mining to continue.",
            "scheduled": "Outside your mining hours. Mining resumes in your next scheduled window.",
            "loading": "Waiting for Twitch campaign data or updated mining preferences.",
            "empty_list": "Your strict mining list is empty. Add a game or turn off Mine only games in this list.",
            "no_live_channel": "No eligible live channel was found. The miner will keep looking.",
            "selecting": "An eligible channel is available. The miner is selecting a stream.",
            "waiting_reward": "Queued rewards are waiting for their start time or prerequisites.",
            "link_account": "A campaign requires a linked game account. Check Campaigns for the game to link.",
            "no_rewards": "No eligible rewards match your current preferences. Check Campaigns and your Mining list.",
            "acquiring": "An eligible stream is live. Waiting for Twitch to identify the reward.",
            "refreshing": "No confirmed progress. Refreshing campaigns and checking again.",
            "switched": "Switched to another eligible channel. Waiting for confirmed progress.",
            "stalled": "Twitch progress is stalled. Check the campaign and try Refresh campaigns.",
        }
        lines = [messages[state]] if state in messages else []
        if health.get("selection") == "manual":
            lines.append("Channel selected manually.")
        elif health.get("selection") == "automatic":
            lines.append("Channel selected by campaign eligibility and mining priorities.")
        if health.get("confirmed_at"):
            confirmed = datetime.fromisoformat(health["confirmed_at"]).astimezone()
            lines.append(f"Last progress confirmed by Twitch: {confirmed:%d %b, %H:%M:%S}")
        elif state in ("watching", "acquiring", "refreshing", "switched", "stalled"):
            lines.append("Waiting for the first confirmed progress since connecting.")
        self.mining_health.setText("\n".join(lines))
        self.mining_health.setVisible(bool(lines))

    def _render_queue(self, rows):
        # The visible ETA has minute precision; preserve selection between snapshots.
        signature = json.dumps([{**row, "estimated_finish": row["estimated_finish"][:16]} for row in rows], sort_keys=True)
        if signature == self.queue_signature:
            return
        self.queue_signature = signature
        self.queue_table.setRowCount(len(rows))
        at_risk = sum(not row["fits"] for row in rows)
        self.queue_summary.setText(f"{len(rows)} eligible rewards in the planning queue · {at_risk} at risk under this budget" if rows else "No rewards are currently queued. Check your game preferences, account links and campaign eligibility.")
        for index, row in enumerate(rows):
            finish = datetime.fromisoformat(row["estimated_finish"]).astimezone().strftime("%d %b %H:%M")
            deadline = datetime.fromisoformat(row["deadline"]).astimezone().strftime("%d %b %H:%M")
            values = (row["game"], row["reward"], MiningPlanner.duration(row["chain_minutes"]), finish, deadline,
                      ("May fit" if row.get("can_earn_now", True) else "Waiting · may fit") if row["fits"] else "At risk")
            for column, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setToolTip(f"{row['campaign']}\nPrerequisites included in watch-time estimate. Availability may change.")
                self.queue_table.setItem(index, column, item)
            self.queue_table.setRowHeight(index, 58)

    def _campaigns(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        layout.addWidget(label("Find your next reward.", "title"))
        layout.addWidget(label("Campaigns and progress, straight from your Twitch inventory.", "muted"))
        filters = QHBoxLayout()
        self.campaign_search = QLineEdit()
        self.campaign_search.setPlaceholderText("Search games or campaigns…")
        self.campaign_search.setAccessibleName("Search campaigns")
        self.campaign_search.textChanged.connect(self._render_campaigns)
        self.campaign_filter = QComboBox()
        self.campaign_filter.addItems(["All campaigns", "Active", "Upcoming", "Completed"])
        self.campaign_filter.setAccessibleName("Campaign status filter")
        self.campaign_filter.currentTextChanged.connect(self._render_campaigns)
        filters.addWidget(self.campaign_search, 1)
        filters.addWidget(self.campaign_filter)
        layout.addLayout(filters)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        self.campaign_layout = QVBoxLayout(container)
        self.campaign_layout.setContentsMargins(0, 0, 8, 0)
        self.campaign_layout.setSpacing(14)
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)
        self._render_campaigns()
        return page

    def _render_campaigns(self):
        if not hasattr(self, "campaign_layout"):
            return
        campaigns = [c for c in self.data.get("campaigns", []) if campaign_matches(c, self.campaign_search.text(), self.campaign_filter.currentText())]
        # The add action depends on the saved Mining list and save state, not only campaign data.
        selected = sorted({name.casefold() for name in self.data.get("settings", {}).get("games_to_watch", [])})
        signature = json.dumps([campaigns, selected, self.settings_saving], sort_keys=True)
        if self.campaign_signature == signature:
            return
        self.campaign_signature = signature
        clear_layout(self.campaign_layout)
        if not campaigns:
            empty, inner = card()
            inner.addSpacing(60)
            inner.addWidget(label("Nothing here just yet.", "section"))
            inner.addWidget(label("Connect Twitch to load your campaigns, or try another filter.", "muted", True))
            inner.addSpacing(60)
            self.campaign_layout.addWidget(empty)
        for campaign in campaigns:
            frame, inner = card()
            heading = QHBoxLayout()
            titles = QVBoxLayout()
            titles.addWidget(label(campaign.get("game_name", "Game"), "section", True))
            titles.addWidget(label(campaign.get("name", ""), "muted", True))
            heading.addLayout(titles, 1)
            badge = "Linked" if campaign.get("linked") else "Account not linked"
            heading.addWidget(label(badge, "muted"))
            inner.addLayout(heading)
            for drop in campaign.get("drops", []):
                row = QHBoxLayout()
                row.addWidget(label(drop.get("name", "Reward"), wrap=True), 1)
                state = "Claimed" if drop.get("is_claimed") else "Ignored" if drop.get("is_ignored") else "Not currently eligible" if drop.get("is_skipped") else f"{drop.get('current_minutes', 0)} / {drop.get('required_minutes', 0)} min"
                row.addWidget(label(state, "muted"))
                inner.addLayout(row)
                progress = QProgressBar()
                progress.setTextVisible(False)
                progress.setValue(100 if drop.get("is_claimed") else progress_percent(drop))
                inner.addWidget(progress)
            game = campaign.get("game_name", "")
            if game.casefold() not in selected:
                add = button("Add to mining list  +", lambda checked=False, name=game: self._add_campaign_game(name), "link")
                add.setEnabled(not self.settings_saving)
                inner.addWidget(add)
            if campaign.get("id"):
                inner.addWidget(button(
                    "Why am I not earning this?",
                    lambda checked=False, key=campaign["id"]: self.engine.submit("campaign_help", key),
                    "link",
                ))
            self.campaign_layout.addWidget(frame)
        self.campaign_layout.addStretch()

    def _history(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        heading = QHBoxLayout()
        heading.addWidget(label("A collection worth keeping.", "title"), 1)
        self.export_button = button("Export CSV", self._export_history, name="exportHistoryButton")
        self.export_button.setEnabled(False)
        heading.addWidget(self.export_button)
        layout.addLayout(heading)
        layout.addWidget(label("Your locally recorded claims. Recent 500 shown; CSV includes the full history.", "muted", True))
        self.history_empty = label("No rewards claimed yet. Your first one will appear here.", "muted", True)
        layout.addWidget(self.history_empty)
        self.history_table = QTableWidget(0, 3)
        self.history_table.setHorizontalHeaderLabels(["GAME", "REWARD", "CLAIMED"])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.history_table.verticalHeader().hide()
        self.history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.history_table.setAlternatingRowColors(False)
        self.history_table.setShowGrid(False)
        layout.addWidget(self.history_table, 1)
        return page

    def _activity(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        layout.addWidget(label("A window into your miner.", "title"))
        layout.addWidget(label("Live activity from the engine. Keep this PC awake while collecting.", "muted"))
        recap, recap_layout = card()
        recap_layout.addWidget(label("Overnight recap", "section"))
        self.recap_night = QComboBox()
        self.recap_night.setAccessibleName("Overnight recap date")
        self.recap_night.currentIndexChanged.connect(self._show_recap_night)
        self.recap_nights = {}
        recap_layout.addWidget(self.recap_night)
        self.recap_summary = label("", "muted", True)
        recap_layout.addWidget(self.recap_summary)
        self.recap_expired = QPlainTextEdit()
        self.recap_expired.setReadOnly(True)
        self.recap_expired.setMaximumHeight(96)
        self.recap_expired.setAccessibleName("Campaigns expired unfinished")
        recap_layout.addWidget(self.recap_expired)
        layout.addWidget(recap)
        self._render_recap({})
        self.activity_text = QPlainTextEdit()
        self.activity_text.setReadOnly(True)
        self.activity_text.setFont(QFont("Cascadia Code", 10))
        self.activity_text.setPlaceholderText("Activity will appear as your miner starts…")
        self.activity_text.setAccessibleName("Miner activity")
        layout.addWidget(self.activity_text, 1)
        return page

    def _render_recap(self, recap):
        current = self.recap_night.currentData()
        nights = {report["start"]: report for report in (recap, *recap.get("history", [])) if report}
        if tuple(nights) != tuple(self.recap_nights):
            self.recap_night.blockSignals(True)
            self.recap_night.clear()
            for key in nights:
                start = datetime.fromisoformat(key).astimezone()
                self.recap_night.addItem(f"Night of {start:%d %b %Y}", key)
            index = self.recap_night.findData(current) if current is not None else -1
            self.recap_night.setCurrentIndex(max(0, index))
            self.recap_night.blockSignals(False)
        self.recap_nights = nights
        self.recap_night.setVisible(len(nights) > 1)
        self._show_recap_night()

    def _show_recap_night(self):
        recap = self.recap_nights.get(self.recap_night.currentData())
        if not recap:
            self.recap_summary.setText("Connect Twitch to see activity from 22:00 to 08:00 local time.")
            self.recap_expired.clear()
            self.recap_expired.hide()
            return
        start = datetime.fromisoformat(recap["start"]).astimezone()
        end = datetime.fromisoformat(recap["end"]).astimezone()
        wait = MiningPlanner.duration(recap["waiting_ms"] // 60_000)
        names = recap["expired"]
        period = f"{start:%d %b %H:%M} to {end:%d %b %H:%M} local time"
        if recap["observed"]:
            summary = (f"{recap['watch_minutes']} confirmed watch min · {recap['claimed']} rewards claimed · "
                       f"{wait} waiting for eligible streams · {len(names)} campaigns expired unfinished")
        else:
            summary = "No activity was recorded for this window."
        self.recap_summary.setText(f"{period}\n{summary}")
        expired = "\n".join(names)
        if self.recap_expired.toPlainText() != expired:
            self.recap_expired.setPlainText(expired)
        self.recap_expired.setVisible(bool(names))

    def _settings(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(16)
        outer.addWidget(label("Make it yours.", "title"))
        outer.addWidget(label("Control what you collect and which games come first.", "muted"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(16)
        games, inner = card()
        inner.addWidget(label("Mining list", "section"))
        inner.addWidget(label("Drag to reorder, or use Move up / Move down. The first game has the highest priority.", "muted", True))
        add_row = QHBoxLayout()
        self.game_picker = QComboBox()
        self.game_picker.setEditable(True)
        self.game_picker.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.game_picker.setPlaceholderText("Choose or type a game…")
        self.game_picker.setAccessibleName("Game to add")
        game_editor = self.game_picker.lineEdit()
        assert game_editor is not None  # Editable combobox always owns its editor.
        game_editor.setPlaceholderText("Choose or type a game…")
        game_editor.returnPressed.connect(self._add_game)
        add_row.addWidget(self.game_picker, 1)
        add_row.addWidget(button("Add game", self._add_game, name="addGameButton"))
        inner.addLayout(add_row)
        self.games_list = QListWidget()
        self.games_list.setMinimumHeight(130)
        self.games_list.setMaximumHeight(180)
        self.games_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.games_list.setAccessibleName("Game mining priority")
        self.games_list.model().rowsMoved.connect(self._settings_edited)
        inner.addWidget(self.games_list)
        order = QHBoxLayout()
        order.addWidget(button("↑  Move up", lambda: self._move_game(-1)))
        order.addWidget(button("↓  Move down", lambda: self._move_game(1)))
        order.addStretch()
        order.addWidget(button("Remove", self._remove_game))
        inner.addLayout(order)
        self.strict_games = QCheckBox("Mine only games in this list")
        self.strict_games.toggled.connect(self._settings_edited)
        inner.addWidget(self.strict_games)
        inner.addWidget(label("Turn this off to include other eligible games after your selected games. An empty strict list can leave the miner idle.", "muted", True))
        layout.addWidget(games)
        policy, policy_layout = card()
        policy_layout.addWidget(label("Reward preferences", "section"))
        benefit_row = QHBoxLayout()
        self.benefits = {}
        for key, text in (("DIRECT_ENTITLEMENT", "In-game items"), ("BADGE", "Chat badges"), ("EMOTE", "Emotes"), ("UNKNOWN", "Other")):
            check = QCheckBox(text)
            check.toggled.connect(self._settings_edited)
            self.benefits[key] = check
            benefit_row.addWidget(check)
        policy_layout.addLayout(benefit_row)
        interval_row = QHBoxLayout()
        interval_row.addWidget(label("Minimum refresh interval", "muted"), 1)
        self.interval = QSpinBox()
        self.interval.setRange(1, 1440)
        self.interval.setSuffix(" min")
        self.interval.valueChanged.connect(self._settings_edited)
        self.interval.setAccessibleName("Minimum refresh interval in minutes")
        interval_row.addWidget(self.interval)
        policy_layout.addLayout(interval_row)
        layout.addWidget(policy)
        desktop, desktop_layout = card()
        desktop_layout.addWidget(label("Desktop behavior", "section"))
        self.desktop_options = {}
        for key, text in (
            ("automatic_queue", "Prioritize campaigns nearing expiry"),
            ("notifications", "Notify on claims and session issues"),
            ("close_to_tray", "Minimize and Close to tray"),
            ("start_at_login", "Launch when I sign into Windows"),
        ):
            checkbox = QCheckBox(text)
            checkbox.setChecked(self.preferences.values[key])
            checkbox.toggled.connect(self._desktop_option_edited)
            self.desktop_options[key] = checkbox
            desktop_layout.addWidget(checkbox)
        desktop_layout.addWidget(label("Game preferences always apply. In tray mode, Close keeps mining; use Quit in the tray menu to stop. Startup is optional and uses this executable's current location.", "muted", True))
        self.desktop_options_status = label("Desktop options are saved separately from mining preferences.", "muted", True)
        desktop_layout.addWidget(self.desktop_options_status)
        desktop_layout.addWidget(button("Save desktop options", self._save_desktop_options, name="saveDesktopOptionsButton"))
        layout.addWidget(desktop)
        account, account_layout = card()
        account_layout.addWidget(label("Your account & local data", "section"))
        account_layout.addWidget(label("Sessions, settings and reward history stay in your Windows user profile. Quit stops mining; tray mode can keep it running when you close the window.", "muted", True))
        row = QHBoxLayout()
        row.addWidget(button("Open data folder", self._open_data))
        row.addStretch()
        self.logout_button = button("Sign out of Twitch", self._logout, "danger", "logoutButton")
        self.logout_button.setEnabled(False)
        row.addWidget(self.logout_button)
        account_layout.addLayout(row)
        layout.addWidget(account)
        layout.addStretch()
        scroll.setWidget(container)
        outer.addWidget(scroll, 1)
        footer = QHBoxLayout()
        self.save_status = label("Settings are saved on this PC.", "muted")
        footer.addWidget(self.save_status, 1)
        self.save_button = button("Save changes", self._save_settings, "primary", "saveSettingsButton")
        self.save_button.setEnabled(False)
        footer.addWidget(self.save_button)
        outer.addLayout(footer)
        return page

    def _ready(self):
        self.engine_ready = True
        self.connect_button.setEnabled(True)
        self.export_button.setEnabled(True)
        self.engine_indicator.setText("●  Engine online")
        self.engine_indicator.setStyleSheet("color: #83cfb3;")
        self.status_line.setText("Your miner is ready. Connect Twitch to get started.")
        if hasattr(self.engine, "preferences"):
            self.engine.submit("desktop_policy", self.preferences.values["automatic_queue"])

    def _update(self, data):
        self.data = data
        connection = data.get("connection") or {"phase": "ready" if data.get("logged_in") else "signed_out", "message": "Connected." if data.get("logged_in") else "Sign in to connect Twitch."}
        self._render_connection(connection)
        self._render_queue(data.get("queue", []))
        self._render_mining_health(data.get("mining_health", {}))
        self.system_tray.update(data)
        logged_in = bool(data.get("logged_in"))
        self.refresh_button.setEnabled(logged_in and not self.closing)
        self.pause_button.setEnabled(logged_in and not self.closing)
        self.logout_button.setEnabled(logged_in and not self.login_busy)
        self.pause_button.setText("▶  Resume mining" if data.get("pause", {}).get("paused") else "Ⅱ  Pause mining")
        if not self.login_busy:
            self.login_browser.setVisible(not logged_in)
            self.login_browser_label.setVisible(not logged_in)
            self.hero_title.setText("You're connected." if logged_in else "Make every minute count.")
            self.hero_copy.setText("Your miner is following your game priorities.\nKeep this app open while it tracks your rewards." if logged_in else "Connect Twitch to discover campaigns, follow your\ngame priorities, and claim eligible earned rewards.")
            self.connect_button.setText("Twitch connected" if logged_in else "Connect Twitch  →")
            self.connect_button.setEnabled(self.engine_ready and not self.closing and not logged_in)
            renewal_error = data.get("session", {}).get("renewal_error")
            self.login_hint.setText(f"Session renewal needs attention ({renewal_error}). Use Retry saved session to recover without signing in again." if renewal_error else "Twitch connected · Session saved on this PC" if logged_in else "Secure browser sign-in · Session stored on this PC")
        self.status_line.setText(data.get("status", "Ready") if logged_in else "Waiting for Twitch sign-in. Your miner is ready.")
        campaigns = data.get("campaigns", [])
        numbers = (sum(bool(c.get("active")) for c in campaigns), data.get("total_claimed", 0), len(data.get("channels", [])))
        for widget, number in zip(self.metrics, numbers, strict=True):
            widget.setText(str(number) if logged_in or number else "—")
        current = data.get("progress")
        paused = data.get("pause", {}).get("paused", False)
        self.mining_title.setText(current.get("drop_name", "Reward") if current else "Mining paused" if paused else "Looking for your next drop" if logged_in else "Ready when you are")
        watching = next((c for c in data.get("channels", []) if c.get("watching")), None)
        if current:
            self.mining_detail.setText(f"{current.get('game_name', '')}  ·  {current.get('current_minutes', 0)} / {current.get('required_minutes', 0)} minutes" + (f"\nWatching {watching.get('name', '')}" if watching else ""))
            remaining = max(0, current.get("required_minutes", 0) - current.get("current_minutes", 0))
            forecast = next((row for row in data.get("queue", []) if row["id"] == current.get("drop_id")), None)
            extra = f"\nRemaining watch time: {MiningPlanner.duration(remaining)}"
            if forecast:
                deadline = datetime.fromisoformat(forecast["deadline"]).astimezone().strftime("%d %b, %H:%M")
                extra += f" · Ends {deadline} · {'May fit' if forecast['fits'] else 'At risk'}"
            self.mining_detail.setText(self.mining_detail.text() + extra)
        else:
            self.mining_detail.setText("Resume whenever you're ready." if paused else "Your eligible rewards will appear here as the inventory loads.\nChoose your games in Settings." if logged_in else "Sign in and choose your games.\nYour current reward will appear here.")
        self.mining_progress.setValue(progress_percent(current))
        games = data.get("settings", {}).get("games_to_watch", [])
        noun = "game" if len(games) == 1 else "games"
        self.queue_title.setText(f"{len(games)} {noun} in your list" if games else "Your games, your order.")
        self.queue_detail.setText("\n".join(f"{i+1:02}   {game}" for i, game in enumerate(games[:3])) if games else "Set a priority list to focus\non the rewards you want.")
        self._render_campaigns()
        self._render_history(data.get("history", []))
        self._render_recap(data.get("overnight_recap", {}))
        lines = "\n".join(data.get("lines", []))
        if lines != self.console_signature:
            self.console_signature = lines
            bar = self.activity_text.verticalScrollBar()
            at_bottom = bar.value() >= bar.maximum() - 5
            position = bar.value()
            self.activity_text.setPlainText(lines)
            bar.setValue(bar.maximum() if at_bottom else position)
        self._load_settings(data.get("settings", {}))

    def _render_history(self, history):
        signature = json.dumps(history, sort_keys=True)
        if signature == self.history_signature:
            return
        self.history_signature = signature
        self.history_empty.setVisible(not history)
        self.history_table.setRowCount(len(history))
        for row, entry in enumerate(history):
            claimed = entry.get("claimed_at", "")
            with suppress(ValueError):
                claimed = datetime.fromisoformat(claimed).astimezone().strftime("%d %b %Y, %H:%M")
            for column, value in enumerate((entry.get("game", ""), entry.get("drop_name", ""), claimed)):
                self.history_table.setItem(row, column, QTableWidgetItem(str(value)))
            self.history_table.setRowHeight(row, 48)

    def _desktop_option_edited(self):
        self.desktop_options_dirty = True
        self.desktop_options_status.setText("You have unsaved desktop options.")

    def _save_desktop_options(self):
        values = {key: checkbox.isChecked() for key, checkbox in self.desktop_options.items()}
        try:
            self.preferences.save(values)
        except (OSError, ValueError):
            self.desktop_options_status.setText("Could not save desktop options. Startup changes require the packaged executable in a writable location.")
            return
        self.desktop_options_dirty = False
        self.desktop_options_status.setText("Desktop options saved.")
        if self.engine_ready:
            self.engine.submit("desktop_policy", values["automatic_queue"])

    def _hide_to_tray(self):
        if not self.closing and not self.system_tray.hide_window():
            self.show_notice("The system tray is unavailable. Keep this window open while mining.")

    def _request_quit(self):
        self.force_quit = True
        self.close()

    def changeEvent(self, event):
        super().changeEvent(event)
        if (event.type() == QEvent.Type.WindowStateChange and self.isMinimized()
                and not self.closing and self.preferences.values["close_to_tray"]):
            QTimer.singleShot(0, self._hide_to_tray)

    def _load_settings(self, settings):
        signature = json.dumps(settings, sort_keys=True)
        if not settings or self.settings_dirty or self.settings_saving or signature == self.settings_signature:
            return
        self.settings_signature = signature
        self.games_list.clear()
        self.games_list.addItems(settings.get("games_to_watch", []))
        self.strict_games.blockSignals(True)
        self.strict_games.setChecked(settings.get("priority_list_only", True))
        self.strict_games.blockSignals(False)
        self.interval.blockSignals(True)
        self.interval.setValue(settings.get("minimum_refresh_interval_minutes", 30))
        self.interval.blockSignals(False)
        for key, checkbox in self.benefits.items():
            checkbox.blockSignals(True)
            checkbox.setChecked(settings.get("mining_benefits", {}).get(key, True))
            checkbox.blockSignals(False)
        self.game_picker.blockSignals(True)
        text = self.game_picker.currentText()
        self.game_picker.clear()
        self.game_picker.addItems(settings.get("games_available", []))
        self.game_picker.setCurrentText(text)
        self.game_picker.blockSignals(False)

    def _settings_edited(self, *_args):
        self.settings_dirty = True
        self.settings_revision += 1
        self.save_status.setText("You have unsaved changes.")
        self.save_button.setEnabled(self.engine_ready and not self.settings_saving)

    def _game_names(self):
        return [self.games_list.item(i).text() for i in range(self.games_list.count())]

    def _add_game(self):
        name = self.game_picker.currentText().strip()
        if not name:
            return
        if name.casefold() in {game.casefold() for game in self._game_names()}:
            self.show_notice("This game is already in your mining list.")
            return
        self.games_list.addItem(name)
        self.game_picker.setCurrentText("")
        self._settings_edited()

    def _move_game(self, direction):
        row = self.games_list.currentRow()
        target = row + direction
        if row < 0 or not 0 <= target < self.games_list.count():
            return
        item = self.games_list.takeItem(row)
        self.games_list.insertItem(target, item)
        self.games_list.setCurrentRow(target)
        self._settings_edited()

    def _remove_game(self):
        row = self.games_list.currentRow()
        if row >= 0:
            self.games_list.takeItem(row)
            self._settings_edited()

    def _save_settings(self):
        if self.settings_saving or not self.engine_ready:
            return
        self.settings_saving = True
        self.saving_revision = self.settings_revision
        self.save_button.setEnabled(False)
        self.save_status.setText("Saving…")
        self._render_campaigns()
        self.engine.submit("settings", {
            "games_to_watch": self._game_names(),
            "priority_list_only": self.strict_games.isChecked(),
            "mining_benefits": {key: checkbox.isChecked() for key, checkbox in self.benefits.items()},
            "minimum_refresh_interval_minutes": self.interval.value(),
        })

    def _add_campaign_game(self, name):
        if self.settings_saving:
            return
        if name.casefold() not in {game.casefold() for game in self._game_names()}:
            self.games_list.addItem(name)
            self._settings_edited()
        self.navigate(4)
        self.show_notice("Game added to your draft list. Save changes to apply it.")

    def _connect_twitch(self):
        if self.data.get("logged_in"):
            return
        if not self.engine_ready or self.login_busy:
            return
        self.login_busy = True
        self.login_cancelling = False
        self.login_stage = "connecting"
        self.login_clock.start()
        self.login_timer.start()
        self.banner.hide()
        self.toast_timer.stop()
        self.overview_scroll.verticalScrollBar().setValue(0)
        self.connect_button.setEnabled(False)
        self.connect_button.setText("Opening sign-in…")
        self.cancel_login.show()
        self.cancel_login.setEnabled(True)
        self.cancel_login.setText("Cancel")
        self.login_browser.setEnabled(False)
        self.login_hint.setText("Opening a separate browser profile for Twitch sign-in…")
        self.engine.submit("login", {"browser": self.login_browser.currentData()})

    def _finish_login(self):
        if (not self.login_busy or self.login_cancelling
                or self.login_stage not in ("login", "chromium_login", "firefox_login")):
            return
        self.finish_login.setEnabled(False)
        self.login_stage = "finishing"
        self.connect_button.setText("Finishing sign-in…")
        self.login_hint.setText("Closing your sign-in window normally. Verification and campaign loading continue automatically in the background.")
        self.engine.submit("finish_login")

    def _cancel_login(self):
        if not self.login_busy or self.login_cancelling:
            return
        self.login_cancelling = True
        self.finish_login.hide()
        self.cancel_login.setEnabled(False)
        self.cancel_login.setText("Closing…")
        self.connect_button.setText("Closing sign-in…")
        self.login_hint.setText("Closing the sign-in browser and releasing its temporary files…")
        self.engine.submit("cancel_login")

    def _login_tick(self):
        if self.login_busy and not self.login_cancelling and self.login_stage in ("login", "chromium_login", "firefox_login"):
            seconds = max(0, self.login_clock.elapsed() // 1000)
            self.connect_button.setText(f"Waiting for Twitch · {seconds // 60}:{seconds % 60:02}")
            if seconds >= 60:
                self.login_hint.setText("Complete Twitch sign-in, then select Finish sign-in here. Campaign data loads automatically. If verification keeps spinning, cancel and try another browser.")

    def _login_phase(self, phase):
        if not self.login_busy or self.login_cancelling:
            return
        self.login_stage = phase
        messages = {
            "connecting": "Preparing secure sign-in…",
            "login": "Sign in and complete Twitch verification in the browser. Then select Finish sign-in here; campaign data loads automatically.",
            "chromium_login": "Complete Twitch sign-in, then select Finish sign-in here. No campaign browsing is needed.",
            "firefox_login": "Complete Twitch sign-in, then select Finish sign-in here. No campaign browsing is needed.",
            "capturing": "Reading the signed-in session automatically in the background. No browsing is needed…",
            "sending": "Verifying the account and loading campaign access automatically…",
            "success": "Twitch connected. Loading your campaigns…",
        }
        self.login_hint.setText(messages.get(phase, "Completing secure Twitch sign-in…"))
        manual = phase in ("login", "chromium_login", "firefox_login")
        self.finish_login.setVisible(manual)
        self.finish_login.setEnabled(manual)
        self.connect_button.setText("Checking session…" if phase in ("capturing", "sending", "success") else "Waiting for Twitch…")

    def _login_finished(self, success, message):
        self.login_busy = False
        self.login_cancelling = False
        self.login_stage = ""
        self.login_timer.stop()
        self.login_browser.setEnabled(True)
        self.cancel_login.hide()
        self.finish_login.hide()
        self.connect_button.setEnabled(self.engine_ready and not success and not self.data.get("logged_in"))
        self.connect_button.setText("Twitch connected" if success else "Connect Twitch  →")
        self.login_hint.setText(message)
        self.show_notice(message, persistent=not success)

    def _command_finished(self, name, success, message):
        if name == "campaign_help" and success:
            dialog = QMessageBox(self)
            dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            dialog.setWindowTitle("Campaign troubleshooting")
            dialog.setTextFormat(Qt.TextFormat.PlainText)
            summary, _, details = message.partition("\n\n")
            dialog.setText(summary)
            if details:
                first, _, remaining = details.partition("\n\n")
                dialog.setInformativeText(first)
                if remaining:
                    dialog.setDetailedText(details)
            dialog.open()
            return
        if name == "settings":
            self.settings_saving = False
            if success and self.settings_revision == self.saving_revision:
                self.settings_dirty = False
                self.settings_signature = None
                self.save_status.setText("All changes saved.")
                self._load_settings(self.data.get("settings", {}))
            elif success:
                self.settings_dirty = True
                self.save_status.setText("Earlier changes saved. Your newer edits still need saving.")
            else:
                self.settings_dirty = True
                self.save_status.setText("Save failed. Your edits are still here. Try again.")
            self.save_button.setEnabled(self.settings_dirty and self.engine_ready)
            self._render_campaigns()
        if not success:
            if name == "login":
                self._login_finished(False, message)
            elif name == "finish_login":
                if (not self.login_busy or self.login_cancelling or self.data.get("logged_in")
                        or self.login_stage not in ("finishing", "login", "chromium_login", "firefox_login")):
                    return
                self.login_stage = "login"
                self.finish_login.setEnabled(True)
                self.connect_button.setText("Waiting for Twitch…")
                self.login_hint.setText(message)
            self.show_notice(message, persistent=True)

    def _toggle_pause(self):
        self.engine.submit("pause", not self.data.get("pause", {}).get("paused", False))

    def _logout(self):
        self.engine.submit("logout")

    def _export_history(self):
        filename, _filter = QFileDialog.getSaveFileName(self, "Export reward history", str(Path.home() / "Documents" / "Twitch drop history.csv"), "CSV files (*.csv)")
        if filename:
            self.export_path = Path(filename)
            self.engine.submit("export")

    def _write_export(self, content):
        if self.export_path is None:
            return
        try:
            self.export_path.write_text(content.lstrip("\ufeff"), encoding="utf-8-sig")
            self.show_notice("Reward history exported.")
        except OSError:
            self.show_notice("Could not save that file. Choose a writable folder and try again.", persistent=True)
        finally:
            self.export_path = None

    def _open_data(self):
        from PySide6.QtCore import QUrl

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(desktop_home())))

    def show_notice(self, message, persistent=False):
        self.banner_text.setText(message)
        self.banner.show()
        self.toast_timer.stop()
        if not persistent:
            self.toast_timer.start(7000)

    def _fatal(self, message):
        self.engine_ready = False
        self.connect_button.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.pause_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.logout_button.setEnabled(False)
        self.export_button.setEnabled(False)
        self.recover_button.setEnabled(False)
        if self.system_tray.icon is not None:
            self.system_tray.pause_action.setEnabled(False)
        self.engine_indicator.setText("●  Engine stopped")
        self.engine_indicator.setStyleSheet("color: #f0a3b0;")
        self.show_notice(message, persistent=True)

    def _engine_stopped(self):
        if self.closing:
            self.close()

    def closeEvent(self, event):
        if (self.engine.isRunning() and not self.closing and not self.force_quit
                and self.preferences.values["close_to_tray"] and self.system_tray.available):
            event.ignore()
            self._hide_to_tray()
            return
        if self.engine.isRunning():
            if not self.closing and (self.settings_dirty or self.desktop_options_dirty):
                answer = QMessageBox.question(self, "Unsaved changes", "Close without saving your settings changes?", QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
                if answer != QMessageBox.StandardButton.Discard:
                    self.force_quit = False
                    event.ignore()
                    return
            event.ignore()
            if not self.closing:
                self.closing = True
                self.setEnabled(False)
                self.status_line.setText("Closing the miner and its sign-in browser. Please wait…")
                self.engine.stop()
        else:
            self.system_tray.stop()
            event.accept()
