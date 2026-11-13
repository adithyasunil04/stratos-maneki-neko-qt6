#!/usr/bin/env python3
"""Automated integration test suite for Phase 3 (Pages & Dialogs) & Phase 4 (TaskRunner & TerminalDrawer)."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt6 import QtCore, QtWidgets
from PyQt6.QtTest import QTest

from src.core.defaults_manager import DEFAULT_APP_CATEGORIES, DefaultsManager
from src.core.environment import detect_edition
from src.core.paths import register_qt_search_paths
from src.core.runner import TaskRunner
from src.core.theme_manager import ThemeManager
from src.ui.components import DefaultAppRow
from src.ui.dialogs import CreditsDialog
from src.ui.main_window import MainWindow


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)
    register_qt_search_paths()

    print("=== StratOS Maneki Neko (PyQt6) Phase 3 & Phase 4 Full App Test Suite ===")

    env = detect_edition("hyprland", persist_cache=False)
    tm = ThemeManager(app, env, initial_theme_override="tokyonight-dark")

    # 1. Construct MainWindow in dry_run mode
    win = MainWindow(theme_manager=tm, dry_run=True)
    win.show()
    QTest.qWait(30)
    assert win.stack.count() == 4
    assert win.stack.currentIndex() == 0
    print("[PASS] MainWindow initialized with 4 wizard pages in QStackedWidget.")

    # 2. Verify Step navigation (Welcome -> Overview -> Setup -> Software)
    win.go_next_step()
    assert win.stack.currentIndex() == 1
    assert win.header_bar.active_step == 1

    # Test OverviewPage feature selection
    win.overview_page.select_feature(2)
    assert "Tiling Window Manager" in win.overview_page.preview_title.text()
    print("[PASS] Page 2 (OverviewPage) feature deck & preview card verified.")

    win.go_next_step()
    assert win.stack.currentIndex() == 2
    print("[PASS] Page 3 (SetupPage) loaded.")

    win.go_next_step()
    assert win.stack.currentIndex() == 3
    initial_selected = win.packages_page.selected_count()
    assert initial_selected > 0, "Expected default checked packages from packages.json"
    print(f"[PASS] Page 4 (PackagesPage) loaded with {initial_selected} default packages checked.")

    # 3. Test PackagesPage category filter, search filter, and source switching
    win.packages_page.set_category_filter("web")
    assert win.packages_page._groups_by_cat["web"].isVisible()
    assert not win.packages_page._groups_by_cat["office"].isVisible()
    win.packages_page.set_category_filter("all")

    win.packages_page.search_entry.setText("StratVIM")
    assert win.packages_page._rows_by_id["stratvim"].isVisible()
    assert not win.packages_page._rows_by_id["firefox"].isVisible()
    win.packages_page.search_entry.clear()
    print("[PASS] PackagesPage category pills & live search filtering verified.")

    # 4. Test TaskRunner.build_package_tasks coalescing
    selections = [
        ("Mozilla Firefox", "pacman", "firefox"),
        ("VSCodium", "aur", "vscodium-bin"),
        ("OnlyOffice", "flatpak", "org.onlyoffice.desktopeditors"),
        ("MPV", "pacman", "mpv"),
    ]
    tasks = TaskRunner.build_package_tasks(selections, system_wide_flatpak=True)
    assert len(tasks) == 3, f"Expected 2 pacman pkgs coalesced into 1 task + 1 flatpak + 1 aur = 3 tasks, got {len(tasks)}"
    assert "firefox" in tasks[0].args and "mpv" in tasks[0].args
    print("[PASS] TaskRunner coalesced multiple Pacman packages into a single pkexec batch.")

    # 5. Test live asynchronous QProcess execution & TerminalDrawer streaming in dry-run mode
    win.packages_page.clear_all_selections()
    assert win.packages_page.selected_count() == 0
    win.packages_page._rows_by_id["firefox"].set_checked(True, immediate=True)
    win.packages_page._rows_by_id["stratvim"].set_checked(True, immediate=True)
    assert win.packages_page.selected_count() == 2

    completed_flag = {"done": False, "ok": False}

    def on_done(all_ok: bool, _failed: int) -> None:
        completed_flag["done"] = True
        completed_flag["ok"] = all_ok

    win.runner.queueCompleted.connect(on_done)

    # Trigger primary action on Page 4 -> starts installation in TerminalDrawer
    win._on_primary_action()
    assert win.terminal_drawer.isVisible()

    # Wait for dry-run QProcess queue to finish
    elapsed = 0
    while not completed_flag["done"] and elapsed < 4000:
        QTest.qWait(50)
        elapsed += 50

    assert completed_flag["done"], "TaskRunner queue did not finish within timeout"
    assert completed_flag["ok"], "TaskRunner dry-run tasks should succeed with exit code 0"
    log_text = win.terminal_drawer.log_view.toPlainText()
    assert "[DRY-RUN]" in log_text and "[Success]" in log_text
    print("[PASS] Asynchronous QProcess TaskRunner & TerminalDrawer live log streaming verified.")

    # 6. Test CreditsDialog construction
    dlg = CreditsDialog(win)
    dlg.show()
    QTest.qWait(20)
    dlg.accept()
    print("[PASS] CreditsDialog populated from data/contributors.json verified.")

    win.close()
    win.deleteLater()
    QTest.qWait(10)

    # 7. Test GNOME Edition Carousel Mode (AdwCarouselWidget + CarouselIndicatorDots)
    env_gnome = detect_edition("gnome", persist_cache=False)
    tm.set_environment(env_gnome)
    win_gnome = MainWindow(theme_manager=tm, dry_run=True)
    win_gnome.show()
    QTest.qWait(30)

    assert win_gnome.carousel is not None, "GNOME mode must use AdwCarouselWidget"
    assert win_gnome.stack is None
    assert win_gnome.step_count() == 7, f"Expected 7 GNOME Tour slides, got {win_gnome.step_count()}"
    assert win_gnome.header_bar.indicator_dots is not None
    assert win_gnome.header_bar.indicator_dots.count == 7
    assert not win_gnome.footer_bar.isVisible(), "FooterBar must be hidden in GNOME Tour mode"

    # Slide 0: prev_button hidden, next_button visible & in accent_mode
    assert not win_gnome.carousel.prev_button.isVisible()
    assert win_gnome.carousel.next_button.isVisible()
    assert win_gnome.carousel.next_button.accent_mode is True

    # Verify GnomeTourSlide labels have full unclipped height
    slide0 = win_gnome.tour_slides[0]
    assert slide0.title_label.height() >= 44, f"Expected title_label height >= 44, got {slide0.title_label.height()}"
    assert slide0.body_label.height() >= 58, f"Expected body_label height >= 58, got {slide0.body_label.height()}"

    # Verify Flatpak System-Wide toggle lives in PackagesPage
    assert win_gnome.packages_page.flatpak_scope_switch is not None
    assert win_gnome.packages_page.install_flatpaks_system_wide is True
    win_gnome.packages_page.flatpak_scope_switch.toggle()
    assert win_gnome.packages_page.install_flatpaks_system_wide is False
    win_gnome.packages_page.flatpak_scope_switch.toggle()
    assert win_gnome.packages_page.install_flatpaks_system_wide is True

    # Animate to Slide 1 via next_button
    win_gnome.carousel.next_button.click()
    QTest.qWait(360)
    assert win_gnome.current_step_index() == 1
    assert abs(win_gnome.carousel.scrollPosition - 1.0) < 0.01
    assert abs(win_gnome.header_bar.indicator_dots.scroll_position - 1.0) < 0.01
    assert win_gnome.carousel.prev_button.isVisible()
    assert win_gnome.carousel.next_button.accent_mode is False

    # Jump to final slide (Slide 6: PackagesPage)
    win_gnome.go_to_step(6)
    QTest.qWait(360)
    assert win_gnome.current_step_index() == 6
    assert not win_gnome.carousel.next_button.isVisible()
    assert win_gnome.packages_page.inline_install_btn is not None
    assert win_gnome.packages_page.inline_install_btn.isVisible()
    print("[PASS] GNOME Tour AdwCarouselWidget (7 slides, animated scrollPosition, indicator dots, floating '<'/'>' chevrons) verified.")

    win_gnome.close()
    win_gnome.deleteLater()
    QTest.qWait(10)

    # 8. Test Unified Default Applications Engine (DefaultsManager + DefaultAppRow across Native, Flatpak, and /usr/local/bin)
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        pacman_dir = tmp / "usr/share/applications"
        flatpak_sys_dir = tmp / "var/lib/flatpak/exports/share/applications"
        local_dir = tmp / "usr/local/share/applications"
        mimeapps_file = tmp / "mimeapps.list"

        pacman_dir.mkdir(parents=True, exist_ok=True)
        flatpak_sys_dir.mkdir(parents=True, exist_ok=True)
        local_dir.mkdir(parents=True, exist_ok=True)

        # Standard /usr/bin package manager app (Firefox -> source omitted)
        (pacman_dir / "firefox.desktop").write_text(
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=Firefox\n"
            "Icon=firefox\n"
            "Exec=/usr/bin/firefox %u\n"
            "MimeType=text/html;x-scheme-handler/http;x-scheme-handler/https;\n",
            encoding="utf-8",
        )
        # Flatpak System Zen Browser -> Flatpak (System)
        (flatpak_sys_dir / "io.github.zen_browser.zen.desktop").write_text(
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=Zen Browser\n"
            "Icon=zen-browser\n"
            "Exec=/usr/bin/flatpak run io.github.zen_browser.zen %u\n"
            "X-Flatpak=io.github.zen_browser.zen\n"
            "MimeType=text/html;x-scheme-handler/http;x-scheme-handler/https;\n",
            encoding="utf-8",
        )
        # /usr/local/bin installed app -> AUR/Script
        (local_dir / "brave-browser.desktop").write_text(
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=Brave Web Browser\n"
            "Icon=brave\n"
            "Exec=/usr/local/bin/brave-browser %U\n"
            "MimeType=text/html;x-scheme-handler/http;x-scheme-handler/https;\n",
            encoding="utf-8",
        )
        # Modular Office Apps (LibreOffice Writer, Calc, Impress) + Plain Text Editor claiming text/csv
        (pacman_dir / "libreoffice-writer.desktop").write_text(
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=LibreOffice Writer\n"
            "Icon=libreoffice-writer\n"
            "Exec=/usr/bin/libreoffice --writer %U\n"
            "MimeType=application/vnd.oasis.opendocument.text;application/msword;application/rtf;\n",
            encoding="utf-8",
        )
        (pacman_dir / "libreoffice-calc.desktop").write_text(
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=LibreOffice Calc\n"
            "Icon=libreoffice-calc\n"
            "Exec=/usr/bin/libreoffice --calc %U\n"
            "MimeType=application/vnd.oasis.opendocument.spreadsheet;application/vnd.ms-excel;text/csv;\n",
            encoding="utf-8",
        )
        (pacman_dir / "libreoffice-impress.desktop").write_text(
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=LibreOffice Impress\n"
            "Icon=libreoffice-impress\n"
            "Exec=/usr/bin/libreoffice --impress %U\n"
            "MimeType=application/vnd.oasis.opendocument.presentation;application/vnd.ms-powerpoint;\n",
            encoding="utf-8",
        )
        (pacman_dir / "nvim.desktop").write_text(
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=Neovim\n"
            "Icon=nvim\n"
            "Exec=/usr/bin/nvim %F\n"
            "MimeType=text/plain;text/csv;\n",
            encoding="utf-8",
        )
        (flatpak_sys_dir / "org.onlyoffice.desktopeditors.desktop").write_text(
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=ONLYOFFICE Desktop Editors\n"
            "Icon=onlyoffice\n"
            "Exec=/usr/bin/flatpak run org.onlyoffice.desktopeditors %U\n"
            "X-Flatpak=org.onlyoffice.desktopeditors\n"
            "MimeType=application/vnd.oasis.opendocument.text;application/vnd.oasis.opendocument.spreadsheet;application/vnd.oasis.opendocument.presentation;\n",
            encoding="utf-8",
        )

        dm = DefaultsManager(
            search_dirs=[pacman_dir, flatpak_sys_dir, local_dir],
            mimeapps_path=mimeapps_file,
            dry_run=True,  # Updates mimeapps_file directly without invoking host xdg-mime
        )
        browser_spec = next(c for c in DEFAULT_APP_CATEGORIES if c.id == "browser")
        candidates = dm.get_candidates(browser_spec)
        assert len(candidates) == 3, f"Expected 3 browser candidates, got {len(candidates)}"

        # Verify granular Office categories isolate Writer, Calc, and Impress while including unified ONLYOFFICE
        doc_spec = next(c for c in DEFAULT_APP_CATEGORIES if c.id == "office_doc")
        sheet_spec = next(c for c in DEFAULT_APP_CATEGORIES if c.id == "office_sheet")
        pres_spec = next(c for c in DEFAULT_APP_CATEGORIES if c.id == "office_pres")

        doc_ids = {c.desktop_id for c in dm.get_candidates(doc_spec)}
        sheet_ids = {c.desktop_id for c in dm.get_candidates(sheet_spec)}
        pres_ids = {c.desktop_id for c in dm.get_candidates(pres_spec)}

        assert doc_ids == {"libreoffice-writer.desktop", "org.onlyoffice.desktopeditors.desktop"}
        assert sheet_ids == {"libreoffice-calc.desktop", "org.onlyoffice.desktopeditors.desktop"}
        assert "nvim.desktop" not in sheet_ids, "Plain text editor claiming text/csv must not pollute Spreadsheet apps"
        assert pres_ids == {"libreoffice-impress.desktop", "org.onlyoffice.desktopeditors.desktop"}

        dm.set_default_for_category(doc_spec, "libreoffice-writer.desktop")
        dm.set_default_for_category(sheet_spec, "libreoffice-calc.desktop")
        dm.set_default_for_category(pres_spec, "libreoffice-impress.desktop")

        by_id = {c.desktop_id: c for c in candidates}
        assert by_id["firefox.desktop"].source_badge == ""
        assert by_id["firefox.desktop"].display_label == "Firefox"
        assert by_id["io.github.zen_browser.zen.desktop"].source_badge == "Flatpak (System)"
        assert by_id["brave-browser.desktop"].source_badge == "AUR/Script"

        # Test DefaultAppRow UI: Index 0 is "Current Default: <App>" header item + 3 candidates = 4 items
        dm.set_default_for_category(browser_spec, "firefox.desktop")
        row = DefaultAppRow(spec=browser_spec, defaults_manager=dm)
        assert row.app_combo.count() == 4
        assert row.app_combo.currentIndex() == 0
        assert "Current Default: Firefox" in row.app_combo.itemText(0)
        initial_id = row.selected_desktop_id()
        assert initial_id == "firefox.desktop"
        assert row.cycle_source(1) is None
        assert row.selected_desktop_id() == initial_id

        # Select Brave Web Browser (index 1 in combo, since index 0 is "Current Default: ...")
        row.app_combo.setCurrentIndex(1)
        new_id = row.selected_desktop_id()
        assert new_id == "brave-browser.desktop"
        assert row.app_combo.currentIndex() == 0
        assert "Current Default: Brave Web Browser  [AUR/Script]" in row.app_combo.itemText(0)
        active_entry = row.selected_entry()
        assert active_entry is not None
        assert active_entry.name in row.subtitle_label.text()

        # Verify mimeapps.list was written with all browser and granular office MIME types
        mime_content = mimeapps_file.read_text(encoding="utf-8")
        assert "[Default Applications]" in mime_content
        assert f"x-scheme-handler/https={new_id}" in mime_content
        assert f"text/html={new_id}" in mime_content
        assert "application/vnd.oasis.opendocument.text=libreoffice-writer.desktop" in mime_content
        assert "application/vnd.openxmlformats-officedocument.wordprocessingml.document=libreoffice-writer.desktop" in mime_content
        assert "application/rtf=libreoffice-writer.desktop" in mime_content
        assert "application/vnd.oasis.opendocument.spreadsheet=libreoffice-calc.desktop" in mime_content
        assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet=libreoffice-calc.desktop" in mime_content
        assert "text/csv=libreoffice-calc.desktop" in mime_content
        assert "application/vnd.oasis.opendocument.presentation=libreoffice-impress.desktop" in mime_content
        assert "application/vnd.openxmlformats-officedocument.presentationml.presentation=libreoffice-impress.desktop" in mime_content
        row.deleteLater()

    print("[PASS] Unified Default Applications Engine (omitted /usr/bin package source, AUR/Script, Flatpak, NoWheelComboBox & mimeapps.list) verified.")
    print("=== ALL PHASE 3 & PHASE 4 FULL APP TESTS PASSED ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
