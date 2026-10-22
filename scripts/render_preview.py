"""Render a documentation preview from synthetic data without querying an account."""
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))


def main():
    previous_home = os.environ.get("CODEX_HOME")
    with tempfile.TemporaryDirectory() as temporary:
        os.environ["CODEX_HOME"] = temporary
        import codex_usage_widget as ui
        from codex_usage import parse_rate_limits

        widget = ui.CodexOverlay.__new__(ui.CodexOverlay)
        widget.canvas = SimpleNamespace(delete=lambda *args: None, create_image=lambda *args, **kwargs: None)
        widget.tray_icon = None
        widget.activity_status = ui.ACTIVITY_READY
        widget.display_mode = "both"
        widget.widget_w = ui.WIDGET_W_BOTH
        # Keep the real card renderer; replace only Tk's image allocation.
        ui.ImageTk.PhotoImage = lambda image: image
        reset = int(time.time()) + 9 * 86400 + 18 * 3600
        monthly = parse_rate_limits({"rateLimits": {"individualLimit": {
            "limit": "5000", "used": "1500", "resetsAt": reset}}}).monthly
        widget._apply_data({
            "primary": {"remaining_percent": 72, "reset_after_seconds": 7200, "limit_window_seconds": 18000},
            "secondary": {"remaining_percent": 64, "reset_after_seconds": 259200, "limit_window_seconds": 604800},
            "primary_reset_time": "22/10 18:30",
            "secondary_reset_time": "27/10 09:00",
            "monthly": monthly,
        })
        image = widget.rendered_image.convert("RGBA")
        # The desktop renderer uses a chroma key for Windows transparency.
        pixels = [(0, 0, 0, 0) if (r, g, b) == (255, 0, 255) else (r, g, b, 255)
                  for r, g, b, _alpha in image.getdata()]
        image.putdata(pixels)
        destination = root / "assets" / "preview.png"
        destination.parent.mkdir(exist_ok=True)
        image.save(destination)
        print("Generated assets/preview.png using synthetic data")
        # Release the temporary log file before deleting its directory on Windows.
        import logging
        logging.shutdown()
    if previous_home is None:
        os.environ.pop("CODEX_HOME", None)
    else:
        os.environ["CODEX_HOME"] = previous_home


if __name__ == "__main__":
    main()
