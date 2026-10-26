"""Account-independent Pillow renderer for the two desktop card styles."""
from datetime import datetime
from functools import lru_cache
from math import ceil, cos, radians, sin
import time

from PIL import Image, ImageChops, ImageDraw, ImageFont

DEFAULT_STYLE = "mondrian"
STYLE_NAMES = {"mondrian": "蒙德里安", "memphis": "孟菲斯波点"}
WIDTH_BOTH, WIDTH_SINGLE, HEIGHT = 292, 212, 396
RENDER_SCALE = 4

PALETTES = {
    "mondrian": dict(bg="#FAF6E9", ink="#181919", muted="#54534B", track="#DED7C7",
                     border="#171818", shadow="#171818", five="#D63B31",
                     week_bg="#1643A1", week_ink="#FFF8E5", week_muted="#E2E9F6",
                     week_track="#5478B9", week="#F6D244", month_bg="#F2CC3C",
                     month_ink="#171818", month_muted="#414032", month_track="#D6AE32",
                     month="#1848A8"),
    "memphis": dict(bg="#F6EEDD", ink="#202333", muted="#535364", track="#D9CDB9",
                    border="#202333", shadow="#2657AB", five="#CF413B",
                    week_bg="#A6D5CC", week_ink="#202333", week_muted="#344E56",
                    week_track="#7FB9B1", week="#214DA7", month_bg="#F4D445",
                    month_ink="#202333", month_muted="#454330", month_track="#CDB83C",
                    month="#136E6B"),
}


def normalize_style(value):
    return value if isinstance(value, str) and value in STYLE_NAMES else DEFAULT_STYLE


def reset_date(epoch, *, now=None, relative_day=False):
    """Local wall-clock time, using the API's reset timestamp without extrapolation."""
    if epoch is None:
        return "重置时间未知"
    try:
        target = datetime.fromtimestamp(float(epoch))
        current = datetime.fromtimestamp(time.time() if now is None else now)
    except (TypeError, ValueError, OverflowError, OSError):
        return "重置时间未知"
    day = (target.date() - current.date()).days
    prefix = {0: "今天", 1: "明天"}.get(day) if relative_day else None
    if prefix is None:
        prefix = f"{target.month}月{target.day}日"
        if target.year != current.year:
            prefix = f"{target.year}年{prefix}"
    return f"{prefix} {target:%H:%M}"


def reset_countdown(epoch, *, now=None):
    if epoch is None:
        return "等待重置时间"
    try:
        seconds = float(epoch) - (time.time() if now is None else now)
        if seconds <= 0:
            return "等待额度更新"
        minutes = ceil(seconds / 60)
    except (TypeError, ValueError, OverflowError):
        return "等待重置时间"
    if seconds < 60:
        return "不足 1 分钟后"
    days, remainder = divmod(minutes, 1440)
    hours, minutes = divmod(remainder, 60)
    if days:
        return f"{days}天{hours}小时后"
    if hours:
        return f"{hours}小时{minutes}分后"
    return f"{minutes}分钟后"


@lru_cache(maxsize=80)
def _font(size, bold=False, numeric=False):
    # Segoe for Latin numerals, YaHei for Chinese (Segoe has no CJK glyphs).
    names = ([r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf"]
             if numeric else [])
    names += [r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
              "DejaVuSans.ttf"]
    for name in names:
        try:
            return ImageFont.truetype(name, round(size * RENDER_SCALE))
        except OSError:
            continue
    return ImageFont.load_default()


def _corner_mask(size, bounds, radii):
    """A rounded rectangle with independent top-left/right, bottom-right/left radii."""
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    x0, y0, x1, y1 = [round(v * RENDER_SCALE) for v in bounds]
    draw.rectangle((x0, y0, x1, y1), fill=255)
    for corner, radius in enumerate(radii):
        r = round(radius * RENDER_SCALE)
        if r <= 0:
            continue
        tile = Image.new("L", (2*r, 2*r), 0)
        ImageDraw.Draw(tile).ellipse((0, 0, 2*r-1, 2*r-1), fill=255)
        crops = [(0, 0, r, r), (r, 0, 2*r, r), (r, r, 2*r, 2*r), (0, r, r, 2*r)]
        positions = [(x0, y0), (x1-r+1, y0), (x1-r+1, y1-r+1), (x0, y1-r+1)]
        mask.paste(tile.crop(crops[corner]), positions[corner])
    return mask


def render_card(*, style=DEFAULT_STYLE, mode="both", primary=None, weekly=None,
                primary_reset=None, weekly_reset=None, monthly=None, activity="ready",
                updated_at=None, error=False, now=None):
    """Return a transparent, oversampled card; never queries an account or creates UI."""
    style = normalize_style(style)
    p = PALETTES[style]
    now = time.time() if now is None else now
    width = WIDTH_BOTH if mode == "both" else WIDTH_SINGLE
    s = RENDER_SCALE
    size = (width*s, HEIGHT*s)
    edge, bottom = width-7, HEIGHT-7
    radii = (7, 7, 7, 7) if style == "mondrian" else (7, 20, 7, 20)
    border = 2.4 if style == "mondrian" else 1.6
    surface = Image.new("RGBA", size, p["bg"])
    draw = ImageDraw.Draw(surface)

    def box(bounds, fill, radius=0):
        coords = tuple(round(v*s) for v in bounds)
        if radius:
            draw.rounded_rectangle(coords, radius=round(radius*s), fill=fill)
        else:
            draw.rectangle(coords, fill=fill)

    def text(x, y, value, color=None, size=12, bold=False, anchor="lm", numeric=False, max_width=None):
        font = _font(size, bold, numeric)
        # Fit unusually long dates/balances while keeping ordinary labels large.
        if max_width:
            while draw.textlength(value, font=font) > max_width*s and size > 8:
                size -= .5
                font = _font(size, bold, numeric)
        draw.text((round(x*s), round(y*s)), value, fill=color or p["ink"],
                  font=font, anchor=anchor)

    # Header: the original preview's red cell becomes a meaningful activity label.
    header_y, section_y, footer_y = 42, 230, 359
    status = {"ready": "就绪", "working": "运行中", "closed": "未检测到", "error": "检测异常"}.get(activity, "未检测到")
    if error:
        status = "读取失败"
    text(17, 22, "Codex", size=16, bold=True, numeric=True)
    if style == "mondrian":
        box((edge-77, 0, edge, header_y), "#BF2F2B")
        box((edge-77, 0, edge-77+border, header_y), p["border"])
        text(edge-38, 22, status, "#FFF8E8", size=11, anchor="mm")
    else:
        text(edge-13, 22, status, p["muted"], size=11, anchor="rm")
        # Keep the pattern separate from text, including in single-gauge mode.
        dot_start = 139 if mode == "both" else 94
        for x in range(dot_start, dot_start+(34 if mode == "both" else 10), 7):
            for y in (16, 23, 30):
                draw.ellipse(((x-1.2)*s, (y-1.2)*s, (x+1.2)*s, (y+1.2)*s), fill=p["ink"])
    box((0, header_y, edge, header_y+border), p["border"])

    if mode in {"weekly", "both"}:
        left = edge/2 if mode == "both" else 0
        box((left, header_y+border, edge, section_y), p["week_bg"])
        if mode == "both":
            box((left, header_y, left+border, section_y), p["border"])

    def gauge(cx, title, value, reset, is_weekly=False):
        ink = p["week_ink"] if is_weekly else p["ink"]
        muted = p["week_muted"] if is_weekly else p["muted"]
        track = p["week_track"] if is_weekly else p["track"]
        tint = p["week"] if is_weekly else p["five"]
        if error:
            value, reset = None, None
        text(cx, 62, title, ink, size=13.5, anchor="mm")
        cy, radius, stroke = 119, 46.5, 5.6

        def arc(fraction, color):
            if fraction <= 0:
                return
            end = 120 + 300*fraction
            bounds = tuple(round(v*s) for v in (cx-radius-stroke/2, cy-radius-stroke/2,
                                                cx+radius+stroke/2, cy+radius+stroke/2))
            draw.arc(bounds, start=120, end=end, fill=color, width=round(stroke*s))
            for angle in (120, end):
                x, y = cx + radius*cos(radians(angle)), cy + radius*sin(radians(angle))
                cap = stroke/2
                draw.ellipse(((x-cap)*s, (y-cap)*s, (x+cap)*s, (y+cap)*s), fill=color)

        arc(1, track)
        if value is not None:
            arc(max(0, min(100, value))/100, tint)
        number = "—" if value is None else f"{value:.0f}"
        number_width = draw.textlength(number, font=_font(29.5, True, True))/s
        x = cx-(number_width+(13 if value is not None else 0))/2
        text(x, 111, number, ink, size=29.5, bold=True, numeric=True)
        if value is not None:
            text(x+number_width+3, 117, "%", muted, size=12, numeric=True)
        text(cx, 136, "暂不可用" if value is None else "剩余", muted, size=10.5, anchor="mm")
        max_width = edge/(2 if mode == "both" else 1)-14
        text(cx, 178, reset_date(reset, now=now, relative_day=not is_weekly), ink,
             size=12, anchor="mm", max_width=max_width)
        countdown = reset_countdown(reset, now=now)
        if reset is not None and countdown not in {"等待额度更新", "等待重置时间"}:
            countdown = "重置 · " + countdown
        text(cx, 197, countdown, muted, size=10.5, anchor="mm", max_width=max_width)
        if value is not None and value < 20:
            box((cx-48, 211, cx+48, 224), ink, 3)
            text(cx, 217, "余量低于 20%", p["week_bg"] if is_weekly else p["bg"], size=9, anchor="mm")

    if mode in {"5h", "both"}:
        gauge(edge/4 if mode == "both" else edge/2, "5 小时", primary, primary_reset)
    if mode in {"weekly", "both"}:
        gauge(edge*3/4 if mode == "both" else edge/2, "每周", weekly, weekly_reset, True)

    # Monthly allowance stays a single progress bar under the gauges.
    month = None if error else monthly
    value = month.remaining_percent if month is not None else None
    if style == "mondrian":
        box((0, section_y, edge, footer_y), p["month_bg"])
        box((0, section_y, edge, section_y+border), p["border"])
        box((0, footer_y, edge, footer_y+border), p["border"])
        left, right, top = 17, edge-17, 247
    else:
        bounds = (14, section_y+10, edge-14, footer_y-3)
        mask = _corner_mask(size, bounds, (3, 16, 3, 16))
        surface.paste(p["month_bg"], (0, 0, *size), mask)
        left, right, top = 26, edge-26, 255
    text(left, top, "本月额度", p["month_ink"], size=13)
    text(right, top, "—" if value is None else f"剩余 {value:.0f}%", p["month_muted"],
         size=10.5, anchor="rm")
    if month is None:
        text(left, top+30, "额度暂不可用", p["month_ink"], size=17)
    else:
        amount, total = f"{month.remaining:,.0f}", f" / {month.limit:,.0f}"
        number_size = 25
        total_width = draw.textlength(total, font=_font(11, numeric=True))/s
        while draw.textlength(amount, font=_font(number_size, True, True))/s+total_width > right-left and number_size > 12:
            number_size -= 1
        text(left, top+29, amount, p["month_ink"], size=number_size, bold=True, numeric=True)
        amount_width = draw.textlength(amount, font=_font(number_size, True, True))/s
        text(left+amount_width, top+34, total, p["month_muted"], size=11, numeric=True)
    bar_y = top+51
    box((left, bar_y, right, bar_y+5), p["month_track"], 2.5 if style == "memphis" else 0)
    if value is not None and value > 0:
        fill_width = (right-left)*min(100, value)/100
        box((left, bar_y, left+fill_width, bar_y+5), p["month"],
            min(2.5, fill_width/2) if style == "memphis" else 0)
    reset = month.resets_at if month else None
    exact = reset_date(reset, now=now)
    if reset is not None and exact != "重置时间未知":
        exact += " 重置"
    text(left, top+75, exact, p["month_ink"], size=11, max_width=right-left)
    countdown = reset_countdown(reset, now=now)
    if value is not None and value < 20:
        countdown += " · 余量低于 20%"
    text(left, top+91, countdown, p["month_muted"], size=10.5, max_width=right-left)

    updated = datetime.fromtimestamp(updated_at).strftime("%H:%M") if updated_at else "--:--"
    text(17, 375, "读取失败 · 请刷新" if error else f"更新 {updated}", p["muted"], size=10)
    text(edge-15, 375, "本机时区", p["muted"], size=10, anchor="rm")

    outer = _corner_mask(size, (1, 1, edge, bottom), radii)
    inner = _corner_mask(size, (1+border, 1+border, edge-border, bottom-border),
                         tuple(max(0, r-border) for r in radii))
    surface.paste(p["border"], (0, 0, *size), ImageChops.subtract(outer, inner))
    result = Image.new("RGBA", size)
    shadow = _corner_mask(size, (6, 6, edge+5, bottom+5), radii)
    result.paste(p["shadow"], (0, 0, *size), shadow)
    result.paste(surface, (0, 0), outer)
    return result
