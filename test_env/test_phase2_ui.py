#!/usr/bin/env python3
"""Automated test suite for Phase 2 UI components & WASD/Arrow NavigationFilter."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt6 import QtCore, QtWidgets
from PyQt6.QtTest import QTest

from src.core.environment import detect_edition
from src.core.paths import register_qt_search_paths
from src.core.theme_manager import ThemeManager
from src.ui.components import (
    AdwActionRow,
    AdwPreferencesGroup,
    HeaderBar,
    RescueBanner,
    SourcePillBar,
    ToggleSwitch,
)
from src.ui.navigation_filter import NavigationFilter


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)
    register_qt_search_paths()

    print("=== StratOS Maneki Neko (PyQt6) Phase 2 UI & Navigation Test Suite ===")

    # 1. Test ToggleSwitch
    sw = ToggleSwitch(checked=False)
    assert not sw.isChecked()
    assert sw.knobPosition == 0.0
    sw.setCheckedImmediate(True)
    assert sw.isChecked()
    assert sw.knobPosition == 1.0
    sw.toggle()
    assert not sw.isChecked()
    print("[PASS] ToggleSwitch state & knobPosition verified.")

    # 2. Test SourcePillBar
    pills = SourcePillBar(["pacman", "flatpak", "aur"], default_source="pacman")
    assert pills.selected_source() == "pacman"
    assert pills.cycle_source(+1) == "flatpak"
    assert pills.cycle_source(+1) == "aur"
    assert pills.cycle_source(+1) == "pacman"
    assert pills.cycle_source(-1) == "aur"
    print("[PASS] SourcePillBar source selection & cyclic wrap verified.")

    # 3. Test AdwActionRow & AdwPreferencesGroup
    group = AdwPreferencesGroup(
        title="Browsers",
        description="Select preferred web browsers and package source.",
    )
    row1 = AdwActionRow(
        title="Mozilla Firefox",
        subtitle="Free and open-source web browser",
        icon_path="appicons:firefox.png",
        has_toggle=True,
        checked=True,
        sources=["pacman", "flatpak"],
        default_source="pacman",
        row_id="firefox",
    )
    row2 = AdwActionRow(
        title="Brave Browser",
        subtitle="Privacy-focused Chromium browser",
        icon_path="appicons:brave.png",
        has_toggle=True,
        checked=False,
        sources=["aur", "flatpak"],
        default_source="aur",
        row_id="brave",
    )
    row3 = AdwActionRow(
        title="Install Grab",
        subtitle="StratOS utility script",
        icon_path="icons:terminal.png",
        action_text="Run Script",
        row_id="grab",
    )
    group.add_row(row1)
    group.add_row(row2)
    group.add_row(row3)
    assert len(group.rows) == 3
    assert row1.is_checked() is True
    assert row2.is_checked() is False
    print("[PASS] AdwPreferencesGroup & AdwActionRow construction verified.")

    # 4. Test HeaderBar (Clean layout + Hamburger Menu + Custom HeaderStepButtons)
    env_wm = detect_edition("hyprland", persist_cache=False)
    tm = ThemeManager(app, env_wm, initial_theme_override="tokyonight-dark")

    window = QtWidgets.QWidget()
    vbox = QtWidgets.QVBoxLayout(window)
    header = HeaderBar(tm, parent=window)
    assert header.hamburger_btn is not None, "HeaderBar must expose hamburger_btn"
    assert len(header._theme_actions) == 5, "Hamburger menu must include all 5 themes"
    assert len(header._font_actions) == 2, "WM mode hamburger menu must include WM font actions"
    assert header.autostart_action is not None, "Hamburger menu must include Launch at Startup action"
    assert header._step_buttons[0].isChecked() is True
    assert header._step_buttons[1].isChecked() is False
    vbox.addWidget(header)

    rescue = RescueBanner("test contrast fallback", parent=window)
    vbox.addWidget(rescue)

    search_input = QtWidgets.QLineEdit(window)
    search_input.setPlaceholderText("Filter packages...")
    vbox.addWidget(search_input)

    vbox.addWidget(group)

    # Install NavigationFilter on the application
    nav = NavigationFilter(window, theme_manager=tm)
    app.installEventFilter(nav)

    window.resize(900, 620)
    window.show()
    QTest.qWait(20)

    # 5. Test WASD & Arrow Navigation
    row1.setFocus()
    QTest.qWait(10)
    assert app.focusWidget() is row1
    assert row1.property("focused") == "true"

    # Press 'D' -> cycles row1 source from 'pacman' to 'flatpak'
    QTest.keyClick(row1, QtCore.Qt.Key.Key_D)
    assert row1.selected_source() == "flatpak", f"Expected flatpak, got {row1.selected_source()}"

    # Press 'A' -> cycles row1 source back to 'pacman'
    QTest.keyClick(row1, QtCore.Qt.Key.Key_A)
    assert row1.selected_source() == "pacman"

    # Press 'Space' -> toggles row1 switch from True to False
    QTest.keyClick(row1, QtCore.Qt.Key.Key_Space)
    assert row1.is_checked() is False

    # Press 'S' -> moves focus down to row2
    QTest.keyClick(row1, QtCore.Qt.Key.Key_S)
    assert app.focusWidget() is row2
    assert row1.property("focused") == "false"
    assert row2.property("focused") == "true"

    # Press Right Arrow on row2 -> cycles source from 'aur' to 'flatpak'
    QTest.keyClick(row2, QtCore.Qt.Key.Key_Right)
    assert row2.selected_source() == "flatpak"

    # Press Space on row2 -> toggles row2 switch from False to True
    QTest.keyClick(row2, QtCore.Qt.Key.Key_Space)
    assert row2.is_checked() is True

    # Press 'W' on row2 -> moves focus back up to row1
    QTest.keyClick(row2, QtCore.Qt.Key.Key_W)
    assert app.focusWidget() is row1

    # Focus search_input and verify typing 'wasd' enters text instead of navigating
    search_input.setFocus()
    QTest.keyClicks(search_input, "wasd")
    assert search_input.text() == "wasd"
    assert app.focusWidget() is search_input
    print("[PASS] WASD + Arrow keys + Space + QLineEdit text-input bypass verified.")

    # 6. Test Ctrl+T global theme cycle shortcut & Hamburger Menu sync
    before_theme = tm.current_theme_id
    QTest.keyClick(
        row1,
        QtCore.Qt.Key.Key_T,
        QtCore.Qt.KeyboardModifier.ControlModifier,
    )
    after_theme = tm.current_theme_id
    assert before_theme != after_theme
    assert header._theme_actions[after_theme].isChecked() is True
    print(f"[PASS] Ctrl+T cycled theme ({before_theme} -> {after_theme}) and synced Hamburger Menu.")

    # 7. Test GNOME Mode HeaderBar
    env_gnome = detect_edition("gnome", persist_cache=False)
    tm_gnome = ThemeManager(app, env_gnome)
    header_gnome = HeaderBar(tm_gnome)
    assert len(header_gnome._font_actions) == 0, "GNOME mode hamburger menu uses Sync GNOME Shell Font action"
    print("[PASS] Clean HeaderBar & Hamburger Menu (Theme, Font, Autostart) verified in both WM & GNOME modes.")

    window.close()
    print("=== ALL PHASE 2 UI & NAVIGATION TESTS PASSED ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
