"""Keep the local rings widget running until the user explicitly quits."""
import ctypes
from ctypes import wintypes
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import subprocess
import sys
import time


def main():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    mutex = kernel.CreateMutexW(None, False, "Local\\CodexUsageRingsSupervisor")
    if not mutex:
        raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error() == 183:
        kernel.CloseHandle(mutex)
        return
    state = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "CodexUsageRings"
    state.mkdir(parents=True, exist_ok=True)
    log = RotatingFileHandler(state / "launcher.log", maxBytes=262144, backupCount=2, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, handlers=[log], format="%(asctime)s %(message)s")
    stop = state / "stop.requested"
    stop.unlink(missing_ok=True)
    root = Path(__file__).resolve().parent
    interpreter = Path(sys.executable).with_name("pythonw.exe")
    if not interpreter.exists():
        interpreter = Path(sys.executable)
    failures = 0
    try:
        while not stop.exists():
            started = time.monotonic()
            try:
                child = subprocess.Popen([str(interpreter), str(root / "codex_usage_widget.py")], cwd=root,
                                         creationflags=subprocess.CREATE_NO_WINDOW)
                (state / "child.pid").write_text(str(child.pid), encoding="ascii")
                logging.info("Widget started: pid=%s", child.pid)
                result = child.wait()
                logging.info("Widget ended: pid=%s exit=%s", child.pid, result)
            except OSError:
                logging.exception("Unable to start widget")
            if stop.exists():
                logging.info("User requested exit; automatic restart stopped")
                break
            failures = failures + 1 if time.monotonic() - started < 60 else 0
            delay = min(60, 5 * 2 ** min(failures, 4))
            logging.info("Unexpected exit; restarting in %s seconds", delay)
            for _ in range(delay):
                if stop.exists():
                    break
                time.sleep(1)
    finally:
        (state / "child.pid").unlink(missing_ok=True)
        kernel.CloseHandle(mutex)


if __name__ == "__main__":
    main()
