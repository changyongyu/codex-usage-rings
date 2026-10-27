"""Render both shipping styles with deterministic synthetic data; no account access."""
import ast
from datetime import datetime
from pathlib import Path
import sys

from PIL import Image

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from codex_usage import parse_rate_limits
from widget_styles import HEIGHT, WIDTH_BOTH, render_card


def sample_data():
    now = datetime(2026, 10, 26, 17).timestamp()
    monthly = parse_rate_limits({"rateLimits": {"individualLimit": {
        "limit": "5000", "used": "1500", "resetsAt": int(now + 9*86400 + 18*3600)}}}).monthly
    return dict(primary=72, weekly=64, primary_reset=now+102*60,
                weekly_reset=datetime(2026, 10, 29, 8).timestamp(),
                monthly=monthly, updated_at=now, now=now)


def main():
    config = ast.parse((root / "codex_usage_widget.py").read_text(encoding="utf-8-sig"))
    scale = next(ast.literal_eval(node.value) for node in config.body
                 if isinstance(node, ast.Assign)
                 and any(isinstance(target, ast.Name) and target.id == "UI_SCALE" for target in node.targets))
    for style, filename in (("mondrian", "preview.png"), ("memphis", "preview-memphis.png")):
        image = render_card(style=style, **sample_data())
        image = image.resize((round(WIDTH_BOTH*scale), round(HEIGHT*scale)), Image.Resampling.LANCZOS)
        destination = root / "assets" / filename
        destination.parent.mkdir(exist_ok=True)
        image.save(destination)
        print(f"Generated assets/{filename} using synthetic data")


if __name__ == "__main__":
    main()
