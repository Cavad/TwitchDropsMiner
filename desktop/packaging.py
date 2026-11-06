"""Keep the host's Windows runtime out of the portable application's DLL bundle."""

from pathlib import PureWindowsPath


def keep_binary(destination: str) -> bool:
    name = PureWindowsPath(destination).name.casefold()
    # Qt uses Windows' unversioned ICU API. Other programs on the build machine's
    # PATH can ship ICU DLLs with the same filename but incompatible exports.
    return name not in {"icuuc.dll", "icuin.dll", "icudt.dll", "ucrtbase.dll"} and not name.startswith("api-ms-win-")
