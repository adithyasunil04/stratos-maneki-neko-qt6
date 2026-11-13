#!/usr/bin/env python3
"""Interactive Phase 2 UI Showcase for StratOS Maneki Neko (PyQt6).

Run with:
    ./.venv/bin/python test_env/preview_ui.py
    ./.venv/bin/python test_env/preview_ui.py --edition gnome
    ./.venv/bin/python test_env/preview_ui.py --edition Hyprland
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt6 import QtCore, QtWidgets

from src.core.environment import detect_edition
from src.core.paths import DATA_DIR, register_qt_search_paths
from src.core.theme_manager import ThemeManager
from src.ui.components import (
    AdwActionRow,
    AdwPreferencesGroup,
    HeaderBar,
    RescueBanner,
)
from src.ui.navigation_filter import NavigationFilter


class Phase2ShowcaseWindow(QtWidgets.QMainWindow):
    """Interactive test harness for Phase 2 HeaderBar, AdwPreferencesGroup, AdwActionRow & WASD navigation."""

    def __init__(self, tm: ThemeManager) -> None:
        super().__init__()
        self.tm = tm
        self.setWindowTitle(
            f"StratOS Maneki Neko — Phase 2 UI Showcase ({tm.env_info.edition_label} / {tm.env_info.ui_mode.upper()})"
        )
        self.resize(940, 660)

        central = QtWidgets.QWidget(self)
        self.setCentralWidget(central)
        root_layout = QtWidgets.QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Persistent HeaderBar
        self.header_bar = HeaderBar(self.tm, parent=central)
        self.header_bar.stepClicked.connect(self._on_step_clicked)
        root_layout.addWidget(self.header_bar)

        # 2. Optional RescueBanner if qt6ct contrast rescue triggered
        if self.tm.rescued_from_broken_qt6ct:
            self.rescue_banner = RescueBanner(self.tm.rescue_reason, parent=central)
            root_layout.addWidget(self.rescue_banner)

        # 3. Top toolbar inside page for testing runtime GNOME <-> WM mode switch & search filter
        toolbar_frame = QtWidgets.QWidget(central)
        toolbar_layout = QtWidgets.QHBoxLayout(toolbar_frame)
        toolbar_layout.setContentsMargins(24, 14, 24, 6)
        toolbar_layout.setSpacing(12)

        self.search_entry = QtWidgets.QLineEdit(toolbar_frame)
        self.search_entry.setPlaceholderText(
            "Filter rows (tests that WASD keys type normally inside QLineEdit)..."
        )
        self.search_entry.textChanged.connect(self._on_search_changed)
        toolbar_layout.addWidget(self.search_entry, stretch=1)

        sim_btn = QtWidgets.QPushButton("Toggle GNOME / WM Layout Mode", toolbar_frame)
        sim_btn.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        sim_btn.clicked.connect(self._toggle_edition_simulation)
        toolbar_layout.addWidget(sim_btn)

        root_layout.addWidget(toolbar_frame)

        # 4. Scrollable content area with AdwPreferencesGroups & AdwActionRows
        self.scroll = QtWidgets.QScrollArea(central)
        self.scroll.setWidgetResizable(True)
        self.scroll_content = QtWidgets.QWidget()
        self.scroll_layout = QtWidgets.QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(24, 10, 24, 20)
        self.scroll_layout.setSpacing(16)

        self._all_rows: list[AdwActionRow] = []
        self._build_sample_groups()

        self.scroll_layout.addStretch(1)
        self.scroll.setWidget(self.scroll_content)
        root_layout.addWidget(self.scroll, stretch=1)

        # 5. Bottom Footer Bar with live WASD / Arrow event log & navigation buttons
        footer = QtWidgets.QFrame(central)
        footer.setObjectName("FooterBar")
        footer_layout = QtWidgets.QHBoxLayout(footer)
        footer_layout.setContentsMargins(18, 10, 18, 10)
        footer_layout.setSpacing(12)

        key_hints = QtWidgets.QLabel(
            "Keys: [W/S or ↑/↓] Focus Row   [A/D or ←/→] Switch Package Source   [Space] Toggle   [Ctrl+T] Cycle Theme",
            footer,
        )
        key_hints.setObjectName("KeybindHint")
        footer_layout.addWidget(key_hints)

        footer_layout.addStretch(1)

        self.status_pill = QtWidgets.QLabel("Ready — try WASD or Arrow keys!", footer)
        self.status_pill.setObjectName("RowSubtitle")
        footer_layout.addWidget(self.status_pill)

        back_btn = QtWidgets.QPushButton("Back", footer)
        back_btn.clicked.connect(lambda: self._step_delta(-1))
        footer_layout.addWidget(back_btn)

        next_btn = QtWidgets.QPushButton("Next Step", footer)
        next_btn.setObjectName("PrimaryButton")
        next_btn.clicked.connect(lambda: self._step_delta(+1))
        footer_layout.addWidget(next_btn)

        root_layout.addWidget(footer)

        # Install NavigationFilter
        self.nav_filter = NavigationFilter(self, theme_manager=self.tm)
        self.nav_filter.navigateLeft.connect(lambda: self._step_delta(-1))
        self.nav_filter.navigateRight.connect(lambda: self._step_delta(+1))
        self.nav_filter.primaryActionRequested.connect(lambda: self._step_delta(+1))
        self.nav_filter.backActionRequested.connect(lambda: self._step_delta(-1))
        QtWidgets.QApplication.instance().installEventFilter(self.nav_filter)  # type: ignore[union-attr]

        # Focus first row automatically
        if self._all_rows:
            self._all_rows[0].setFocus()

    def _build_sample_groups(self) -> None:
        # Group 1: System Setup Action Rows (Button + Toggle examples)
        setup_group = AdwPreferencesGroup(
            title="System Setup Actions (AdwActionRow Demo)",
            description="Demonstrates action rows with icons, action buttons, and animated ToggleSwitch.",
            parent=self.scroll_content,
        )
        for title, sub, icon, is_toggle, action_txt in [
            (
                "Update System & Mirrors",
                "Synchronize Pacman repositories and upgrade installed packages",
                "icons:updates.png",
                False,
                "Update Now",
            ),
            (
                "Install Flatpaks System-Wide",
                "When disabled, Flatpaks are installed with --user for the current account",
                "icons:settings.png",
                True,
                None,
            ),
            (
                "Launch at Startup",
                "Automatically open Maneki Neko when logging into StratOS",
                "icons:maneki_neko.png",
                True,
                None,
            ),
        ]:
            row = AdwActionRow(
                title=title,
                subtitle=sub,
                icon_path=icon,
                has_toggle=is_toggle,
                checked=True,
                action_text=action_txt,
                parent=setup_group,
            )
            row.toggled.connect(
                lambda checked, t=title: self.status_pill.setText(
                    f"Toggled '{t}' -> {'ON' if checked else 'OFF'}"
                )
            )
            row.activated.connect(
                lambda t=title: self.status_pill.setText(f"Activated action: '{t}'")
            )
            setup_group.add_row(row)
            self._all_rows.append(row)

        self.scroll_layout.addWidget(setup_group)

        # Group 2+: Load first 2 categories from data/packages.json
        pkg_file = DATA_DIR / "packages.json"
        if pkg_file.is_file():
            data = json.loads(pkg_file.read_text(encoding="utf-8"))
            all_pkgs = data.get("packages", [])
            for cat in data.get("categories", [])[:2]:
                cat_id = cat["id"]
                cat_label = cat.get("label") or cat.get("title") or cat_id
                cat_pkgs = cat.get("packages") or [
                    p for p in all_pkgs if p.get("category") == cat_id
                ]
                cat_group = AdwPreferencesGroup(
                    title=f"Software Category: {cat_label}",
                    description=cat.get("description", ""),
                    parent=self.scroll_content,
                )
                for pkg in cat_pkgs:
                    sources = list(pkg.get("sources", {}).keys())
                    row = AdwActionRow(
                        title=pkg["name"],
                        subtitle=pkg.get("summary") or pkg.get("description", ""),
                        icon_path=pkg.get("icon"),
                        has_toggle=True,
                        checked=pkg.get("default_checked", False),
                        sources=sources,
                        default_source=pkg.get("default_source"),
                        row_id=pkg["id"],
                        parent=cat_group,
                    )
                    row.toggled.connect(
                        lambda checked, n=pkg["name"]: self.status_pill.setText(
                            f"{n}: {'Selected' if checked else 'Unselected'}"
                        )
                    )
                    row.sourceChanged.connect(
                        lambda src, n=pkg["name"]: self.status_pill.setText(
                            f"{n}: Switched source to [{src.upper()}]"
                        )
                    )
                    cat_group.add_row(row)
                    self._all_rows.append(row)
                self.scroll_layout.addWidget(cat_group)

    def _on_search_changed(self, query: str) -> None:
        q = query.strip().lower()
        for row in self._all_rows:
            visible = (
                not q
                or q in row.title_label.text().lower()
                or q in row.subtitle_label.text().lower()
            )
            row.setVisible(visible)

    def _on_step_clicked(self, index: int) -> None:
        self.status_pill.setText(f"Switched to Wizard Step {index + 1}")

    def _step_delta(self, delta: int) -> None:
        next_step = (self.header_bar.active_step + delta) % 4
        self.header_bar.set_active_step(next_step)
        self.status_pill.setText(f"Wizard Step -> {next_step + 1}")

    def _toggle_edition_simulation(self) -> None:
        if self.tm.env_info.ui_mode == "gnome":
            new_env = detect_edition("hyprland")
        else:
            new_env = detect_edition("gnome")
        self.tm.set_environment(new_env)
        # Rebuild HeaderBar to reflect WM font selector vs GNOME font button
        central_layout = self.centralWidget().layout()  # type: ignore[union-attr]
        old_header = self.header_bar
        self.header_bar = HeaderBar(self.tm, parent=self.centralWidget())
        self.header_bar.stepClicked.connect(self._on_step_clicked)
        central_layout.replaceWidget(old_header, self.header_bar)  # type: ignore[union-attr]
        old_header.deleteLater()
        self.setWindowTitle(
            f"StratOS Maneki Neko — Phase 2 UI Showcase ({new_env.edition_label} / {new_env.ui_mode.upper()})"
        )
        self.status_pill.setText(
            f"Switched layout to {new_env.edition_label} ({new_env.ui_mode.upper()}) — Font: {self.tm.env_info.font_family}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview Phase 2 UI components.")
    parser.add_argument(
        "--edition",
        choices=["auto", "gnome", "hyprland", "niri", "swayfx"],
        default="auto",
        help="Simulate a specific StratOS edition",
    )
    args = parser.parse_args()

    app = QtWidgets.QApplication(sys.argv)
    register_qt_search_paths()

    env_info = detect_edition(args.edition)
    tm = ThemeManager(app, env_info)

    win = Phase2ShowcaseWindow(tm)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
