"""Der große Knopf „▶ Stream starten“ / „■ Stream beenden“ oben neben ON AIR (ab Build 1.2.3).

Ein Klick genügt. Starten geht sofort, Beenden fragt erst nach („Stream wirklich beenden?“).
Während OBS verbindet oder stoppt, ist der Knopf gesperrt (kein Doppelklick) und sagt, was gerade passiert.
Der Knopf spricht nie selbst mit OBS – nur mit der Zwischenschicht `obs/stream.py`.
"""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QSizePolicy, QToolTip

from ..obs.stream import Knopf, StreamSteuerung
from .bausteine import gesperrt_hinweis, knopf
from .stil import stylesheet


def frage_ja_nein(E, eltern, titel: str, text: str, ja_text: str, nein_text: str) -> bool:
    """Große, einfache Nachfrage mit zwei Knöpfen. Vorgewählt ist immer das Harmlose („nein“)."""
    g = E.groessen
    box = QMessageBox(eltern)
    box.setWindowTitle(titel)
    box.setText(text)
    box.setIcon(QMessageBox.Icon.Warning)
    ja = box.addButton(ja_text, QMessageBox.ButtonRole.DestructiveRole)
    nein = box.addButton(nein_text, QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(nein)
    box.setEscapeButton(nein)
    box.setStyleSheet(stylesheet(E) + f"QMessageBox {{ background-color: {E.farben.flaeche}; }}"
                      f"QLabel {{ font-size: {g.schrift}px; }} QPushButton {{ min-width: 340px; }}")
    box.exec()
    return box.clickedButton() is ja


class StreamKnopf:
    """Baut den Knopf und hält ihn passend zum echten Zustand von OBS."""

    def __init__(self, E, stream: StreamSteuerung, eltern):
        self.E, self.stream, self._eltern = E, stream, eltern
        t = E.texte
        self.knopf = knopf(t.knopf_stream_starten, "stream_starten")
        self.knopf.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.knopf.setFixedWidth(int(E.groessen.stream_knopf_breite))
        self.knopf.clicked.connect(self._geklickt)
        gesperrt_hinweis(self.knopf, self._grund, self._kurz_melden)
        # Für Tests austauschbar: gibt True zurück, wenn wirklich beendet werden soll
        self.frage_beenden = lambda: frage_ja_nein(E, eltern, t.frage_stream_beenden_titel, t.frage_stream_beenden,
                                                   t.knopf_stream_beenden_ja, t.knopf_stream_beenden_nein)
        stream.knopf_geaendert.connect(self._zeigen)
        self._zeigen(stream.knopf)

    def _geklickt(self) -> None:
        zustand = self.stream.knopf
        if zustand is Knopf.STARTEN:
            self.stream.starten()  # ohne Nachfrage
        elif zustand is Knopf.BEENDEN:
            if self.frage_beenden() and self.stream.knopf is Knopf.BEENDEN:
                self.stream.beenden()  # (läuft er noch? – er könnte in OBS beendet worden sein)

    def _zeigen(self, zustand: Knopf) -> None:
        t = self.E.texte
        text, name, frei = {
            Knopf.GESPERRT: (t.knopf_stream_starten, "stream_starten", False),
            Knopf.STARTEN: (t.knopf_stream_starten, "stream_starten", True),
            Knopf.VERBINDE: (t.knopf_stream_verbinde, "stream_wartet", False),
            Knopf.BEENDEN: (t.knopf_stream_beenden, "stream_beenden", True),
            Knopf.STOPPE: (t.knopf_stream_stoppe, "stream_wartet", False),
        }[zustand]
        k = self.knopf
        k.setText(text)
        k.setAccessibleName(text)
        k.setEnabled(frei)
        if k.objectName() != name:
            k.setObjectName(name)
            k.style().unpolish(k)  # neue Farbe übernehmen
            k.style().polish(k)

    def _grund(self) -> str:
        t = self.E.texte
        return {Knopf.GESPERRT: t.gesperrt_stream, Knopf.VERBINDE: t.gesperrt_stream_verbinde,
                Knopf.STOPPE: t.gesperrt_stream_stoppe}.get(self.stream.knopf, "")

    def _kurz_melden(self, text: str) -> None:
        k = self.knopf
        QToolTip.showText(k.mapToGlobal(k.rect().bottomLeft()), text, k)
