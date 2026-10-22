"""
Codex Usage Widget
------------------
Always-on-top desktop card for Codex 5h, weekly, and monthly allowances.
Default double-meter display: 250x268 px; launched via Windows Task Scheduler.

Python 3.11+ on Windows.
"""

import ctypes
from ctypes import wintypes
import json
import logging
import os
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageTk

try:
    import pystray
except ImportError as exc:
    raise SystemExit(
        "Missing dependency: pystray. Install it with: pip install pystray pillow"
    ) from exc

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CODEX_HOME = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
WIDGET_POS_JSON = CODEX_HOME / "widget_pos.json"
LOG_PATH = CODEX_HOME / "codex_widget.log"
INSTANCE_JSON = CODEX_HOME / "codex_widget_instance.json"
POLL_SECONDS = 60
ACTIVITY_POLL_SECONDS = 2
ACTIVITY_DISCOVERY_SECONDS = 5
ACTIVITY_BUSY_SECONDS = 30
ACTIVITY_SESSION_LOOKBACK_SECONDS = 6 * 60 * 60
ACTIVITY_MAX_SESSION_FILES = 40
TRAY_DOUBLE_CLICK_SECONDS = 0.35
_MUTEX_HANDLE = None
_OWNS_MUTEX = False

DARK = "#111820"
TRANSPARENT = "#ff00ff"
WHITE = "#EDF2F6"
GREEN = "#81D7C0"
YELLOW = "#E9BF75"
RED = "#F18082"
BLUE = "#96ADF7"
GOLD = "#75879B"
TRACK = "#2B3642"
INNER_TRACK = "#242D38"
TEXT_DIM = "#A2AFBD"

ACTIVITY_WORKING = "working"
ACTIVITY_READY = "ready"
ACTIVITY_CLOSED = "closed"
ACTIVITY_ERROR = "error"

_ACTIVITY_WORKING_EVENT_TYPES = {
    "agent_message",
    "agent_reasoning",
    "custom_tool_call",
    "custom_tool_call_output",
    "function_call",
    "function_call_output",
    "reasoning",
    "task_started",
    "tool_call",
    "tool_call_start",
    "turn_started",
    "user_message",
}
_ACTIVITY_COMPLETED_EVENT_TYPES = {
    "task_complete",
    "task_completed",
    "turn_aborted",
    "turn_complete",
    "turn_completed",
}
_ACTIVITY_WAITING_EVENT_TYPES = {
    "approval_requested",
    "request_user_input",
    "user_input_requested",
}

WIDGET_W_BOTH = 200
WIDGET_W_SINGLE = 110
WIDGET_H = 214
UI_SCALE = 1.25


def display_size(value):
    return round(value * UI_SCALE)

CARD_RADIUS = 22
RENDER_SCALE = 4


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _console_logging_requested() -> bool:
    value = os.environ.get("CODEX_WIDGET_CONSOLE", "")
    return value.lower() in {"1", "true", "yes", "on"}


def _console_stream():
    """Use console logging only when explicitly requested.

    A packaged GUI build must never allocate a terminal window. Logs are always
    written to codex_widget.log, so a console is unnecessary during normal use.
    """
    if not _console_logging_requested():
        return None

    if os.name == "nt":
        kernel32 = ctypes.windll.kernel32
        attached = bool(kernel32.GetConsoleWindow())
        if not attached:
            attached = bool(kernel32.AllocConsole())
        if attached:
            try:
                stream = open("CONOUT$", "w", encoding="utf-8", buffering=1)
                sys.stdout = stream
                sys.stderr = stream
                return stream
            except OSError:
                return None
    return sys.stderr


def _app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _setup_logging() -> Path:
    log_path = LOG_PATH
    handlers: list[logging.Handler] = []
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))
    except Exception:
        log_path = _app_dir() / "codex_widget.log"
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))

    console = _console_stream()
    if console is not None:
        handlers.append(logging.StreamHandler(console))

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s [%(threadName)s] %(message)s",
        handlers=handlers,
        force=True,
    )
    logging.info("Logging started at %s", log_path)
    logging.info(
        "Console logging requested=%s stream=%s stderr_isatty=%s",
        _console_logging_requested(),
        type(console).__name__,
        bool(getattr(console, "isatty", lambda: False)()) if console else False,
    )
    logging.info("Python=%s frozen=%s executable=%s", sys.version, getattr(sys, "frozen", False), sys.executable)
    logging.info("CODEX_HOME=%s INSTANCE_JSON=%s", CODEX_HOME, INSTANCE_JSON)
    return log_path


LOG_FILE = _setup_logging()


def _log_unhandled_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_traceback))


sys.excepthook = _log_unhandled_exception

if hasattr(threading, "excepthook"):
    def _log_thread_exception(args):
        logging.critical(
            "Unhandled thread exception in %s",
            args.thread.name if args.thread else "<unknown>",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    threading.excepthook = _log_thread_exception


# ---------------------------------------------------------------------------
# Single instance
# ---------------------------------------------------------------------------

def _pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if os.name == "nt":
        process_query_limited_information = 0x1000
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not handle:
            return False
        kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _read_instance_info() -> dict | None:
    try:
        if not INSTANCE_JSON.exists():
            return None
        with open(INSTANCE_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        logging.exception("Failed to read instance metadata from %s.", INSTANCE_JSON)
        return None


def _write_instance_info():
    try:
        CODEX_HOME.mkdir(parents=True, exist_ok=True)
        info = {
            "pid": os.getpid(),
            "executable": sys.executable,
            "frozen": bool(getattr(sys, "frozen", False)),
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "cwd": os.getcwd(),
            "log_file": str(LOG_FILE),
        }
        with open(INSTANCE_JSON, "w", encoding="utf-8") as f:
            json.dump(info, f, indent=2)
            f.write("\n")
        logging.info("Wrote instance metadata: %s.", info)
    except Exception:
        logging.exception("Failed to write instance metadata to %s.", INSTANCE_JSON)


def _remove_instance_info():
    if not _OWNS_MUTEX:
        return
    try:
        info = _read_instance_info()
        if info and int(info.get("pid", -1)) != os.getpid():
            logging.warning("Not removing instance metadata because it belongs to another pid: %s.", info)
            return
        INSTANCE_JSON.unlink(missing_ok=True)
        logging.info("Removed instance metadata from %s.", INSTANCE_JSON)
    except Exception:
        logging.exception("Failed to remove instance metadata from %s.", INSTANCE_JSON)


def ensure_single_instance() -> bool:
    """Return False when another widget process is already running."""
    global _OWNS_MUTEX
    if os.name != "nt":
        logging.debug("Single-instance mutex skipped on non-Windows OS.")
        _OWNS_MUTEX = True
        _write_instance_info()
        return True

    global _MUTEX_HANDLE
    kernel32 = ctypes.windll.kernel32
    _MUTEX_HANDLE = kernel32.CreateMutexW(None, True, "CodexUsageWidgetSingleInstance")
    last_error = kernel32.GetLastError()
    if last_error == 183:
        info = _read_instance_info()
        if info:
            pid = int(info.get("pid", -1))
            logging.info(
                "Another widget instance is already running; exiting. owner_pid=%s pid_running=%s info=%s.",
                pid,
                _pid_is_running(pid),
                info,
            )
        else:
            logging.info(
                "Another widget instance is already running; exiting. No instance metadata exists yet; "
                "look for an existing python.exe or codex_widget.exe process."
            )
        return False
    _OWNS_MUTEX = True
    _write_instance_info()
    logging.debug("Single-instance mutex acquired; GetLastError=%s.", last_error)
    return True


# ---------------------------------------------------------------------------
# Codex App Server adapter
# ---------------------------------------------------------------------------

def _format_reset(epoch_seconds, include_date: bool) -> str:
    if not epoch_seconds:
        return "--/-- --:--" if include_date else "--:--"
    try:
        dt = datetime.fromtimestamp(float(epoch_seconds))
        if include_date:
            return f"{dt.day:02d}/{dt.month:02d} {dt.strftime('%H:%M')}"
        return dt.strftime("%H:%M")
    except Exception:
        return "--/-- --:--" if include_date else "--:--"


def fetch_usage() -> dict:
    """Local deployment adapter using the installed Codex App Server."""
    from codex_usage import query_usage
    snapshot = query_usage(timeout=20)
    def window(value):
        if value is None:
            return None
        seconds = (value.duration_minutes or 0) * 60
        return {
            "used_percent": value.used_percent,
            "remaining_percent": value.remaining_percent,
            "window_minutes": value.duration_minutes,
            "limit_window_seconds": seconds,
            "reset_at": value.resets_at,
            "reset_after_seconds": max(0, (value.resets_at or int(time.time())) - int(time.time())),
        }
    primary, secondary = window(snapshot.primary), window(snapshot.secondary)
    result = {
        "plan": snapshot.plan,
        "limit_status": snapshot.reached_type or "OK",
        "primary": primary,
        "secondary": secondary,
        "monthly": snapshot.monthly,
        "primary_reset_time": _format_reset(primary["reset_at"] if primary else None, True),
        "secondary_reset_time": _format_reset(secondary["reset_at"] if secondary else None, True),
        "fetched_at": datetime.now().strftime("%H:%M:%S"),
    }
    logging.info("Usage fetched through Codex App Server successfully.")
    return result


# ---------------------------------------------------------------------------
# Overlay UI
# ---------------------------------------------------------------------------

def _limit_color(percent_left: float) -> str:
    if percent_left < 10:
        return RED
    if percent_left <= 30:
        return YELLOW
    return GREEN


def _hex_to_rgba(color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    color = color.lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16), alpha


def _font(size: int, bold: bool = False, symbol: bool = False) -> ImageFont.ImageFont:
    names = []
    if symbol:
        names.append(r"C:\Windows\Fonts\seguisym.ttf")
    names.append(r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf")
    names.append("arialbd.ttf" if bold else "arial.ttf")

    for name in names:
        try:
            return ImageFont.truetype(name, size * RENDER_SCALE)
        except OSError:
            continue
    return ImageFont.load_default()


def _reset_remaining_percent(window: dict) -> float | None:
    try:
        reset_after = float(window["reset_after_seconds"])
        window_seconds = float(window["limit_window_seconds"])
        if window_seconds <= 0:
            return None
        return max(0.0, min(100.0, (reset_after / window_seconds) * 100.0))
    except Exception:
        return None


def _load_widget_state() -> dict:
    try:
        if not WIDGET_POS_JSON.exists():
            logging.debug("Widget state file does not exist at %s.", WIDGET_POS_JSON)
            return {}
        with open(WIDGET_POS_JSON, "r", encoding="utf-8") as f:
            payload = json.load(f)
        state = {
            "x": int(payload["x"]),
            "y": int(payload["y"]),
            "locked": bool(payload.get("locked", False)),
            "always_on_top": bool(payload.get("always_on_top", True)),
            "display_mode": payload.get("display_mode", "both"),
        }
        logging.debug("Loaded widget state: %s.", state)
        return state
    except Exception:
        logging.exception("Failed to load widget state from %s; using defaults.", WIDGET_POS_JSON)
        return {}


def _save_widget_state(x: int, y: int, locked: bool, always_on_top: bool, display_mode: str):
    try:
        CODEX_HOME.mkdir(parents=True, exist_ok=True)
        with open(WIDGET_POS_JSON, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "x": x,
                    "y": y,
                    "locked": locked,
                    "always_on_top": always_on_top,
                    "display_mode": display_mode,
                },
                f,
            )
            f.write("\n")
        logging.debug(
            "Saved widget state: x=%s y=%s locked=%s always_on_top=%s display_mode=%s.",
            x,
            y,
            locked,
            always_on_top,
            display_mode,
        )
    except Exception:
        logging.exception("Failed to save widget state to %s.", WIDGET_POS_JSON)
        pass


def _get_monitor_rects() -> list[tuple[int, int, int, int]]:
    if os.name != "nt":
        return []

    rects: list[tuple[int, int, int, int]] = []

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    class MONITORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", RECT),
            ("rcWork", RECT),
            ("dwFlags", wintypes.DWORD),
        ]

    monitor_enum_proc = ctypes.WINFUNCTYPE(
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(RECT),
        ctypes.c_void_p,
    )

    def callback(monitor, _hdc, _rect, _data):
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if ctypes.windll.user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            work = info.rcWork
            rects.append((work.left, work.top, work.right, work.bottom))
        return 1

    try:
        ctypes.windll.user32.EnumDisplayMonitors(0, 0, monitor_enum_proc(callback), 0)
    except Exception:
        logging.exception("Failed to enumerate monitors.")
        return []

    logging.debug("Detected monitor work areas: %s.", rects)
    return rects


def _rect_intersects(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]


def _primary_monitor_rect(root: tk.Tk) -> tuple[int, int, int, int]:
    for rect in _get_monitor_rects():
        if rect[0] <= 0 < rect[2] and rect[1] <= 0 < rect[3]:
            return rect
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    return (0, 0, screen_width, screen_height)


def _position_on_available_screen(root: tk.Tk, x: int, y: int, widget_w: int) -> tuple[int, int, bool]:
    widget_rect = (x, y, x + widget_w, y + display_size(WIDGET_H))
    monitors = _get_monitor_rects()
    if monitors and any(_rect_intersects(widget_rect, monitor) for monitor in monitors):
        logging.debug("Saved widget position is visible: x=%s y=%s.", x, y)
        return x, y, False

    if not monitors:
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        if 0 <= x < screen_width - 24 and 0 <= y < screen_height - 24:
            logging.debug("Saved widget position is visible using Tk screen bounds: x=%s y=%s.", x, y)
            return x, y, False

    left, top, right, _bottom = _primary_monitor_rect(root)
    new_x = max(left + 20, right - widget_w - 24)
    new_y = top + 24
    logging.info("Saved widget position is off-screen; moving from (%s, %s) to (%s, %s).", x, y, new_x, new_y)
    return new_x, new_y, True


# ---------------------------------------------------------------------------
# Codex activity detection
# ---------------------------------------------------------------------------

def _codex_process_is_running() -> bool:
    """Return whether the Codex desktop app, ChatGPT app, or Codex CLI is open."""
    if os.name != "nt":
        return False

    th32cs_snapprocess = 0x00000002
    invalid_handle_value = ctypes.c_void_p(-1).value

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32FirstW.restype = wintypes.BOOL
    kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32NextW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    snapshot = kernel32.CreateToolhelp32Snapshot(th32cs_snapprocess, 0)
    if snapshot == invalid_handle_value:
        raise ctypes.WinError(ctypes.get_last_error())

    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        if not kernel32.Process32FirstW(snapshot, ctypes.byref(entry)):
            error = ctypes.get_last_error()
            if error == 18:  # ERROR_NO_MORE_FILES
                return False
            raise ctypes.WinError(error)

        while True:
            if entry.szExeFile.lower() in {"codex.exe", "chatgpt.exe"}:
                return True
            if not kernel32.Process32NextW(snapshot, ctypes.byref(entry)):
                error = ctypes.get_last_error()
                if error != 18:
                    raise ctypes.WinError(error)
                return False
    finally:
        kernel32.CloseHandle(snapshot)


def _parse_event_timestamp(value) -> float | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _classify_codex_event(root: dict) -> tuple[str, float | None] | None:
    """Classify one Codex transcript row as working, waiting, or completed."""
    payload = root.get("payload")
    if not isinstance(payload, dict):
        payload = {}

    event_type = payload.get("type") or root.get("type")
    if not isinstance(event_type, str):
        return None
    event_type = event_type.lower()

    phase = payload.get("phase") or root.get("phase")
    phase = phase.lower() if isinstance(phase, str) else ""
    status = payload.get("status") or payload.get("state") or root.get("status")
    status = status.lower() if isinstance(status, str) else ""
    name = payload.get("name")
    name = name.lower() if isinstance(name, str) else ""
    timestamp = _parse_event_timestamp(root.get("timestamp"))

    if (
        event_type in _ACTIVITY_COMPLETED_EVENT_TYPES
        or phase == "final_answer"
        or status in {"complete", "completed", "failed", "cancelled", "canceled"}
    ):
        return ACTIVITY_READY, timestamp

    if (
        event_type in _ACTIVITY_WAITING_EVENT_TYPES
        or name in {"request_user_input", "ask_user", "ask_user_question"}
        or status in {"waiting", "awaiting_approval", "needs_input"}
    ):
        return ACTIVITY_READY, timestamp

    if event_type in _ACTIVITY_WORKING_EVENT_TYPES:
        return ACTIVITY_WORKING, timestamp

    if event_type == "message" and payload.get("role") == "assistant":
        return ACTIVITY_WORKING, timestamp

    return None


def _latest_session_activity(path: Path) -> tuple[str, float] | None:
    """Read only the tail of a live JSONL transcript and return its latest useful event."""
    file_mtime = path.stat().st_mtime
    with open(path, "rb") as transcript:
        transcript.seek(0, os.SEEK_END)
        size = transcript.tell()
        start = max(0, size - 131_072)
        transcript.seek(start)
        data = transcript.read().decode("utf-8", errors="ignore")

    lines = data.splitlines()
    if start and lines:
        lines = lines[1:]

    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            root = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(root, dict):
            continue
        classified = _classify_codex_event(root)
        if classified is not None:
            status, timestamp = classified
            return status, timestamp if timestamp is not None else file_mtime
    return None


class CodexActivityScanner:
    def __init__(self):
        self._session_files: list[Path] = []
        self._last_discovery = 0.0

    def _discover_session_files(self, now: float) -> None:
        sessions_dir = CODEX_HOME / "sessions"
        if not sessions_dir.exists():
            self._session_files = []
            self._last_discovery = time.monotonic()
            return

        cutoff = now - ACTIVITY_SESSION_LOOKBACK_SECONDS
        candidates: list[tuple[float, Path]] = []
        for path in sessions_dir.rglob("*.jsonl"):
            try:
                modified = path.stat().st_mtime
            except OSError:
                continue
            if modified >= cutoff:
                candidates.append((modified, path))
        candidates.sort(reverse=True)
        self._session_files = [path for _modified, path in candidates[:ACTIVITY_MAX_SESSION_FILES]]
        self._last_discovery = time.monotonic()

    def scan(self) -> str:
        if not _codex_process_is_running():
            self._session_files = []
            self._last_discovery = 0.0
            return ACTIVITY_CLOSED

        now = time.time()
        if time.monotonic() - self._last_discovery >= ACTIVITY_DISCOVERY_SECONDS:
            self._discover_session_files(now)

        readable = 0
        read_errors = 0
        for path in self._session_files:
            try:
                activity = _latest_session_activity(path)
                readable += 1
            except OSError:
                read_errors += 1
                continue
            if activity is None:
                continue
            status, occurred_at = activity
            if status == ACTIVITY_WORKING and now - occurred_at <= ACTIVITY_BUSY_SECONDS:
                return ACTIVITY_WORKING

        if self._session_files and not readable and read_errors:
            raise OSError("Codex session transcripts could not be read")
        return ACTIVITY_READY


class CodexOverlay:
    def __init__(self):
        logging.info("Initializing CodexOverlay.")
        self.state = _load_widget_state()
        self.root = tk.Tk()
        logging.debug("Tk root created.")
        self.root.withdraw()
        self.root.overrideredirect(True)
        self.always_on_top = bool(self.state.get("always_on_top", True))
        self.root.wm_attributes("-topmost", self.always_on_top)
        self.root.configure(bg=TRANSPARENT)
        try:
            self.root.wm_attributes("-transparentcolor", TRANSPARENT)
        except tk.TclError:
            logging.exception("Transparent color attribute failed; falling back to solid background.")
            self.root.configure(bg=DARK)
        self.root.resizable(False, False)

        self.drag_offset_x = 0
        self.drag_offset_y = 0
        self.poll_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.locked = bool(self.state.get("locked", False))
        self.always_on_top_var = tk.BooleanVar(value=self.always_on_top)
        self.display_mode = self.state.get("display_mode", "both")
        if self.display_mode not in {"5h", "weekly", "both"}:
            self.display_mode = "both"
        self.display_mode_var = tk.StringVar(value=self.display_mode)
        self.widget_w = WIDGET_W_BOTH if self.display_mode == "both" else WIDGET_W_SINGLE
        self.primary_left = None
        self.weekly_left = None
        self.primary_time_left = None
        self.weekly_time_left = None
        self.primary_reset = "--/-- --:--"
        self.weekly_reset = "--/-- --:--"
        self.monthly = None
        self.error = False
        self.activity_status = ACTIVITY_CLOSED
        self.activity_scanner = CodexActivityScanner()
        self.tray_icon = None
        self.widget_visible = True
        self.tray_limit_mode = "5h"
        self.tray_click_lock = threading.Lock()
        self.tray_click_timer = None

        self._build_ui()
        self._start_tray_icon()
        self._restore_position()
        self.root.deiconify()
        self._start_activity_monitor()
        self._start_polling()
        logging.info("CodexOverlay initialized.")

    def _build_ui(self):
        logging.debug("Building widget UI.")
        self.canvas = tk.Canvas(
            self.root,
            width=display_size(self.widget_w),
            height=display_size(WIDGET_H),
            bg=TRANSPARENT,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="both", expand=True)

        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label=self._activity_menu_label(), state="disabled")
        self.activity_menu_index = self.menu.index("end")
        self.menu.add_command(label="立即刷新", command=self.refresh_now)
        self.menu.add_command(label=self._lock_menu_label(), command=self.toggle_lock)
        self.lock_menu_index = self.menu.index("end")
        self.menu.add_checkbutton(
            label="始终置顶",
            variable=self.always_on_top_var,
            command=self.toggle_always_on_top,
        )
        display_menu = tk.Menu(self.menu, tearoff=0)
        display_menu.add_radiobutton(
            label="仅 5 小时", value="5h", variable=self.display_mode_var, command=self.change_display_mode
        )
        display_menu.add_radiobutton(
            label="仅每周", value="weekly", variable=self.display_mode_var, command=self.change_display_mode
        )
        display_menu.add_radiobutton(
            label="双圆环", value="both", variable=self.display_mode_var, command=self.change_display_mode
        )
        self.menu.add_cascade(label="显示模式", menu=display_menu)
        self.menu.add_separator()
        self.menu.add_command(label="收起到托盘", command=self.minimize_to_tray)
        self.menu.add_command(label="退出", command=self.quit)

        self._bind_interactions(self.root)
        self._bind_interactions(self.canvas)
        self._draw()
        logging.debug("Widget UI built.")

    def _lock_menu_label(self) -> str:
        return "解锁位置" if self.locked else "锁定位置"

    def _activity_menu_label(self) -> str:
        labels = {
            ACTIVITY_WORKING: "Codex：运行中",
            ACTIVITY_READY: "Codex：就绪",
            ACTIVITY_CLOSED: "Codex：未检测到",
            ACTIVITY_ERROR: "Codex：检测异常",
        }
        return labels[self.activity_status]

    def _update_lock_control(self):
        self.menu.entryconfig(self.lock_menu_index, label=self._lock_menu_label())

    def _bind_interactions(self, widget):
        widget.bind("<ButtonPress-1>", self._drag_start)
        widget.bind("<B1-Motion>", self._drag_move)
        widget.bind("<ButtonRelease-1>", self._drag_end)
        widget.bind("<Double-Button-1>", self._double_click)
        widget.bind("<Button-3>", self._show_menu)

    def _double_click(self, _event):
        """Minimize the floating widget to the system tray."""
        self.minimize_to_tray()

    def _restore_position(self):
        self.root.update_idletasks()
        saved = _load_widget_state()
        if "x" in saved and "y" in saved:
            x, y, moved = _position_on_available_screen(self.root, saved["x"], saved["y"], display_size(self.widget_w))
        else:
            left, top, right, _bottom = _primary_monitor_rect(self.root)
            x = max(left + 20, right - display_size(self.widget_w) - 24)
            y = top + 24
            moved = True
        self.root.geometry(f"{display_size(self.widget_w)}x{display_size(WIDGET_H)}+{x}+{y}")
        logging.info("Widget positioned at x=%s y=%s moved=%s.", x, y, moved)
        if moved:
            self._save_state()

    def _drag_start(self, event):
        if self.locked:
            return
        self.drag_offset_x = event.x_root - self.root.winfo_x()
        self.drag_offset_y = event.y_root - self.root.winfo_y()

    def _drag_move(self, event):
        if self.locked:
            return
        x = event.x_root - self.drag_offset_x
        y = event.y_root - self.drag_offset_y
        self.root.geometry(f"+{x}+{y}")

    def _drag_end(self, event):
        if self.locked:
            return
        self._save_state()

    def toggle_lock(self):
        self.locked = not self.locked
        logging.info("Widget lock toggled: locked=%s.", self.locked)
        self._update_lock_control()
        self._save_state()

    def _apply_activity_status(self, status: str):
        if status == self.activity_status:
            return
        logging.info("Codex activity changed: %s -> %s.", self.activity_status, status)
        self.activity_status = status
        self.menu.entryconfig(self.activity_menu_index, label=self._activity_menu_label())
        self._draw()

    def _start_activity_monitor(self):
        logging.info("Starting Codex activity monitor; interval=%s seconds.", ACTIVITY_POLL_SECONDS)
        threading.Thread(target=self._activity_loop, name="activity-monitor", daemon=True).start()

    def _activity_loop(self):
        while not self.stop_event.is_set():
            try:
                status = self.activity_scanner.scan()
            except Exception:
                logging.exception("Codex activity scan failed.")
                status = ACTIVITY_ERROR
            try:
                self.root.after(0, lambda status=status: self._apply_activity_status(status))
            except (RuntimeError, tk.TclError):
                return
            if self.stop_event.wait(ACTIVITY_POLL_SECONDS):
                return

    def toggle_always_on_top(self):
        self.always_on_top = bool(self.always_on_top_var.get())
        logging.info("Always-on-top toggled: always_on_top=%s.", self.always_on_top)
        self.root.wm_attributes("-topmost", self.always_on_top)
        self._save_state()

    def _save_state(self):
        _save_widget_state(
            self.root.winfo_x(),
            self.root.winfo_y(),
            self.locked,
            self.always_on_top,
            self.display_mode,
        )


    def change_display_mode(self):
        new_mode = self.display_mode_var.get()
        if new_mode not in {"5h", "weekly", "both"}:
            return
        self.display_mode = new_mode
        self.widget_w = WIDGET_W_BOTH if new_mode == "both" else WIDGET_W_SINGLE
        if new_mode == "5h":
            self.tray_limit_mode = "5h"
        elif new_mode == "weekly":
            self.tray_limit_mode = "weekly"
        self.canvas.config(width=display_size(self.widget_w), height=display_size(WIDGET_H))
        self.root.geometry(f"{display_size(self.widget_w)}x{display_size(WIDGET_H)}+{self.root.winfo_x()}+{self.root.winfo_y()}")
        logging.info("Display mode changed: %s.", new_mode)
        self._save_state()
        self._draw()
        if self.tray_icon is not None:
            self.tray_icon.menu = self._build_tray_menu()
        self._update_tray_icon()

    def _show_menu(self, event):
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def _make_tray_image(self, value: str, color: str = "#000000") -> Image.Image:
        """Create a transparent tray icon containing the selected limit marker and value."""
        size = 256
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        text = str(value)
        # Use virtually the entire icon. Windows scales this master image down
        # to the current tray-icon size while preserving crisp edges.
        font_size = 215 if len(text) <= 2 else 168
        font = None
        for name in (r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\segoeuib.ttf", "arialbd.ttf"):
            try:
                font = ImageFont.truetype(name, font_size)
                break
            except OSError:
                continue
        if font is None:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), text, font=font, stroke_width=0)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = (size - text_w) / 2 - bbox[0]
        y = (size - text_h) / 2 - bbox[1]
        draw.text((x, y), text, fill=(0, 0, 0, 255), font=font)

        return image

    def _build_tray_menu(self):
        if self.display_mode == "both":
            items = [
                pystray.MenuItem("切换 5 小时 / 每周", self._tray_click, default=True),
                pystray.MenuItem("显示悬浮窗", self._tray_maximize),
            ]
        else:
            items = [pystray.MenuItem("显示悬浮窗", self._tray_maximize, default=True)]
        return pystray.Menu(
            *items,
            pystray.MenuItem("立即刷新", self._tray_refresh),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", self._tray_quit),
        )

    def _start_tray_icon(self):
        logging.info("Starting system tray icon.")
        self.tray_icon = pystray.Icon(
            "CodexUsageWidget",
            self._make_tray_image("--"),
            "5h limit : --% | reset --/-- --:--\nWeekly limit : --% | reset --/-- --:--",
            self._build_tray_menu(),
        )
        self.tray_icon.run_detached()

    def _update_tray_icon(self):
        if self.tray_icon is None:
            return

        if self.error:
            value = "!"
            color = "#000000"
            if self.display_mode == "5h":
                title = "5h limit : error | reset --/-- --:--"
            elif self.display_mode == "weekly":
                title = "Weekly limit : error | reset --/-- --:--"
            else:
                title = "5h limit : error | reset --/-- --:--\nWeekly limit : error | reset --/-- --:--"
        else:
            primary_value = "--" if self.primary_left is None else str(int(round(float(self.primary_left))))
            weekly_value = "--" if self.weekly_left is None else str(int(round(float(self.weekly_left))))
            if self.display_mode == "5h":
                value = primary_value
                title = f"5h limit : {primary_value}% | reset {self.primary_reset}"
            elif self.display_mode == "weekly":
                value = weekly_value
                title = f"Weekly limit : {weekly_value}% | reset {self.weekly_reset}"
            else:
                value = primary_value if self.tray_limit_mode == "5h" else weekly_value
                title = (
                    f"5h limit : {primary_value}% | reset {self.primary_reset}\n"
                    f"Weekly limit : {weekly_value}% | reset {self.weekly_reset}"
                )
            color = "#000000"

        try:
            self.tray_icon.icon = self._make_tray_image(value, color)
            self.tray_icon.title = title
        except Exception:
            logging.exception("Failed to update tray icon.")

    def _tray_toggle_limit(self, _icon=None, _item=None):
        if self.display_mode != "both":
            return
        self.tray_limit_mode = "weekly" if self.tray_limit_mode == "5h" else "5h"
        logging.info("Tray limit display toggled: mode=%s.", self.tray_limit_mode)
        self._update_tray_icon()

    def _tray_click(self, _icon=None, _item=None):
        """Treat one click as a toggle and two quick clicks as maximize."""
        with self.tray_click_lock:
            if self.tray_click_timer is not None and self.tray_click_timer.is_alive():
                self.tray_click_timer.cancel()
                self.tray_click_timer = None
                double_click = True
            else:
                self.tray_click_timer = threading.Timer(
                    TRAY_DOUBLE_CLICK_SECONDS,
                    self._tray_single_click,
                )
                self.tray_click_timer.daemon = True
                self.tray_click_timer.start()
                double_click = False

        if double_click:
            self.root.after(0, self.maximize_from_tray)

    def _tray_single_click(self):
        with self.tray_click_lock:
            self.tray_click_timer = None
        if self.display_mode == "both":
            self._tray_toggle_limit()

    def _tray_maximize(self, _icon=None, _item=None):
        self.root.after(0, self.maximize_from_tray)

    def _tray_refresh(self, _icon=None, _item=None):
        self.root.after(0, self.refresh_now)

    def _tray_quit(self, _icon=None, _item=None):
        self.root.after(0, self.quit)

    def minimize_to_tray(self):
        logging.info("Minimizing widget to tray.")
        self._save_state()
        self.widget_visible = False
        self.root.withdraw()

    def maximize_from_tray(self):
        logging.info("Restoring widget from tray.")
        self.widget_visible = True
        self.root.deiconify()
        self.root.lift()
        if self.always_on_top:
            self.root.wm_attributes("-topmost", True)
        self.root.after(100, lambda: self.root.wm_attributes("-topmost", self.always_on_top))

    def _set_loading(self):
        self.error = False
        self.primary_left = None
        self.weekly_left = None
        self.primary_time_left = None
        self.weekly_time_left = None
        self.primary_reset = "--/-- --:--"
        self.weekly_reset = "--/-- --:--"
        self.monthly = None
        self._draw()
        self._update_tray_icon()

    def _apply_data(self, data: dict):
        logging.debug("Applying usage data to UI: %s.", data)
        primary = data.get("primary") or {}
        secondary = data.get("secondary") or {}
        primary_left = primary.get("remaining_percent")
        weekly_left = secondary.get("remaining_percent")
        self.monthly = data.get("monthly")

        # Both missing -- genuine error
        if primary_left is None and weekly_left is None and self.monthly is None:
            logging.error("Usage payload had no primary or weekly remaining percent: %s.", data)
            self._apply_error()
            return

        self.error = False
        self.primary_left = primary_left
        self.weekly_left = weekly_left
        self.primary_time_left = _reset_remaining_percent(primary) if primary else None
        self.weekly_time_left = _reset_remaining_percent(secondary) if secondary else None
        self.primary_reset = data.get("primary_reset_time", "--/-- --:--")
        self.weekly_reset = data.get("secondary_reset_time", "--/-- --:--")
        self._draw()
        self._update_tray_icon()

    def _apply_error(self):
        logging.info("Showing error state in widget.")
        self.error = True
        self._draw()
        self._update_tray_icon()

    def _draw_meter_image(
        self,
        draw: ImageDraw.ImageDraw,
        cx: int,
        cy: int,
        percent: float | None,
        time_percent: float | None,
        title: str,
        reset_text: str,
        color: str,
    ):
        s = RENDER_SCALE
        value = 0.0 if percent is None else max(0.0, min(100.0, float(percent)))
        time_value = 0.0 if time_percent is None else max(0.0, min(100.0, float(time_percent)))
        quota_arc_end = -90 + value * 3.6
        time_arc_end = -90 + time_value * 3.6

        title_font = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 11 * s)
        percent_font = _font(25, bold=True)
        reset_font = _font(9)

        draw.text((cx * s, 16 * s), title, fill=_hex_to_rgba(TEXT_DIM), font=title_font, anchor="mm")

        outer_r = 37
        inner_r = 30
        outer = tuple(v * s for v in (cx - outer_r, cy - outer_r, cx + outer_r, cy + outer_r))
        inner = tuple(v * s for v in (cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r))

        def arc(bounds, radius, fraction, stroke, tint):
            draw.arc(bounds, start=0, end=360, fill=_hex_to_rgba(TRACK if radius == outer_r else INNER_TRACK), width=stroke*s)
            if fraction <= 0:
                return
            end = -90 + fraction * 3.6
            draw.arc(bounds, start=-90, end=end, fill=_hex_to_rgba(tint), width=stroke*s)
            from math import cos, sin, radians
            center_radius = (radius-stroke/2)*s
            cap = stroke*s/2
            for angle in (-90, end):
                px, py = cx*s + center_radius*cos(radians(angle)), cy*s + center_radius*sin(radians(angle))
                draw.ellipse((px-cap, py-cap, px+cap, py+cap), fill=_hex_to_rgba(tint))
        arc(outer, outer_r, value, 5, color)
        arc(inner, inner_r, time_value, 2, GOLD)

        number = "—" if percent is None else f"{value:.0f}"
        unit_font = _font(11)
        number_width = draw.textlength(number, font=percent_font)
        unit_width = draw.textlength("%", font=unit_font) if percent is not None else 0
        x = cx*s - (number_width+unit_width+2*s)/2
        draw.text((x, (cy+1)*s), number, fill=_hex_to_rgba(WHITE), font=percent_font, anchor="lm")
        if percent is not None:
            draw.text((x+number_width+2*s, (cy+5)*s), "%", fill=_hex_to_rgba(TEXT_DIM), font=unit_font, anchor="lm")
        draw.text((cx*s, 115*s), reset_text, fill=_hex_to_rgba(TEXT_DIM), font=reset_font, anchor="mm")

    def _draw_monthly(self, draw):
        s = RENDER_SCALE
        left, right = 18, self.widget_w - 18
        compact = self.widget_w < WIDGET_W_BOTH
        def font(size):
            return ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", size * s)
        def text(x, y, value, fill=TEXT_DIM, anchor="lm", size=10):
            draw.text((x*s, y*s), value, font=font(size), fill=_hex_to_rgba(fill), anchor=anchor)
        draw.rounded_rectangle((10*s, 130*s, (self.widget_w-10)*s, 208*s), radius=12*s, fill=_hex_to_rgba("#1A2530"))
        text(left, 144, "月度额度", size=9 if compact else 11)
        monthly = self.monthly
        value = monthly.remaining_percent if monthly else None
        color = "#81D7C0" if value is None or value > 30 else _limit_color(value)
        text(right, 144, "—" if value is None else f"{value:.0f}%", color, "rm", size=9 if compact else 11)
        bounds = (left*s, 159*s, right*s, 166*s)
        draw.rounded_rectangle(bounds, radius=3*s, fill=_hex_to_rgba(TRACK))
        if value is not None and value > 0:
            fill_right = left*s + (right-left)*s*value/100
            draw.rounded_rectangle((left*s, 159*s, fill_right, 166*s),
                                   radius=min(3*s, (fill_right-left*s)/2), fill=_hex_to_rgba(color))
        amount = "额度暂不可用" if monthly is None else f"{monthly.remaining:,.0f} / {monthly.limit:,.0f}"
        text(left, 183, amount if compact or monthly is None else f"剩余 {amount}", WHITE, size=8 if compact else 11)
        if monthly is None or monthly.resets_at is None:
            reset = "重置时间未知"
        else:
            seconds = max(0, monthly.resets_at - int(time.time()))
            days, seconds = divmod(seconds, 86400)
            hours, seconds = divmod(seconds, 3600)
            minutes = seconds // 60
            reset = f"{days}天{hours}小时后重置" if days else f"{hours}小时{minutes}分后重置"
            if monthly.resets_at <= time.time():
                reset = "等待额度更新"
        text(left, 202, reset, size=7 if compact else 10)

    def _draw(self):
        self.canvas.delete("all")

        s = RENDER_SCALE
        image = Image.new("RGBA", (self.widget_w * s, WIDGET_H * s), _hex_to_rgba(DARK))
        draw = ImageDraw.Draw(image)
        # A restrained vertical surface gradient, rendered at native oversampling.
        for y in range(WIDGET_H*s):
            t = y / max(1, WIDGET_H*s-1)
            rgb = tuple(round(a+(b-a)*t) for a,b in zip((25,33,44),(15,21,29)))
            draw.line((0,y,self.widget_w*s,y), fill=rgb+(255,))

        dot_x = (self.widget_w - 13) * s
        dot_y = 13 * s
        dot_r = 2.5 * s
        dot_bounds = (dot_x - dot_r, dot_y - dot_r, dot_x + dot_r, dot_y + dot_r)
        activity_colors = {
            ACTIVITY_WORKING: YELLOW,
            ACTIVITY_READY: GREEN,
            ACTIVITY_ERROR: RED,
        }
        if self.activity_status == ACTIVITY_CLOSED:
            draw.ellipse(dot_bounds, outline=_hex_to_rgba(TEXT_DIM), width=max(1, s))
        else:
            draw.ellipse(dot_bounds, fill=_hex_to_rgba(activity_colors[self.activity_status]))

        if self.error:
            draw.text(
                ((self.widget_w // 2) * s, (WIDGET_H // 2) * s),
                "ERR",
                fill=_hex_to_rgba(RED),
                font=_font(24, bold=True),
                anchor="mm",
            )
            self._show_rendered(image)
            return

        primary_color = BLUE if self.primary_left is None else _limit_color(self.primary_left)
        weekly_color = BLUE if self.weekly_left is None or self.weekly_left > 30 else _limit_color(self.weekly_left)
        if self.display_mode in {"5h", "both"}:
            self._draw_meter_image(
                draw,
                55,
                66,
                self.primary_left,
                self.primary_time_left,
                "5 小时",
                self.primary_reset,
                primary_color,
            )
        if self.display_mode == "weekly":
            weekly_cx = 55
        else:
            weekly_cx = 145
        if self.display_mode in {"weekly", "both"}:
            self._draw_meter_image(
                draw,
                weekly_cx,
                66,
                self.weekly_left,
                self.weekly_time_left,
                "每周",
                self.weekly_reset,
                weekly_color,
            )

        self._draw_monthly(draw)
        self._show_rendered(image)

    def _show_rendered(self, image: Image.Image):
        width, height = display_size(self.widget_w), display_size(WIDGET_H)
        image = image.resize((width, height), Image.Resampling.LANCZOS).convert("RGB")
        keyed = Image.new("RGB", (width, height), _hex_to_rgba(TRANSPARENT)[:3])
        mask = Image.new("L", (width, height), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle(
            (4, 4, width - 4, height - 4),
            radius=display_size(CARD_RADIUS),
            fill=255,
        )
        keyed.paste(image, (0, 0), mask)
        ImageDraw.Draw(keyed).rounded_rectangle((4, 4, width-4, height-4), radius=display_size(CARD_RADIUS), outline="#35414F", width=1)
        self.rendered_image = ImageTk.PhotoImage(keyed)
        self.canvas.create_image(0, 0, image=self.rendered_image, anchor="nw")

    def refresh_now(self):
        logging.info("Manual refresh requested.")
        threading.Thread(target=self._poll_once, name="manual-refresh", daemon=True).start()

    def _start_polling(self):
        logging.info("Starting polling thread; interval=%s seconds.", POLL_SECONDS)
        self._set_loading()
        threading.Thread(target=self._poll_loop, name="usage-poll", daemon=True).start()

    def _poll_loop(self):
        logging.debug("Polling loop started.")
        self._poll_once()
        while not self.stop_event.wait(POLL_SECONDS):
            self._poll_once()
        logging.debug("Polling loop stopped.")

    def _poll_once(self):
        if not self.poll_lock.acquire(blocking=False):
            logging.debug("Skipping poll because another poll is already running.")
            return
        try:
            logging.debug("Poll started.")
            data = fetch_usage()
            self.root.after(0, lambda data=data: self._apply_data(data))
        except Exception:
            logging.exception("Usage poll failed.")
            self.root.after(0, self._apply_error)
        finally:
            self.poll_lock.release()
            logging.debug("Poll finished.")

    def quit(self):
        logging.info("Quit requested.")
        (Path(os.environ.get("LOCALAPPDATA", Path.home())) / "CodexUsageRings").mkdir(parents=True, exist_ok=True)
        (Path(os.environ.get("LOCALAPPDATA", Path.home())) / "CodexUsageRings" / "stop.requested").touch()
        self.stop_event.set()
        with self.tray_click_lock:
            if self.tray_click_timer is not None:
                self.tray_click_timer.cancel()
                self.tray_click_timer = None
        if self.tray_icon is not None:
            try:
                self.tray_icon.stop()
            except Exception:
                logging.exception("Failed to stop tray icon cleanly.")
            self.tray_icon = None
        self.root.destroy()

    def run(self):
        logging.info("Entering Tk mainloop.")
        self.root.mainloop()
        logging.info("Tk mainloop exited.")


def main():
    logging.info("codex_widget startup begins.")
    try:
        if not ensure_single_instance():
            sys.exit(0)
        CodexOverlay().run()
    except Exception:
        logging.critical("Fatal startup/runtime exception.", exc_info=True)
        raise
    finally:
        _remove_instance_info()
        logging.info("codex_widget process exiting.")


if __name__ == "__main__":
    main()
