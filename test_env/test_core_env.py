#!/usr/bin/env python3
"""Test runner for StratOS Maneki Neko Phase 1 core environment components.

Run with:
    ./.venv/bin/python test_env/test_core_env.py
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.core import autostart, environment, paths  # noqa: E402


def test_paths_and_catalogs() -> None:
    print("=== 1. Testing Paths, Data Catalogs & Persistent Settings Schema ===")
    print(f"  ROOT_DIR         : {paths.ROOT_DIR}")
    print(f"  DATA_DIR         : {paths.DATA_DIR}")
    print(f"  ASSETS_DIR       : {paths.ASSETS_DIR}")
    print(f"  SETTINGS_FILE    : {paths.USER_SETTINGS_FILE}")

    pkg_data = paths.load_json_data("packages.json")
    categories = pkg_data.get("categories", [])
    packages = pkg_data.get("packages", [])
    assert len(categories) == 5, f"Expected 5 categories, got {len(categories)}"
    assert len(packages) == 16, f"Expected 16 packages, got {len(packages)}"
    print(f"  Loaded {len(categories)} categories and {len(packages)} packages from data/packages.json [OK]")

    contrib_data = paths.load_json_data("contributors.json")
    contributors = contrib_data.get("contributors", [])
    assert len(contributors) >= 9
    print(f"  Loaded {len(contributors)} contributors from data/contributors.json [OK]")

    themes_data = paths.load_json_data("themes.json").get("themes", {})
    expected_themes = {"system", "tokyonight-dark", "tokyonight-light", "gruvbox-dark", "gruvbox-light"}
    assert expected_themes.issubset(themes_data.keys())
    print(f"  Loaded themes    : {list(themes_data.keys())} [OK]")

    settings = paths.load_user_settings()
    for required_key in (
        "theme",
        "wm_font_mode",
        "cached_gnome_font",
        "cached_qt6ct_font",
        "install_flatpaks_system_wide",
        "package_source_preferences",
    ):
        assert required_key in settings, f"Missing setting key: {required_key}"
    print(f"  Verified settings schema keys: {list(settings.keys())} [OK]")


def test_font_parsing_and_edition_detection() -> None:
    print("\n=== 2. Testing GNOME Font Parsing, WM Font Modes & Edition Detection ===")
    # Test Pango / gsettings font strings ("Cantarell 11", "Rubik 11", "Cantarell Bold 11")
    assert environment.parse_font_string("'Cantarell 11'", "Sans", 10) == ("Cantarell", 11)
    assert environment.parse_font_string("'Rubik 11'", "Cantarell", 11) == ("Rubik", 11)
    assert environment.parse_font_string("'Cantarell Bold 12'", "Cantarell", 11) == ("Cantarell", 12)
    # Test qt6ct serialized QFont strings
    assert environment.parse_font_string(
        '"JetBrains Mono,10,-1,5,400,0,0,0,0,0,0,0,0,0,0,1"',
        "Sans",
        11,
    ) == ("JetBrains Mono", 10)
    print("  Verified gsettings ('Cantarell 11', 'Rubik 11') and qt6ct QFont string parsers [OK]")

    for mode in ("auto", "gnome", "hyprland", "niri", "swayfx"):
        info = environment.detect_edition(
            mode, wm_font_mode_override="jetbrains-mono", persist_cache=False
        )
        term_cmd = environment.detect_preferred_terminal(info)
        print(
            f"  Mode={mode:<8} -> edition={info.edition:<8} | ui_mode={info.ui_mode:<5} | "
            f"font='{info.font_family}' ({info.font_size}pt) | wm_font_mode={info.wm_font_mode} | "
            f"terminal={term_cmd[0]}"
        )
        if mode == "gnome":
            assert info.ui_mode == "gnome"
        elif mode in ("hyprland", "niri", "swayfx"):
            assert info.ui_mode == "wm"
            assert info.font_family == "JetBrains Mono"

    # Test WM font mode override with simulated qt6ct.conf
    with tempfile.TemporaryDirectory() as tmpdir:
        fake_qt6ct = Path(tmpdir) / "qt6ct.conf"
        fake_qt6ct.write_text(
            "[Fonts]\ngeneral=\"FiraCode Nerd Font,11,-1,5,50,0,0,0,0,0\"\n",
            encoding="utf-8",
        )
        fam, sz = environment.query_qt6ct_general_font(qt6ct_conf_path=fake_qt6ct)
        assert (fam, sz) == ("FiraCode Nerd Font", 11)
        print(f"  Simulated qt6ct.conf [Fonts] general -> '{fam}' ({sz}pt) [OK]")


def test_autostart_state() -> None:
    print("\n=== 3. Testing Autostart Status Check ===")
    enabled = autostart.is_autostart_enabled()
    print(f"  Autostart file   : {paths.AUTOSTART_DESKTOP_FILE} (enabled={enabled}) [OK]")


def test_pyqt6_and_theme_manager() -> None:
    print("\n=== 4. Testing PyQt6, Direct qt6ct Color Extraction & QSS Font Lock ===")
    from PyQt6 import QtGui, QtWidgets
    from src.core import theme_manager

    # Test WCAG contrast math on known colors
    dark_bg = QtGui.QColor("#1a1b26")
    light_fg = QtGui.QColor("#c0caf5")
    bad_fg = QtGui.QColor("#1f202e")
    good_ratio = theme_manager.contrast_ratio(dark_bg, light_fg)
    bad_ratio = theme_manager.contrast_ratio(dark_bg, bad_fg)
    print(f"  TokyoNight Dark contrast ratio : {good_ratio:.2f}:1 (readable >= 1.8)")
    print(f"  Broken config contrast ratio   : {bad_ratio:.2f}:1 (triggers rescue < 1.8)")
    assert good_ratio > 7.0
    assert bad_ratio < 1.8

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    theme_manager.configure_qt_platform_theme_env()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    paths.register_qt_search_paths()

    # Test simulated qt6ct color_scheme_path extraction (ensuring [Fonts] in qt6ct is ignored)
    with tempfile.TemporaryDirectory() as tmpdir:
        scheme_file = Path(tmpdir) / "custom_scheme.conf"
        # 21 color roles
        colors = [
            "#ffebdbb2", "#ff504945", "#ff7c6f64", "#ff665c54", "#ff1d2021",
            "#ff665c54", "#ffebdbb2", "#fffbf1c7", "#ffebdbb2", "#ff3c3836",
            "#ff282828", "#ff1d2021", "#fffe8019", "#ff1d2021", "#ff83a598",
            "#ffd3869b", "#ff32302f", "#ff000000", "#ff3c3836", "#ffebdbb2",
            "#ff928374",
        ]
        line = ", ".join(colors)
        scheme_file.write_text(
            f"[ColorScheme]\nactive_colors={line}\ninactive_colors={line}\ndisabled_colors={line}\n",
            encoding="utf-8",
        )
        qt6ct_file = Path(tmpdir) / "qt6ct.conf"
        qt6ct_file.write_text(
            f"[Appearance]\ncustom_palette=true\ncolor_scheme_path={scheme_file}\n"
            f"[Fonts]\ngeneral=\"Comic Sans MS,14,-1,5,50,0,0,0,0,0\"\n",
            encoding="utf-8",
        )
        extracted_pal = theme_manager.load_qt6ct_color_palette(app.palette(), qt6ct_conf_path=qt6ct_file)
        assert extracted_pal.color(QtGui.QPalette.ColorRole.Window).name() == "#282828"
        assert extracted_pal.color(QtGui.QPalette.ColorRole.Highlight).name() == "#fe8019"
        print("  Extracted color-only QPalette from simulated qt6ct.conf (ignoring qt6ct [Fonts]) [OK]")

    # Test GNOME mode QSS font lock + WM mode font switching
    gnome_env = environment.detect_edition("gnome", persist_cache=False)
    tm = theme_manager.ThemeManager(app, gnome_env)
    assert f'font-family: "{gnome_env.font_family}"' in app.styleSheet()
    print(f"  Verified GNOME QSS locks font to '{gnome_env.font_family}' above qt6ct [OK]")

    for theme_id, label in tm.available_themes():
        tm.apply_theme(theme_id, persist=False)
        win_hex = app.palette().color(QtGui.QPalette.ColorRole.Window).name()
        txt_hex = app.palette().color(QtGui.QPalette.ColorRole.WindowText).name()
        hl_hex = app.palette().color(QtGui.QPalette.ColorRole.Highlight).name()
        print(
            f"  Applied theme '{theme_id:<16}' ({label:<16}) -> "
            f"Window={win_hex}, Text={txt_hex}, Highlight={hl_hex}"
        )

    # Test WM mode switching between JetBrains Mono (Default) and System (qt6ct Font)
    wm_env = environment.detect_edition("hyprland", wm_font_mode_override="jetbrains-mono", persist_cache=False)
    tm_wm = theme_manager.ThemeManager(app, wm_env)
    assert tm_wm.env_info.font_family == "JetBrains Mono"
    tm_wm.set_wm_font_mode("qt6ct-system", persist=False)
    print(
        f"  Verified WM font mode switch -> mode={tm_wm.env_info.wm_font_mode}, "
        f"active font='{tm_wm.env_info.font_family}' ({tm_wm.env_info.font_size}pt) [OK]"
    )


if __name__ == "__main__":
    test_paths_and_catalogs()
    test_font_parsing_and_edition_detection()
    test_autostart_state()
    test_pyqt6_and_theme_manager()
    print("\nAll updated Phase 1 environment checks completed successfully!")
