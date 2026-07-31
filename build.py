"""Build CodexWeeklyWidget.exe with PyInstaller."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "codex_usage_widget.py"
ICON = ROOT / "codex.ico"


def main() -> None:
    if not SCRIPT.exists():
        raise SystemExit(f"Missing script: {SCRIPT}")
    if not ICON.exists():
        raise SystemExit(f"Missing icon: {ICON}")

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--windowed",
        "--name",
        "CodexWeeklyWidget",
        "--icon",
        str(ICON),
        "--hidden-import",
        "pystray._win32",
        str(SCRIPT),
    ]

    print("Running:")
    print(" ".join(f'\"{part}\"' if " " in part else part for part in command))
    subprocess.run(command, cwd=ROOT, check=True)
    print(f"\nBuild complete: {ROOT / 'dist' / 'CodexWeeklyWidget.exe'}")


if __name__ == "__main__":
    main()
