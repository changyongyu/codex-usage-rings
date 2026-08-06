r"""Build CodexWeeklyWidget.exe on Windows.

Run:
    py build.py

The script automatically:
1. Creates .venv if needed.
2. Installs requirements.txt inside the virtual environment.
3. Runs PyInstaller.
4. Places CodexWeeklyWidget.exe in the repository root.
5. Removes PyInstaller's dist, build, and spec artifacts.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "codex_usage_widget.py"
ICON = ROOT / "codex.ico"
REQUIREMENTS = ROOT / "requirements.txt"
VENV_DIR = ROOT / ".venv"
VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"
SPEC_FILE = ROOT / "CodexWeeklyWidget.spec"
BUILT_EXE = DIST_DIR / "CodexWeeklyWidget.exe"
OUTPUT_EXE = ROOT / "CodexWeeklyWidget.exe"
INSIDE_VENV_FLAG = "--inside-venv"


def run(command: list[str]) -> None:
    print("\nRunning:")
    print(" ".join(f'"{part}"' if " " in part else part for part in command))
    subprocess.run(command, cwd=ROOT, check=True)


def validate_files() -> None:
    missing = [
        path.name
        for path in (SCRIPT, ICON, REQUIREMENTS)
        if not path.exists()
    ]

    if missing:
        raise SystemExit(
            "Missing required file(s): " + ", ".join(missing)
        )


def running_inside_project_venv() -> bool:
    try:
        return Path(sys.executable).resolve() == VENV_PYTHON.resolve()
    except OSError:
        return False


def prepare_venv() -> None:
    if not VENV_PYTHON.exists():
        print(f"Creating virtual environment: {VENV_DIR}")
        run([sys.executable, "-m", "venv", str(VENV_DIR)])
    else:
        print(f"Using existing virtual environment: {VENV_DIR}")

    print("\nInstalling/updating dependencies...")
    run([str(VENV_PYTHON), "-m", "pip", "install", "--upgrade", "pip"])
    run([
        str(VENV_PYTHON),
        "-m",
        "pip",
        "install",
        "-r",
        str(REQUIREMENTS),
    ])


def build_exe() -> None:
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
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

    print("\nBuilding CodexWeeklyWidget.exe...")
    run(command)

    if not BUILT_EXE.exists():
        raise SystemExit(
            "Build finished, but the expected EXE was not found:\n"
            f"{BUILT_EXE}"
        )

    os.replace(BUILT_EXE, OUTPUT_EXE)
    size_mb = OUTPUT_EXE.stat().st_size / (1024 * 1024)
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    SPEC_FILE.unlink(missing_ok=True)

    print("\nBuild complete!")
    print(f"EXE:  {OUTPUT_EXE}")
    print(f"Size: {size_mb:.1f} MB")


def main() -> None:
    if os.name != "nt":
        raise SystemExit("This build script supports Windows only.")

    validate_files()

    if (
        INSIDE_VENV_FLAG not in sys.argv
        and not running_inside_project_venv()
    ):
        prepare_venv()

        print("\nRestarting build inside .venv...")
        run([
            str(VENV_PYTHON),
            str(Path(__file__).resolve()),
            INSIDE_VENV_FLAG,
        ])
        return

    build_exe()


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        raise SystemExit(
            f"\nBuild failed. Command exited with code {exc.returncode}."
        ) from exc
