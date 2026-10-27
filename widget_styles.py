"""Account-independent Pillow renderer for the two desktop card styles."""
from datetime import datetime
from functools import lru_cache
from math import ceil, cos, exp, pi, sin
import time

from PIL import Image, ImageChops, ImageDraw, ImageFont

DEFAULT_STYLE = "mondrian"
STYLE_NAMES = {"mondrian": "蒙德里安", "memphis": "孟菲斯波点"}
WIDTH_BOTH, WIDTH_SINGLE, HEIGHT = 464, 398, 284
RENDER_SCALE = 4

PALETTES = {
    "mondrian": dict(bg="#FAF7EF", ink="#282B29", muted="#585F63", hero_bg="#F2ECE1",
                     border="#333933", divider="#D5CFBB", five="#BE4035", wet="#FFFAF0",
                     week_bg="#EDF1F6", week_track="#D9E1ED", week="#2453A1",
                     month_bg="#F4E9CA", month_muted="#65572F"),
    "memphis": dict(bg="#F6EEDD", ink="#25283B", muted="#555466", hero_bg="#F6EEDD",
                    border="#25283B", divider="#25283B", five="#C8453E", wet="#FFFAF0",
                    week_bg="#B9DCD3", week_track="#91BDB3", week="#2C54A5",
                    month_bg="#F3D453", month_muted="#534622"),
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


@lru_cache(maxsize=4)
def _card_layers(style, mode, primary, weekly, primary_date, primary_count,
                 weekly_date, weekly_count, monthly_values, monthly_date,
                 monthly_count, activity, updated, error):
    """Cache text and static surfaces; animation only paints the hero-sized crop."""
    p = PALETTES[style]
    s = RENDER_SCALE
    width = WIDTH_BOTH if mode == "both" else WIDTH_SINGLE
    size = (width*s, HEIGHT*s)
    edge, bottom = width-1, HEIGHT-1
    border = 1.25 if style == "mondrian" else 1.5
    radii = (15, 15, 15, 15) if style == "mondrian" else (10, 28, 10, 28)
    header, split, footer, hero_right = 40, 151, 254, 164
    surface = Image.new("RGBA", size, p["bg"])
    draw = ImageDraw.Draw(surface)

    def box(bounds, fill, radius=0):
        coords = tuple(round(v*s) for v in bounds)
        if radius:
            draw.rounded_rectangle(coords, radius=round(radius*s), fill=fill)
        else:
            draw.rectangle(coords, fill=fill)

    def text(x, y, value, color=None, size=12, bold=False, numeric=False,
             anchor="lm", max_width=None, target=None):
        painter = ImageDraw.Draw(target) if target is not None else draw
        font = _font(size, bold, numeric)
        while max_width and painter.textlength(value, font=font) > max_width*s and size > 11:
            size -= .5
            font = _font(size, bold, numeric)
        painter.text((round(x*s), round(y*s)), value, fill=color or p["ink"],
                     font=font, anchor=anchor)

    status = {"ready": "就绪", "working": "运行中", "closed": "未检测到", "error": "检测异常"}.get(activity, "未检测到")
    status = "读取失败" if error else status
    text(16, 20, "Codex", size=16, bold=True, numeric=True)
    text(76, 21, "使用额度", p["muted"], size=11)
    text(edge-16, 21, status, p["muted"], size=11, anchor="rm")
    status_w = draw.textlength(status, font=_font(11))/s
    box((edge-26-status_w, 18, edge-21-status_w, 23), "#426E54" if not error else p["five"], 2.5)
    if style == "memphis":
        for x in range(round(edge-91-status_w), round(edge-56-status_w), 7):
            for y in (14, 21, 28):
                draw.ellipse(((x-1)*s, (y-1)*s, (x+1)*s, (y+1)*s), fill=p["ink"])

    left, right = hero_right+20, edge-18
    if mode == "both":
        box((hero_right, header, edge, split), p["week_bg"])
        text(left, 65, "每周", size=13)
        suffix = "% 剩余" if weekly is not None else "暂不可用"
        suffix_w = draw.textlength(suffix, font=_font(11))/s
        text(right, 68, suffix, p["muted"], size=11, anchor="rm")
        text(right-suffix_w-4, 63, "—" if weekly is None else f"{weekly:.0f}",
             size=30, numeric=True, anchor="rm")
        box((left, 89, right, 102), p["week_track"], 6.5)
        if weekly is not None and weekly > 0:
            fill_width = (right-left)*max(0, min(100, weekly))/100
            box((left, 89, left+fill_width, 102), p["week"], min(6.5, fill_width/2))
        text(left, 119, weekly_date+" 重置" if weekly is not None else "等待额度数据",
             p["muted"], size=11, max_width=right-left)
        countdown = weekly_count + (" · 余量低于20%" if weekly is not None and weekly < 20 else "")
        text(left, 137, countdown, p["muted"], size=11, max_width=right-left)

    month_top = split if mode == "both" else header
    box((hero_right, month_top, edge, footer), p["month_bg"])
    if mode == "both":
        box((hero_right, split, edge, split+border), p["divider"])
    title_y = month_top+20
    amount_y = month_top+51 if mode == "both" else month_top+78
    text(left, title_y, "本月额度", size=13)
    value = monthly_values[2] if monthly_values else None
    label = "暂不可用" if value is None else f"剩余 {value:.0f}%"
    text(right, title_y, label, p["month_muted"], size=11, anchor="rm")
    if monthly_values is None:
        text(left, amount_y, "额度暂不可用", size=18)
    else:
        amount, total, _ = monthly_values
        number_size = 32
        suffix = " / " + total
        suffix_w = draw.textlength(suffix, font=_font(12, numeric=True))/s
        while draw.textlength(amount, font=_font(number_size, numeric=True))/s+suffix_w > right-left and number_size > 12:
            number_size -= 1
        text(left, amount_y, amount, size=number_size, numeric=True)
        amount_w = draw.textlength(amount, font=_font(number_size, numeric=True))/s
        text(left+amount_w, amount_y+5, suffix, p["month_muted"], size=12, numeric=True)
    text(left, footer-28, monthly_date+" 重置" if monthly_values else "等待额度数据",
         p["month_muted"], size=11, max_width=right-left)
    countdown = monthly_count + (" · 余量低于20%" if value is not None and value < 20 else "")
    text(left, footer-11, countdown, p["month_muted"], size=11, max_width=right-left)

    box((0, header, edge, header+border), p["border"])
    box((hero_right, header, hero_right+border, footer), p["border"])
    box((0, footer, edge, footer+border), p["divider"])
    text(15, 269, "读取失败 · 请刷新" if error else f"更新 {updated}", p["muted"], size=11)
    text(edge-15, 269, "本机时区", p["muted"], size=11, anchor="rm")

    # Both ink layers have identical glyph geometry. The same liquid mask clips
    # the fill and light ink, keeping text readable as the waterline crosses it.
    bounds = tuple(round(v*s) for v in (border, header+border, hero_right, footer))
    hero_size = (bounds[2]-bounds[0], bounds[3]-bounds[1])
    dry = Image.new("RGBA", hero_size)
    wet = Image.new("RGBA", hero_size)
    hero_value = weekly if mode == "weekly" else primary
    hero_date = weekly_date if mode == "weekly" else primary_date
    hero_count = weekly_count if mode == "weekly" else primary_count
    for layer, color in ((dry, p["ink"]), (wet, p["wet"])):
        text(16, 23, "每周" if mode == "weekly" else "5 小时", color, size=14, target=layer)
        number = "—" if hero_value is None else f"{hero_value:.0f}"
        text(13, 79, number, color, size=48, bold=True, numeric=True, target=layer)
        number_w = draw.textlength(number, font=_font(48, True, True))/s
        if hero_value is not None:
            text(16+number_w, 91, "%", color, size=14, numeric=True, target=layer)
        label = "暂不可用" if hero_value is None else ("余量低于20%" if hero_value < 20 else "剩余额度")
        text(16, 112, label, color, size=11, target=layer)
        if draw.textlength(hero_date, font=_font(12)) > (hero_size[0]/s-27)*s:
            parts = hero_date.rsplit(" ", 1)
            text(16, 159, parts[0], color, size=11, target=layer)
            text(16, 177, parts[-1] if len(parts) == 2 else "", color, size=12, target=layer)
        else:
            text(16, 177, hero_date, color, size=12, target=layer)
        text(16, 197, hero_count, color, size=11, target=layer)

    outer = _corner_mask(size, (0, 0, edge, bottom), radii)
    inner = _corner_mask(size, (border, border, edge-border, bottom-border),
                         tuple(max(0, r-border) for r in radii))
    surface.paste(p["border"], (0, 0, *size), ImageChops.subtract(outer, inner))
    return surface, dry, wet, outer, bounds


def render_card(*, style=DEFAULT_STYLE, mode="both", primary=None, weekly=None,
                primary_reset=None, weekly_reset=None, monthly=None, activity="ready",
                updated_at=None, error=False, now=None, wave_time=0, liquid_percent=None):
    """Render the real card at 4× resolution. No account access and no offset shadow."""
    style = normalize_style(style)
    mode = mode if mode in {"both", "5h", "weekly"} else "both"
    p = PALETTES[style]
    now = time.time() if now is None else now
    if error:
        primary = weekly = monthly = None
        primary_reset = weekly_reset = None
    monthly_values = None if monthly is None else (
        f"{monthly.remaining:,.0f}", f"{monthly.limit:,.0f}", monthly.remaining_percent)
    monthly_reset = monthly.resets_at if monthly else None
    layers = _card_layers(style, mode, primary, weekly,
        reset_date(primary_reset, now=now, relative_day=True), reset_countdown(primary_reset, now=now),
        reset_date(weekly_reset, now=now), reset_countdown(weekly_reset, now=now), monthly_values,
        reset_date(monthly_reset, now=now), reset_countdown(monthly_reset, now=now), activity,
        datetime.fromtimestamp(updated_at).strftime("%H:%M") if updated_at else "--:--", error)
    base, dry, wet, outer, bounds = layers
    value = weekly if mode == "weekly" else primary
    if liquid_percent is not None and value is not None:
        value = liquid_percent
    percent = 0 if value is None else max(0, min(100, float(value)))
    w, h = dry.size
    level = h*(1-percent/100)
    amp = 0 if wave_time <= 0 or wave_time >= 2.2 else 5*RENDER_SCALE*exp(-wave_time/.55)*min(1, wave_time/.07)
    amp = min(amp, level, h-level)
    points = [(w*i/64, level+amp*(cos(i*pi/64)*sin(wave_time/.175)*.75+
                                  sin(i*pi/32+wave_time/.175)*.25)) for i in range(65)]
    mask = Image.new("L", (w, h), 0)
    if percent > 0:
        ImageDraw.Draw(mask).polygon(points+[(w, h), (0, h)], fill=255)
    hero = Image.new("RGBA", (w, h), p["hero_bg"])
    hero.paste(p["week"] if mode == "weekly" else p["five"], (0, 0, w, h), mask)
    hero.alpha_composite(dry)
    hero.paste(wet, (0, 0), ImageChops.multiply(wet.getchannel("A"), mask))
    result = base.copy()
    result.paste(hero, bounds[:2])
    result.putalpha(outer)
    return result
