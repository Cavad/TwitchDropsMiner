# Third-party components

The application source retains the upstream MIT license in `LICENSE`.
The Windows EXE also packages unmodified third-party Python and Qt libraries.
Their own license terms and notices continue to apply.

- Qt for Python / PySide6 and Shiboken6: the installed distribution metadata lists
  `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`. See the
  [Qt for Python licenses](https://doc.qt.io/qtforpython-6/licenses.html) and
  [corresponding source repository](https://code.qt.io/cgit/pyside/pyside-setup.git/).
- Python: [Python license and source](https://www.python.org/psf/license/).
- PyInstaller: [license and bootloader exception](https://pyinstaller.org/en/stable/license.html).
- Runtime Python dependencies and exact versions are recorded in `uv.lock`;
  Windows UI/build dependencies are pinned in `packaging/desktop-requirements.txt`
  and `packaging/login-helper-requirements.txt`.

The executable includes installed dependency metadata and license files. This fork's
source and packaging instructions are available for rebuilding with modified
libraries; do not remove applicable third-party notices when redistributing.
