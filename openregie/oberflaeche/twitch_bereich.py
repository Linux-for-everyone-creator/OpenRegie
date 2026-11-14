"""Twitch-Bereich unter der Vorschau: anmelden und Streamtitel ändern.

  Nicht angemeldet:   [ Mit Twitch anmelden ]
  Warten auf Bestätigung: Code groß anzeigen, [Twitch-Seite öffnen] [Abbrechen]
  Angemeldet:         Streamtitel [______________] [Titel ändern]   „Angemeldet als …“ [Abmelden]
"""

from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QSizePolicy, QVBoxLayout, QWidget

from ..twitch.konto import TITEL_HOECHSTLAENGE, Anmeldung, TwitchKonto
from .bausteine import beschriftung, knopf
from .overlay_bereich import meldung


def _fest(k, breite: int):
    k.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    k.setFixedWidth(breite)
    return k


class TwitchBereich(QWidget):
    def __init__(self, E, konto: TwitchKonto, parent=None, browser_oeffnen=None):
        super().__init__(parent)
        self.E = E
        self.konto = konto
        self._browser_oeffnen = browser_oeffnen or (lambda adresse: QDesktopServices.openUrl(QUrl(adresse)))
        self._seite = ""
        t, g = E.texte, E.groessen

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(g.abstand // 2)

        kopf = QHBoxLayout()
        kopf.addWidget(beschriftung(t.twitch_ueberschrift, "ueberschrift"))
        kopf.addStretch(1)
        self.konto_text = beschriftung("", "gedimmt")
        kopf.addWidget(self.konto_text)
        self.abmelden = _fest(knopf(t.knopf_twitch_abmelden), 200)
        self.abmelden.clicked.connect(konto.abmelden)
        kopf.addWidget(self.abmelden)
        lay.addLayout(kopf)

        # angemeldet: Titel ändern
        self.titel_reihe = QWidget()
        tr = QHBoxLayout(self.titel_reihe)
        tr.setContentsMargins(0, 0, 0, 0)
        tr.setSpacing(g.abstand // 2)
        self.titel = QLineEdit()
        self.titel.setMaxLength(TITEL_HOECHSTLAENGE)
        self.titel.setAccessibleName(t.twitch_ueberschrift)
        self.titel.returnPressed.connect(self.titel_aendern)
        tr.addWidget(self.titel, 1)
        self.uebernehmen = _fest(knopf(t.knopf_titel_uebernehmen, "einblenden"), 220)
        self.uebernehmen.clicked.connect(self.titel_aendern)
        tr.addWidget(self.uebernehmen)
        lay.addWidget(self.titel_reihe)

        # nicht angemeldet / wartet
        self.hinweis = beschriftung("", "hinweis_gross")
        self.hinweis.setWordWrap(True)
        lay.addWidget(self.hinweis)
        knoepfe = QHBoxLayout()
        knoepfe.setSpacing(g.abstand // 2)
        self.anmelden = knopf(t.knopf_twitch_anmelden, "twitch")
        self.anmelden.clicked.connect(self._anmelden)
        knoepfe.addWidget(self.anmelden)
        self.seite_oeffnen = knopf(t.knopf_twitch_seite, "twitch")
        self.seite_oeffnen.clicked.connect(lambda: self._seite and self._browser_oeffnen(self._seite))
        knoepfe.addWidget(self.seite_oeffnen)
        self.abbrechen = _fest(knopf(t.knopf_abbrechen), 200)
        self.abbrechen.clicked.connect(konto.anmeldung_abbrechen)
        knoepfe.addWidget(self.abbrechen)
        lay.addLayout(knoepfe)

        self.meldung = meldung()
        lay.addWidget(self.meldung)

        konto.anmeldung_geaendert.connect(self._zustand)
        konto.code_bereit.connect(self._code)
        konto.titel_geladen.connect(self._titel_geladen)
        konto.meldung.connect(lambda text, fehler: self.meldung.zeigen(text, not fehler))
        self._code_text = ""
        self._zustand(konto.zustand)

    def _zustand(self, zustand: Anmeldung) -> None:
        t = self.E.texte
        angemeldet = zustand is Anmeldung.ANGEMELDET
        wartet = zustand is Anmeldung.WARTET
        self.titel_reihe.setVisible(angemeldet)
        self.abmelden.setVisible(angemeldet)
        self.konto_text.setText(t.twitch_angemeldet.format(name=self.konto.name) if angemeldet else "")
        self.anmelden.setVisible(zustand is Anmeldung.ABGEMELDET)
        self.seite_oeffnen.setVisible(wartet)
        self.abbrechen.setVisible(wartet)
        self.hinweis.setVisible(not angemeldet)
        if zustand is Anmeldung.NICHT_EINGERICHTET:
            self.hinweis.setText(t.twitch_nicht_eingerichtet)
        elif zustand is Anmeldung.ABGEMELDET:
            self.hinweis.setText(t.twitch_abgemeldet)
        elif wartet:
            self.hinweis.setText(t.twitch_wartet.format(code=self._code_text))
            self.hinweis.setObjectName("ueberschrift")
            self.hinweis.style().unpolish(self.hinweis)
            self.hinweis.style().polish(self.hinweis)
            return
        self.hinweis.setObjectName("hinweis_gross")
        self.hinweis.style().unpolish(self.hinweis)
        self.hinweis.style().polish(self.hinweis)

    def _anmelden(self) -> None:
        self.meldung.zeigen("")
        self.konto.anmelden()

    def _code(self, code: str, adresse: str) -> None:
        self._code_text = code
        self._seite = adresse
        self._zustand(self.konto.zustand)
        if adresse:
            self._browser_oeffnen(adresse)

    def _titel_geladen(self, titel: str) -> None:
        # Nicht überschreiben, während Kevin gerade tippt
        if not self.titel.hasFocus() or not self.titel.text():
            self.titel.setText(titel)
            self.titel.setCursorPosition(0)

    def titel_aendern(self) -> None:
        self.uebernehmen.setEnabled(False)
        self.meldung.zeigen("…")

        def fertig(ok, text):
            self.uebernehmen.setEnabled(True)
            self.meldung.zeigen(text, ok)

        self.konto.titel_setzen(self.titel.text(), fertig)
