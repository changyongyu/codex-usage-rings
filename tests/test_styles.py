"""Theme migration and real Tk menu integration, using only temporary state files."""
from datetime import datetime
import importlib
import json
import logging
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from PIL import ImageChops

from widget_styles import (DEFAULT_STYLE, normalize_style, reset_countdown, reset_date,
                           render_card, PALETTES, RENDER_SCALE, WIDTH_BOTH, HEIGHT)


class LiquidRendererTests(unittest.TestCase):
    def test_zero_missing_and_failed_data_are_not_conflated(self):
        kwargs = dict(now=1000, weekly=64)
        zero = render_card(primary=0, **kwargs)
        missing = render_card(primary=None, **kwargs)
        failure = render_card(primary=72, error=True, **kwargs)
        self.assertNotEqual(zero.tobytes(), missing.tobytes())
        self.assertEqual(failure.tobytes(), render_card(primary=None, error=True, **kwargs).tobytes())

    def test_wave_only_changes_hero_and_never_mutates_cached_layers(self):
        for style in PALETTES:
            kwargs = dict(style=style, primary=50, weekly=64, now=1000)
            still = render_card(**kwargs)
            wave = render_card(**kwargs, wave_time=.16)
            changed = ImageChops.difference(still.convert("RGB"), wave.convert("RGB")).getbbox()
            self.assertIsNotNone(changed)
            self.assertLessEqual(changed[2], 164*RENDER_SCALE)
            self.assertEqual(still.tobytes(), render_card(**kwargs).tobytes())
            self.assertEqual(still.tobytes(), render_card(**kwargs, wave_time=3).tobytes())

    def test_empty_and_full_liquid_are_clamped_and_no_offset_shadow(self):
        for style in PALETTES:
            empty = render_card(style=style, primary=50, now=1000, liquid_percent=-5)
            full = render_card(style=style, primary=50, now=1000, liquid_percent=105)
            point = (120*RENDER_SCALE, 200*RENDER_SCALE)
            self.assertNotEqual(empty.getpixel(point), full.getpixel(point))
            self.assertEqual(full.size, (WIDTH_BOTH*RENDER_SCALE, HEIGHT*RENDER_SCALE))
            self.assertEqual(full.getpixel((full.width-1, full.height-1))[3], 0)


class ResetTimeTests(unittest.TestCase):
    def test_reset_date_uses_calendar_and_preserves_cross_year(self):
        now = datetime(2026, 12, 31, 23).timestamp()
        reset = datetime(2027, 1, 1, 4).timestamp()
        self.assertEqual(reset_date(reset, now=now, relative_day=True), "明天 04:00")
        self.assertEqual(reset_date(reset, now=now), "2027年1月1日 04:00")

    def test_countdown_expired_missing_and_minute_boundary(self):
        self.assertEqual(reset_countdown(None, now=1000), "等待重置时间")
        self.assertEqual(reset_countdown(1000, now=1000), "等待额度更新")
        self.assertEqual(reset_countdown(1020, now=1000), "不足 1 分钟后")
        self.assertEqual(reset_countdown(4600, now=1000), "1小时0分后")
        self.assertEqual(reset_countdown(1000+9*86400+18*3600, now=1000), "9天18小时后")

    def test_invalid_theme_defaults_to_mondrian(self):
        for value in (None, "", "old-dark", [], {}):
            with self.subTest(value=value):
                self.assertEqual(normalize_style(value), DEFAULT_STYLE)


class MenuPersistenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.logging_home = tempfile.TemporaryDirectory()
        with patch.dict(os.environ, {"CODEX_HOME": cls.logging_home.name}):
            cls.ui = importlib.import_module("codex_usage_widget")
        cls.restore_position = cls.ui.CodexOverlay._restore_position

    @classmethod
    def tearDownClass(cls):
        logging.shutdown()
        cls.logging_home.cleanup()

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        directory = Path(temporary.name)
        for name, value in (("CODEX_HOME", directory), ("WIDGET_POS_JSON", directory/"widget_pos.json")):
            p = patch.object(self.ui, name, value)
            p.start()
            self.addCleanup(p.stop)
        # Exercise real menus and PhotoImage, without tray threads, account reads or visible windows.
        for name in ("_start_tray_icon", "_start_activity_monitor", "_start_polling", "_restore_position"):
            p = patch.object(self.ui.CodexOverlay, name)
            p.start()
            self.addCleanup(p.stop)
        p = patch.object(self.ui.tk.Tk, "deiconify")
        p.start()
        self.addCleanup(p.stop)

    def open_widget(self):
        widget = self.ui.CodexOverlay()
        self.addCleanup(self.close_widget, widget)
        return widget

    def close_widget(self, widget):
        if widget.stop_event.is_set():
            return
        widget.stop_event.set()
        for timer in widget.root.tk.call("after", "info"):
            widget.root.after_cancel(timer)
        widget.root.update_idletasks()
        widget.root.destroy()

    def test_clean_install_defaults_to_mondrian(self):
        widget = self.open_widget()
        self.assertEqual(widget.style, "mondrian")
        self.assertEqual(widget.style_var.get(), "mondrian")

    def test_upgrade_keeps_existing_settings_and_uses_default_style(self):
        self.ui.WIDGET_POS_JSON.write_text(json.dumps(dict(x=80, y=120, locked=True,
            always_on_top=False, display_mode="weekly")), encoding="utf-8")
        state = self.ui._load_widget_state()
        self.assertEqual(state["style"], "mondrian")
        self.assertEqual((state["x"], state["y"], state["locked"], state["display_mode"]),
                         (80, 120, True, "weekly"))

    def test_larger_card_fits_existing_monitor_including_negative_coordinates(self):
        root = SimpleNamespace(winfo_screenwidth=lambda: 1920, winfo_screenheight=lambda: 1080)
        with patch.object(self.ui, "_get_monitor_rects", return_value=[(-1920, -200, 0, 880), (0, 0, 1920, 1080)]):
            self.assertEqual(self.ui._position_on_available_screen(root, -263, -152, 365), (-365, -152, True))
            self.assertEqual(self.ui._position_on_available_screen(root, 100, 900, 365),
                             (100, 1080-self.ui.display_size(self.ui.WIDGET_H), True))

    def test_failed_setting_replace_preserves_previous_selection(self):
        self.ui._save_widget_state(80, 120, True, False, "both", "memphis")
        before = self.ui.WIDGET_POS_JSON.read_text(encoding="utf-8")
        with patch.object(Path, "replace", side_effect=OSError("simulated write failure")):
            self.ui._save_widget_state(80, 120, True, False, "both", "mondrian")
        self.assertEqual(self.ui.WIDGET_POS_JSON.read_text(encoding="utf-8"), before)

    def test_restored_coordinates_are_saved_before_window_is_mapped(self):
        self.ui._save_widget_state(-263, -152, True, True, "both", "memphis")
        widget = self.open_widget()
        with patch.object(self.ui, "_position_on_available_screen", return_value=(-365, -152, True)):
            type(self).restore_position(widget)
        state = self.ui._load_widget_state()
        self.assertEqual((state["x"], state["y"], state["style"]), (-365, -152, "memphis"))

    def test_both_menu_entries_switch_and_selection_survives_restart(self):
        widget = self.open_widget()
        menu = next(widget.menu.nametowidget(widget.menu.entrycget(index, "menu"))
                    for index in range(widget.menu.index("end")+1)
                    if widget.menu.type(index) == "cascade"
                    and widget.menu.entrycget(index, "label") == "展示风格")
        self.assertEqual(menu.entrycget(0, "label"), "蒙德里安")
        self.assertEqual(menu.entrycget(1, "label"), "孟菲斯波点")
        menu.invoke(1)
        self.assertEqual(widget.style, "memphis")
        self.assertEqual(self.ui._load_widget_state()["style"], "memphis")
        self.close_widget(widget)
        reopened = self.open_widget()
        self.assertEqual(reopened.style, "memphis")
        reopened.style_var.set("mondrian")
        reopened.change_style()
        self.assertEqual(self.ui._load_widget_state()["style"], "mondrian")

    def test_tray_selection_dispatches_to_tk_and_updates_radio(self):
        widget = self.open_widget()
        menu = widget._build_tray_menu()
        style_menu = next(item.submenu for item in menu.items if item.text == "展示风格")
        style_menu.items[1](None)
        widget.root.update()
        self.assertEqual(widget.style, "memphis")
        self.assertTrue(style_menu.items[1].checked)
        self.assertFalse(style_menu.items[0].checked)

    def test_liquid_animation_stops_at_deadline_and_reuses_canvas_image(self):
        widget = self.open_widget()
        widget.primary_left = 50
        with patch.object(widget, "_system_animations_enabled", return_value=True):
            widget._start_liquid_motion(previous=70)
        self.assertIsNotNone(widget._liquid_after)
        widget.root.after_cancel(widget._liquid_after)
        with patch.object(self.ui.time, "monotonic", return_value=widget._liquid_started+2.3):
            widget._liquid_tick()
        self.assertIsNone(widget._liquid_after)
        self.assertEqual(len(widget.canvas.find_all()), 1)

    def test_reduced_motion_and_error_cancel_animation(self):
        widget = self.open_widget()
        widget.primary_left = 50
        with patch.object(widget, "_system_animations_enabled", return_value=False):
            widget._start_liquid_motion()
        self.assertIsNone(widget._liquid_after)
        with patch.object(widget, "_system_animations_enabled", return_value=True):
            widget._start_liquid_motion()
        self.assertIsNotNone(widget._liquid_after)
        widget._apply_error()
        self.assertIsNone(widget._liquid_after)

    def test_hiding_card_cancels_pending_animation(self):
        widget = self.open_widget()
        widget.primary_left = 50
        with patch.object(widget, "_system_animations_enabled", return_value=True):
            widget._start_liquid_motion()
        widget.minimize_to_tray()
        self.assertIsNone(widget._liquid_after)
        self.assertFalse(widget.widget_visible)


if __name__ == "__main__":
    unittest.main()
