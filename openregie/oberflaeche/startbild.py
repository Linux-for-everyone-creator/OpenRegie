"""Ladebildschirm: zeigt Name, Untertitel und was gerade passiert,
solange OBS im Hintergrund startet und sich verbindet."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from .. import einstellungen


class Startbild(QWidget):
    def __init__(self, E, symbol: Path | None = None, parent=None):
        super().__init__(parent, Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint)
        f, g, t = E.farben, E.groessen, E.texte
        self.setWindowTitle(t.programmname)
        self.setFixedSize(int(g.start_breite), int(g.start_hoehe))
        self.setObjectName("startbild")
        self.setStyleSheet(
            f"QWidget#startbild {{ background-color: {f.flaeche}; border: 3px solid {f.rahmen};"
            f" border-radius: {g.knopf_rundung}px; }}"
            f"QLabel {{ color: {f.text}; background: transparent; }}")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(48, 40, 48, 28)
        lay.setSpacing(8)
        if symbol is not None and symbol.exists():
            bild = QLabel()
            bild.setPixmap(QIcon(str(symbol)).pixmap(96, 96))
            bild.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(bild)
        name = QLabel(t.programmname)
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name.setStyleSheet(f"font-size: {g.start_schrift_name}px; font-weight: 900;")
        lay.addWidget(name)
        untertitel = QLabel(t.untertitel)
        untertitel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        untertitel.setStyleSheet(f"font-size: {g.schrift_titel - 4}px; color: {f.text_gedimmt};")
        lay.addWidget(untertitel)
        lay.addStretch(1)
        self.zustand = QLabel("")
        self.zustand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zustand.setWordWrap(True)
        self.zustand.setStyleSheet(f"font-size: {g.schrift}px;")
        lay.addWidget(self.zustand)
        build = QLabel(einstellungen.build_anzeige(E))
        build.setAlignment(Qt.AlignmentFlag.AlignLeft)
        build.setStyleSheet(f"font-size: {g.schrift_klein}px; color: {f.text_gedimmt};")
        lay.addWidget(build)

    def text_setzen(self, text: str) -> None:
        self.zustand.setText(text)
