"""Bedienfeld für den Countdown (rechte Seite des Regiepults)."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..titel.countdown import Countdown, Zustand
from .bausteine import beschriftung, knopf


def schritt_text(sekunden: int, plus: bool) -> str:
    zeichen = "+" if plus else "−"
    if sekunden % 60 == 0:
        return f"{zeichen}{sekunden // 60} Min"
    return f"{zeichen}{sekunden} Sek"


class CountdownBereich(QWidget):
    einrichten_geklickt = Signal()

    def __init__(self, E, countdown: Countdown, parent=None):
        super().__init__(parent)
        self._E = E
        self.cd = countdown
        t, c = E.texte, E.countdown
        gross, klein = int(c.schritt_gross_sekunden), int(c.schritt_klein_sekunden)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(E.groessen.abstand)

        lay.addWidget(beschriftung(t.countdown_ueberschrift, "ueberschrift"))

        self.anzeige = beschriftung("00:00", "countdown_anzeige")
        self.anzeige.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.anzeige)
        self.zustand_text = beschriftung("", "countdown_zustand")
        self.zustand_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.zustand_text)

        lay.addWidget(beschriftung(t.plus_minus_beschriftung, "gedimmt"))
        raster = QGridLayout()
        raster.setSpacing(E.groessen.abstand // 2)
        self.minus_gross = knopf(schritt_text(gross, False))
        self.plus_gross = knopf(schritt_text(gross, True))
        self.minus_klein = knopf(schritt_text(klein, False))
        self.plus_klein = knopf(schritt_text(klein, True))
        raster.addWidget(self.minus_gross, 0, 0)
        raster.addWidget(self.plus_gross, 0, 1)
        raster.addWidget(self.minus_klein, 1, 0)
        raster.addWidget(self.plus_klein, 1, 1)
        lay.addLayout(raster)
        self.minus_gross.clicked.connect(lambda: self._aendern(-gross))
        self.plus_gross.clicked.connect(lambda: self._aendern(gross))
        self.minus_klein.clicked.connect(lambda: self._aendern(-klein))
        self.plus_klein.clicked.connect(lambda: self._aendern(klein))

        reihe = QHBoxLayout()
        reihe.setSpacing(E.groessen.abstand // 2)
        self.start = knopf(t.knopf_start, "start")
        self.pause = knopf(t.knopf_pause, "pause")
        self.stopp = knopf(t.knopf_stopp, "stopp")
        for k in (self.start, self.pause, self.stopp):
            reihe.addWidget(k)
        lay.addLayout(reihe)
        self.start.clicked.connect(lambda: self._bedienen(self.cd.start))
        self.pause.clicked.connect(lambda: self._bedienen(self.cd.pause))
        self.stopp.clicked.connect(lambda: self._bedienen(self.cd.stopp))

        lay.addSpacing(E.groessen.abstand)
        self.einrichten = knopf(t.knopf_einrichten)
        self.einrichten.clicked.connect(self.einrichten_geklickt)
        lay.addWidget(self.einrichten)
        self.meldung = QLabel("")
        self.meldung.setObjectName("meldung")
        self.meldung.setWordWrap(True)
        lay.addWidget(self.meldung)
        lay.addStretch(1)

        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self.auffrischen)
        self._timer.start()
        self.auffrischen()

    def _aendern(self, sekunden: int) -> None:
        self.cd.aendern(sekunden)
        self.auffrischen()

    def _bedienen(self, aktion) -> None:
        aktion()
        self.auffrischen()

    def meldung_zeigen(self, text: str, erfolg: bool | None = None) -> None:
        f = self._E.farben
        farbe = {True: f.status_verbunden, False: f.status_getrennt, None: f.text}[erfolg]
        self.meldung.setStyleSheet(f"color: {farbe};")
        self.meldung.setText(text)

    def auffrischen(self) -> None:
        t = self._E.texte
        zustand = self.cd.zustand
        rest = self.cd.rest()
        self.anzeige.setText(self.cd.text())
        self.zustand_text.setText({
            Zustand.BEREIT: t.countdown_zustand_bereit,
            Zustand.LAEUFT: t.countdown_zustand_laeuft,
            Zustand.PAUSIERT: t.countdown_zustand_pausiert,
            Zustand.ABGELAUFEN: t.countdown_zustand_abgelaufen,
        }[zustand])

        self.start.setText(t.knopf_weiter if zustand is Zustand.PAUSIERT else t.knopf_start)
        # Start/Weiter: nicht während er läuft; aus dem Stand nur mit Dauer > 0
        self.start.setEnabled(zustand is Zustand.PAUSIERT
                              or (zustand is not Zustand.LAEUFT and self.cd.dauer > 0))
        self.pause.setEnabled(zustand is Zustand.LAEUFT)
        self.stopp.setEnabled(zustand is not Zustand.BEREIT)
        hoechst = self.cd.hoechstdauer
        # Minus geht nicht, wenn schon 0; Plus nicht, wenn schon am Höchstwert.
        # Im Stand zählt die Dauer, sonst die restliche Zeit (wie in Countdown.aendern).
        bezug = self.cd.dauer if zustand in (Zustand.BEREIT, Zustand.ABGELAUFEN) else rest
        self.minus_gross.setEnabled(bezug > 0)
        self.minus_klein.setEnabled(bezug > 0)
        self.plus_gross.setEnabled(bezug < hoechst)
        self.plus_klein.setEnabled(bezug < hoechst)
