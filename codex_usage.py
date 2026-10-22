"""Read ChatGPT Work/Codex allowance data from the local Codex app server."""

from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


class UsageError(RuntimeError):
    """Raised when the local Codex app server cannot return usage data."""


@dataclass(frozen=True)
class UsageWindow:
    used_percent: int
    duration_minutes: int | None
    resets_at: int | None

    @property
    def remaining_percent(self) -> int:
        return max(0, min(100, 100 - self.used_percent))


@dataclass(frozen=True)
class MonthlyAllowance:
    limit: Decimal
    used: Decimal
    resets_at: int | None

    @property
    def remaining(self) -> Decimal:
        return max(Decimal(0), self.limit - self.used)

    @property
    def remaining_percent(self) -> float:
        return float(min(Decimal(100), self.remaining / self.limit * 100))


def _monthly(value: Any) -> MonthlyAllowance | None:
    if not isinstance(value, dict):
        return None
    try:
        limit, used = Decimal(str(value['limit'])), Decimal(str(value['used']))
        if not limit.is_finite() or not used.is_finite() or limit <= 0 or used < 0:
            return None
        reset = value.get('resetsAt')
        return MonthlyAllowance(limit, used, int(reset) if reset is not None else None)
    except (KeyError, InvalidOperation, TypeError, ValueError, OverflowError):
        return None


@dataclass(frozen=True)
class UsageSnapshot:
    plan: str
    primary: UsageWindow | None
    secondary: UsageWindow | None
    credit_balance: Decimal | None
    unlimited_credits: bool
    reached_type: str | None
    fetched_at: float
    monthly: MonthlyAllowance | None = None


def _window(value: Any) -> UsageWindow | None:
    if not isinstance(value, dict) or "usedPercent" not in value:
        return None
    try:
        used_percent = int(Decimal(str(value["usedPercent"])))
        duration = value.get("windowDurationMins")
        resets_at = value.get("resetsAt")
        return UsageWindow(
            used_percent=max(0, min(100, used_percent)),
            duration_minutes=int(duration) if duration is not None else None,
            resets_at=int(resets_at) if resets_at is not None else None,
        )
    except (InvalidOperation, TypeError, ValueError, OverflowError) as exc:
        raise UsageError("ข้อมูล Usage ที่ Codex ส่งกลับมาไม่ถูกต้อง") from exc


def _pick_rate_limits(result: dict[str, Any]) -> dict[str, Any] | None:
    """Prefer the Codex bucket while tolerating future bucket identifiers."""
    buckets = result.get("rateLimitsByLimitId")
    if isinstance(buckets, dict):
        codex = buckets.get("codex")
        if isinstance(codex, dict):
            return codex

        candidates = [value for value in buckets.values() if isinstance(value, dict)]
        candidates.sort(
            key=lambda value: (
                str(value.get("limitId", "")).lower() == "codex",
                isinstance(value.get("secondary"), dict),
                isinstance(value.get("primary"), dict),
            ),
            reverse=True,
        )
        if candidates:
            return candidates[0]

    legacy = result.get("rateLimits")
    return legacy if isinstance(legacy, dict) else None


def parse_rate_limits(result: dict[str, Any]) -> UsageSnapshot:
    """Convert an account/rateLimits/read result into a small stable model."""
    rate_limits = _pick_rate_limits(result)
    if rate_limits is None:
        raise UsageError("ไม่พบข้อมูล Rate Limits ในคำตอบจาก Codex")

    credits = rate_limits.get("credits")
    balance = None
    unlimited = False
    if isinstance(credits, dict):
        unlimited = bool(credits.get("unlimited", False))
        raw_balance = credits.get("balance")
        if raw_balance is not None:
            try:
                balance = Decimal(str(raw_balance))
            except InvalidOperation:
                balance = None

    primary = _window(rate_limits.get("primary"))
    secondary = _window(rate_limits.get("secondary"))
    monthly = _monthly(rate_limits.get("individualLimit"))
    if primary is None and secondary is None and monthly is None:
        raise UsageError("Codex ยังไม่ส่งข้อมูลรอบ Usage กลับมา")

    return UsageSnapshot(
        plan=str(rate_limits.get("planType") or result.get("planType") or "unknown"),
        primary=primary,
        secondary=secondary,
        credit_balance=balance,
        unlimited_credits=unlimited,
        reached_type=rate_limits.get("rateLimitReachedType"),
        fetched_at=time.time(),
        monthly=monthly,
    )


class _LineReader:
    def __init__(self, stream: Any) -> None:
        self.lines: queue.Queue[str | None] = queue.Queue()
        self.thread = threading.Thread(target=self._read, args=(stream,), daemon=True)
        self.thread.start()

    def _read(self, stream: Any) -> None:
        try:
            for line in stream:
                self.lines.put(line)
        finally:
            self.lines.put(None)

    def get(self, timeout: float) -> str:
        try:
            line = self.lines.get(timeout=timeout)
        except queue.Empty as exc:
            raise UsageError("Codex ตอบกลับช้าเกินกำหนด") from exc
        if line is None:
            raise UsageError("Codex app server ปิดการเชื่อมต่อ")
        return line


def _send(process: subprocess.Popen[str], payload: dict[str, Any]) -> None:
    if process.stdin is None:
        raise UsageError("เปิดช่องส่งข้อมูลไปยัง Codex ไม่สำเร็จ")
    process.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
    process.stdin.flush()


def _wait_for_id(reader: _LineReader, request_id: int, deadline: float) -> dict[str, Any]:
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise UsageError("Codex ตอบกลับช้าเกินกำหนด")
        raw = reader.get(remaining)
        try:
            message = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if message.get("id") != request_id:
            continue
        if "error" in message:
            detail = message["error"]
            if isinstance(detail, dict):
                detail = detail.get("message") or detail
            raise UsageError(f"Codex ตอบกลับด้วยข้อผิดพลาด: {detail}")
        result = message.get("result")
        if not isinstance(result, dict):
            raise UsageError("รูปแบบคำตอบจาก Codex ไม่ถูกต้อง")
        return result


def find_codex_executables() -> list[str]:
    """Find Codex even when a long-running widget has a stale Windows PATH."""
    candidates: list[Path] = []
    override = os.environ.get("CODEX_USAGE_WIDGET_CODEX")
    if override:
        candidates.append(Path(override).expanduser())

    for command in ("codex", "codex.exe"):
        found = shutil.which(command)
        if found:
            candidates.append(Path(found))

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        local = Path(local_app_data)
        candidates.extend(
            (
                local / "OpenAI" / "Codex" / "codex.exe",
                local / "Programs" / "Codex" / "codex.exe",
                local / "Microsoft" / "WindowsApps" / "codex.exe",
            )
        )
        versioned_bin = local / "OpenAI" / "Codex" / "bin"
        try:
            candidates.extend(
                sorted(
                    versioned_bin.glob("*/codex.exe"),
                    key=lambda path: path.stat().st_mtime,
                    reverse=True,
                )
            )
        except OSError:
            pass

    for variable in ("ProgramFiles", "ProgramFiles(x86)"):
        root = os.environ.get(variable)
        if root:
            candidates.append(Path(root) / "OpenAI" / "Codex" / "codex.exe")

    available: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            resolved = str(candidate.resolve(strict=True))
        except OSError:
            continue
        key = os.path.normcase(resolved)
        if key not in seen:
            seen.add(key)
            available.append(resolved)
    return available


def _query_with_executable(executable: str, timeout: float) -> UsageSnapshot:
    """Fetch one snapshot from one concrete Codex executable."""

    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        process = subprocess.Popen(
            [executable, "app-server", "--listen", "stdio://"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=creation_flags,
        )
    except OSError as exc:
        raise UsageError(f"เปิด Codex app server ไม่สำเร็จ: {exc}") from exc
    if process.stdout is None:
        process.kill()
        raise UsageError("เปิดช่องอ่านข้อมูลจาก Codex ไม่สำเร็จ")

    reader = _LineReader(process.stdout)
    deadline = time.monotonic() + timeout
    try:
        _send(
            process,
            {
                "id": 1,
                "method": "initialize",
                "params": {
                    "clientInfo": {"name": "chatgpt-usage-widget", "version": "1.0.0"},
                    "capabilities": {"experimentalApi": True},
                },
            },
        )
        _wait_for_id(reader, 1, deadline)
        _send(process, {"method": "initialized"})
        _send(process, {"id": 2, "method": "account/rateLimits/read"})
        try:
            result = _wait_for_id(reader, 2, deadline)
        except UsageError as exc:
            error_text = str(exc).lower()
            if not any(word in error_text for word in ("auth", "token", "401", "unauthor")):
                raise
            _send(
                process,
                {"id": 3, "method": "account/read", "params": {"refreshToken": True}},
            )
            _wait_for_id(reader, 3, deadline)
            _send(process, {"id": 4, "method": "account/rateLimits/read"})
            result = _wait_for_id(reader, 4, deadline)
        return parse_rate_limits(result)
    except OSError as exc:
        raise UsageError(f"เรียก Codex ไม่สำเร็จ: {exc}") from exc
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1.5)
            except subprocess.TimeoutExpired:
                process.kill()
        if process.stdin:
            process.stdin.close()
        if process.stdout:
            process.stdout.close()


def query_usage(timeout: float = 15.0) -> UsageSnapshot:
    """Fetch a snapshot, falling back across current and newly installed Codex builds."""
    executables = find_codex_executables()
    if not executables:
        raise UsageError("ไม่พบ Codex กรุณาเปิดหรือติดตั้ง Codex Desktop แล้วลองอีกครั้ง")

    errors: list[str] = []
    for executable in executables:
        try:
            return _query_with_executable(executable, timeout)
        except UsageError as exc:
            errors.append(str(exc))

    detail = errors[-1] if errors else "ไม่ทราบสาเหตุ"
    raise UsageError(f"เชื่อมต่อ Codex ไม่สำเร็จ: {detail}")
