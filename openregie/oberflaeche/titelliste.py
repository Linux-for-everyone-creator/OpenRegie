"""Liste aller OpenRegie-Titel (linke Seite). Ein Klick wählt einen Titel aus.

Vorbereitet für später: Tally-Licht pro Titel (1.1), Knopf „Bearbeiten“ (1.2).
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QButtonGroup, QVBoxLayout, QWidget

from ..titel.basis import Titel
from .bausteine import beschriftung, knopf


class TitelListe(QWidget):
    titel_gewaehlt = Signal(str)  # Kennung des Titels

    def __init__(self, E, parent=None):
        super().__init__(parent)
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(E.groessen.abstand // 2)
        self._lay.addWidget(beschriftung(E.texte.titelliste_ueberschrift, "ueberschrift"))
        self._gruppe = QButtonGroup(self)
        self._gruppe.setExclusive(True)
        self.knoepfe: dict[str, object] = {}
        self._lay.addStretch(1)

    def hinzufuegen(self, titel: Titel) -> None:
        k = knopf(titel.name, "titel")
        k.setCheckable(True)
        k.clicked.connect(lambda _=False, kennung=titel.kennung: self.waehlen(kennung))
        self._gruppe.addButton(k)
        self.knoepfe[titel.kennung] = k
        self._lay.insertWidget(self._lay.count() - 1, k)  # vor dem Abstandhalter

    def waehlen(self, kennung: str) -> None:
        k = self.knoepfe.get(kennung)
        if k is not None:
            k.setChecked(True)
            self.titel_gewaehlt.emit(kennung)
