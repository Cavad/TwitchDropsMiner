"""Native desktop preferences and optional per-user Windows startup registration."""

from __future__ import annotations

import json
import os
import sys
from contextlib import suppress
from pathlib import Path

from desktop.model import desktop_home


class StartupRegistration:
    KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
    NAME = "TwitchDropsMinerDesktop"

    @classmethod
    def configure(cls, enabled: bool, executable: Path | None = None) -> None:
        if sys.platform != "win32":
            if enabled:
                raise OSError("Windows startup is unavailable")
            return
        import winreg

        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, cls.KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                path = (executable or Path(sys.executable)).resolve()
                if not path.is_file() or '"' in str(path):
                    raise OSError("Executable is unavailable")
                command = f'"{path}" --start-in-tray'
                if len(command) > 260:
                    raise OSError("Executable path is too long for Windows startup")
                winreg.SetValueEx(key, cls.NAME, 0, winreg.REG_SZ, command)
            else:
                with suppress(FileNotFoundError):
                    winreg.DeleteValue(key, cls.NAME)


class DesktopPreferences:
    DEFAULTS = {"notifications": True, "close_to_tray": False, "start_at_login": False, "automatic_queue": True}

    def __init__(self, path: Path | None = None):
        self.path = path or desktop_home() / "desktop-preferences.json"
        self.values = dict(self.DEFAULTS)
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                self.values.update({key: raw[key] for key in self.DEFAULTS if type(raw.get(key)) is bool})
        except (OSError, ValueError):
            pass

    def save(self, values: dict[str, bool]) -> None:
        if set(values) != set(self.DEFAULTS) or any(type(value) is not bool for value in values.values()):
            raise ValueError("Invalid desktop preferences")
        previous = self.values
        changed_startup = values["start_at_login"] != previous["start_at_login"]
        if changed_startup and values["start_at_login"] and not getattr(sys, "frozen", False):
            raise OSError("Launch at sign-in is available in the packaged executable")
        if changed_startup:
            StartupRegistration.configure(values["start_at_login"])
        temporary = self.path.with_suffix(".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(json.dumps(values, indent=2), encoding="utf-8")
            os.replace(temporary, self.path)
        except OSError:
            with suppress(OSError):
                if changed_startup:
                    StartupRegistration.configure(previous["start_at_login"])
            with suppress(OSError):
                temporary.unlink(missing_ok=True)
            raise
        self.values = dict(values)
