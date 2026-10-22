"""Ask Windows to launch the widget independently of the calling application."""
import os
from pathlib import Path
import subprocess

subprocess.run(
    [str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "schtasks.exe"),
     "/Run", "/TN", "CodexUsageRings"],
    creationflags=subprocess.CREATE_NO_WINDOW,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    check=True,
)
