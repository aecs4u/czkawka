from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QDialogButtonBox, QFrame,
    QTabWidget, QTextBrowser, QWidget
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QFont

from ..icons import app_logo_path
from ..localizer import tr


class AboutDialog(QDialog):
    """About dialog with tabs for information and credits."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("about-title"))
        self.setMinimumWidth(520)
        self.setMinimumHeight(500)

        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # Logo
        logo_path = app_logo_path()
        if logo_path:
            logo_label = QLabel()
            pixmap = QPixmap(logo_path)
            scaled = pixmap.scaledToHeight(300, Qt.SmoothTransformation)
            logo_label.setPixmap(scaled)
            logo_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(logo_label)

        title = QLabel(tr("about-app-name"))
        title_font = QFont()
        title_font.setPointSize(22)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel(tr("about-subtitle"))
        sub_font = QFont()
        sub_font.setPointSize(11)
        subtitle.setFont(sub_font)
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)

        version = QLabel(tr("about-version"))
        version.setAlignment(Qt.AlignCenter)
        version.setEnabled(False)
        layout.addWidget(version)

        # Tabs
        tabs = QTabWidget()
        tabs.addTab(self._build_about_tab(), tr("about-tab-about"))
        tabs.addTab(self._build_credits_tab(), tr("about-tab-credits"))
        tabs.addTab(self._build_license_tab(), tr("about-tab-license"))
        layout.addWidget(tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def _build_about_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        desc = QLabel(tr("about-description"))
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignCenter)
        layout.addWidget(desc)

        links = QTextBrowser()
        links.setOpenExternalLinks(True)
        links.setHtml(
            '<p style="text-align:center;">'
            '<a href="https://github.com/qarmin/czkawka">GitHub Repository</a>'
            "</p>"
        )
        links.setMaximumHeight(50)
        links.setFrameShape(QFrame.NoFrame)
        layout.addWidget(links)

        layout.addStretch()
        return w

    def _build_credits_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        credits = QTextBrowser()
        credits.setOpenExternalLinks(True)
        credits.setHtml(
            "<h3>Project</h3>"
            "<p>"
            '<b>Czkawka</b> &mdash; created by <a href="https://github.com/qarmin">Rafa\u0142 Mikrut (qarmin)</a>'
            "</p>"
            "<h3>Kalka Frontend</h3>"
            "<p>"
            '<b>Kalka</b> &mdash; PySide6/Qt frontend by <a href="https://github.com/aecs4u">aecs4u</a>'
            "</p>"
            "<h3>Key Libraries</h3>"
            "<table cellpadding='3'>"
            "<tr><td><b>PySide6</b></td><td>Qt for Python (LGPL)</td></tr>"
            "<tr><td><b>blake3</b></td><td>Fast cryptographic hashing</td></tr>"
            "<tr><td><b>image_hasher</b></td><td>Perceptual image hashing</td></tr>"
            "<tr><td><b>rusty-chromaprint</b></td><td>Audio fingerprinting</td></tr>"
            "<tr><td><b>vid_dup_finder_lib</b></td><td>Video duplicate detection</td></tr>"
            "<tr><td><b>lofty</b></td><td>Audio tag reading</td></tr>"
            "<tr><td><b>rayon</b></td><td>Parallel data processing</td></tr>"
            "<tr><td><b>strsim</b></td><td>String similarity metrics</td></tr>"
            "<tr><td><b>xxhash-rust</b></td><td>Fast non-cryptographic hashing</td></tr>"
            "<tr><td><b>Fluent</b></td><td>Localization system</td></tr>"
            "</table>"
            "<h3>Contributors</h3>"
            "<p>"
            "Thank you to all contributors who have submitted bug reports, "
            "feature requests, translations, and pull requests."
            "</p>"
            '<p><a href="https://github.com/qarmin/czkawka/graphs/contributors">'
            "View all contributors on GitHub</a></p>"
        )
        layout.addWidget(credits)
        return w

    def _build_license_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        license_text = QTextBrowser()
        license_text.setPlainText(
            "MIT License\n\n"
            "Copyright (c) 2020-2026 Rafa\u0142 Mikrut\n\n"
            "Permission is hereby granted, free of charge, to any person obtaining a copy "
            "of this software and associated documentation files (the \"Software\"), to deal "
            "in the Software without restriction, including without limitation the rights "
            "to use, copy, modify, merge, publish, distribute, sublicense, and/or sell "
            "copies of the Software, and to permit persons to whom the Software is "
            "furnished to do so, subject to the following conditions:\n\n"
            "The above copyright notice and this permission notice shall be included in all "
            "copies or substantial portions of the Software.\n\n"
            "THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR "
            "IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, "
            "FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE "
            "AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER "
            "LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, "
            "OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE "
            "SOFTWARE."
        )
        layout.addWidget(license_text)
        return w
