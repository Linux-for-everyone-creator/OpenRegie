"""Das Hauptfenster – Aussehen nach dem Entwurf „Hauptfenster (Build 1)“.

  ┌──────────────────────────────────────────────────────────────────────┐
  │ [■] OpenRegie         ( ● OBS verbunden )        ( ● ON AIR ) 18:57:12 │  Kopfleiste
  ├──────────────────────────────────────────────────────────────────────┤
  │ (Hinweis, wenn mit OBS etwas nicht stimmt)  [OBS starten] [Neu]       │  Meldungsleiste
  ├──────────────┬──────────────────────────────┬────────────────────────┤
  │ Bibliothek ↻+│  Live-Bild (roter Rahmen,    │ AUSGEWÄHLT             │
  │ ┌────┐┌────┐ │  wenn live)                  │ Countdown | Circles    │
  │ │Kach││Kach│ │                              │ Countdown / Texte      │
  │ └────┘└────┘ ├──────────────────────────────┤                        │
  │ LAMPEN ● ● ● │  Twitch-Streamtitel          │ [▶ Einblenden][■ Aus…] │
  └──────────────┴──────────────────────────────┴────────────────────────┘
   OpenRegie · Vorabversion · Build 1.1   ← Wasserzeichen unten links
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QTime, Qt, QTimer
from PySide6.QtWidgets import (QGraphicsOpacityEffect, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
                               QSizePolicy, QStackedWidget, QVBoxLayout, QWidget)

from .. import einstellungen
from ..obs.motor import MotorZustand, ObsMotor
from ..obs.verbindung import ObsVerbindung, Sendung, Status
from ..obs.vorschau import Vorschau
from ..twitch.konto import TwitchKonto
from ..uno.verwaltung import UnoVerwaltung
from .bausteine import Logo, OnAirLicht, VerbindungsAnzeige, VorschauBild, beschriftung, flaeche, knopf
from .overlay_bereich import Bibliothek, OverlayBedienfeld, UnoEinrichtung
from .stil import stylesheet
from .twitch_bereich import TwitchBereich

log = logging.getLogger("openregie.fenster")

STREAM_STOPP_WARTEN_MS = 15000


class Hauptfenster(QMainWindow):
    def __init__(self, E, verbindung: ObsVerbindung, vorschau: Vorschau, motor: ObsMotor,
                 uno: UnoVerwaltung, twitch: TwitchKonto):
        super().__init__()
        self.E = E
        self.verbindung = verbindung
        self.vorschau = vorschau
        self.motor = motor
        self.uno = uno
        self.twitch = twitch
        self._sammlung_text = ""
        self._einrichtung_vom_nutzer = False
        self._schliessen_erlaubt = False
        self._stoppt_fuer_ende = False
        t, g = E.texte, E.groessen

        self.setWindowTitle(f"{t.programmname} – {t.untertitel}")
        self.setStyleSheet(stylesheet(E))
        self.resize(int(g.fenster_breite), int(g.fenster_hoehe))

        mitte = QWidget()
        mitte.setObjectName("zentrale")
        # Beim Start soll kein Knopf markiert sein: die Fläche selbst bekommt den Fokus.
        mitte.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setCentralWidget(mitte)
        haupt = QVBoxLayout(mitte)
        haupt.setContentsMargins(0, 0, 0, 0)
        haupt.setSpacing(0)

        # --- Kopfleiste ---------------------------------------------------
        kopf = flaeche("kopfleiste")
        kl = QHBoxLayout(kopf)
        kl.setContentsMargins(g.abstand * 2, g.abstand, g.abstand * 2, g.abstand)
        kl.setSpacing(g.abstand)
        kl.addWidget(Logo(E))
        name = QVBoxLayout()
        name.setSpacing(0)
        name.addWidget(beschriftung(t.programmname, "programmname"))
        name.addWidget(beschriftung(t.untertitel, "untertitel"))
        kl.addLayout(name)
        kl.addStretch(1)
        self.verbindungsanzeige = VerbindungsAnzeige(E)
        kl.addWidget(self.verbindungsanzeige)
        kl.addStretch(1)
        self.on_air = OnAirLicht(E)
        kl.addWidget(self.on_air)
        kl.addSpacing(g.abstand)
        self.uhr = beschriftung("", "uhr")
        kl.addWidget(self.uhr)
        haupt.addWidget(kopf)

        inhalt = QVBoxLayout()
        # unten Platz für das Wasserzeichen lassen
        inhalt.setContentsMargins(g.abstand, g.abstand, g.abstand, g.abstand + g.schrift_klein + 8)
        inhalt.setSpacing(g.abstand)
        haupt.addLayout(inhalt, 1)

        # --- Meldungsleiste (nur sichtbar, wenn etwas nicht stimmt) --------
        # Sitzt in der Mitte unter „Live-Bild“ (es geht ja um OBS) – nicht über allen Spalten,
        # sonst fehlt rechts die Höhe für Countdown und Knöpfe.
        self.meldungsleiste = flaeche()
        ml = QHBoxLayout(self.meldungsleiste)
        ml.setContentsMargins(g.abstand, g.abstand // 2, g.abstand, g.abstand // 2)
        self.meldungstext = QLabel("")
        self.meldungstext.setObjectName("meldung")
        self.meldungstext.setWordWrap(True)
        ml.addWidget(self.meldungstext, 1)
        self.knopf_obs_starten = knopf(t.knopf_obs_starten)
        self.knopf_obs_starten.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.knopf_obs_starten.clicked.connect(self.obs_starten)
        ml.addWidget(self.knopf_obs_starten)
        self.knopf_neu = knopf(t.knopf_verbinden)
        self.knopf_neu.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.knopf_neu.clicked.connect(self.verbindung.jetzt_neu_verbinden)
        ml.addWidget(self.knopf_neu)

        # --- Mitte: Bibliothek | Live-Bild + Twitch | Ausgewählt -------------
        reihe = QHBoxLayout()
        reihe.setSpacing(g.abstand)
        inhalt.addLayout(reihe, 1)
        rand = g.abstand + 8

        links = flaeche()
        links.setFixedWidth(int(g.bibliothek_breite))
        ll = QVBoxLayout(links)
        ll.setContentsMargins(rand, rand, rand, rand)
        self.bibliothek = Bibliothek(E, uno)
        ll.addWidget(self.bibliothek, 1)
        reihe.addWidget(links)

        spalte = QVBoxLayout()
        spalte.setSpacing(g.abstand)
        szenenzeile = QHBoxLayout()
        szenenzeile.addWidget(beschriftung(t.vorschau_ueberschrift, "ueberschrift"))
        szenenzeile.addStretch(1)
        self.szenenname = beschriftung("", "gedimmt")
        szenenzeile.addWidget(self.szenenname)
        spalte.addLayout(szenenzeile)
        spalte.addWidget(self.meldungsleiste)
        self.vorschaubild = VorschauBild(E)
        spalte.addWidget(self.vorschaubild, 1)

        twitch_flaeche = flaeche()
        tl = QVBoxLayout(twitch_flaeche)
        tl.setContentsMargins(rand, rand, rand, rand)
        self.twitch_bereich = TwitchBereich(E, twitch)
        tl.addWidget(self.twitch_bereich)
        spalte.addWidget(twitch_flaeche)
        reihe.addLayout(spalte, 1)

        rechts = flaeche()
        rechts.setFixedWidth(int(g.seitenleiste_breite))
        rl = QVBoxLayout(rechts)
        rl.setContentsMargins(rand, rand, rand, rand)
        self.bedienfelder = QStackedWidget()
        self.uno_einrichtung = UnoEinrichtung(E, uno)
        self.overlay_bedienfeld = OverlayBedienfeld(E, uno)
        self.bedienfelder.addWidget(self.uno_einrichtung)
        self.bedienfelder.addWidget(self.overlay_bedienfeld)
        rl.addWidget(self.bedienfelder)
        reihe.addWidget(rechts)

        # --- Wasserzeichen mit Build-Nummer unten links ---------------------
        self.build = QLabel(einstellungen.build_anzeige(E), mitte)
        self.build.setObjectName("build")
        self.build.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        deckkraft = QGraphicsOpacityEffect(self.build)
        deckkraft.setOpacity(float(g.build_deckkraft))
        self.build.setGraphicsEffect(deckkraft)
        self.build.adjustSize()

        # --- Bedienung ------------------------------------------------------
        self.bibliothek.gewaehlt.connect(self._overlay_zeigen)
        self.bibliothek.einrichten_geklickt.connect(lambda: self._einrichtung_zeigen(vom_nutzer=True))
        self.uno_einrichtung.zurueck_geklickt.connect(self._zurueck_zur_auswahl)
        # Wer selbst einfügt oder entfernt, bleibt auf der Seite und sieht die Meldung
        self.uno_einrichtung.einfuegen.clicked.connect(lambda: setattr(self, "_einrichtung_vom_nutzer", True))
        uno.liste_geaendert.connect(self._liste_geaendert)
        uno.meldung.connect(lambda text, fehler: self.bibliothek.meldung.zeigen(text, False if fehler else None))

        verbindung.status_geaendert.connect(self._status)
        verbindung.sendung_geaendert.connect(self._sendung)
        verbindung.szene_geaendert.connect(self._szene)
        vorschau.neues_bild.connect(self._bild)
        motor.zustand_geaendert.connect(lambda *_: self._meldungsleiste_auffrischen())
        motor.sammlung_meldung.connect(self._sammlung)

        self._stopp_uhr = QTimer(self)
        self._stopp_uhr.setSingleShot(True)
        self._stopp_uhr.timeout.connect(self._endgueltig_schliessen)

        self._uhr_takt = QTimer(self)
        self._uhr_takt.setInterval(500)
        self._uhr_takt.timeout.connect(self._uhr_stellen)
        self._uhr_takt.start()
        self._uhr_stellen()

        self._status(verbindung.status, verbindung.meldung)
        self._sendung(verbindung.sendung)
        self._liste_geaendert()
        mitte.setFocus()

    # ------------------------------------------------------------------
    def _uhr_stellen(self) -> None:
        self.uhr.setText(QTime.currentTime().toString("HH:mm:ss"))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        g = self.E.groessen
        self.build.adjustSize()
        mitte = self.centralWidget()
        self.build.move(g.abstand + 4, mitte.height() - self.build.height() - 6)
        self.build.raise_()

    # --- Overlays ---------------------------------------------------------
    def _overlay_zeigen(self, schluessel: str) -> None:
        overlay = self.uno.overlays.get(schluessel)
        if overlay is None:
            self._zurueck_zur_auswahl()
            return
        self.overlay_bedienfeld.zeigen(overlay)
        self.bedienfelder.setCurrentWidget(self.overlay_bedienfeld)

    def _einrichtung_zeigen(self, vom_nutzer: bool = True) -> None:
        self._einrichtung_vom_nutzer = vom_nutzer
        self.bibliothek.auswahl_aufheben()
        self.uno_einrichtung.projekte_zeigen()
        self.bedienfelder.setCurrentWidget(self.uno_einrichtung)

    def _zurueck_zur_auswahl(self) -> None:
        if self.uno.overlays:
            self._einrichtung_vom_nutzer = False
            self.bibliothek.waehlen(next(iter(self.uno.overlays)))
        else:
            self._einrichtung_zeigen(vom_nutzer=False)

    def _liste_geaendert(self) -> None:
        """Ohne Uno-Projekt: gleich die Einrichtung zeigen. Sonst das erste Overlay wählen."""
        gezeigt = self.overlay_bedienfeld.overlay
        if gezeigt is not None and self.uno.overlays.get(gezeigt.schluessel) not in (None, gezeigt):
            # Sicherheitsnetz: „Ausgewählt“ darf nie an einem alten Overlay hängen bleiben
            self.overlay_bedienfeld.zeigen(self.uno.overlays[gezeigt.schluessel])
        if self.bedienfelder.currentWidget() is self.uno_einrichtung and self._einrichtung_vom_nutzer:
            return  # Kevin ist gerade beim Einrichten – dort bleiben
        if self.bibliothek.gewaehlter is None:
            self._zurueck_zur_auswahl()

    # --- OBS ----------------------------------------------------------------
    def _status(self, status: Status, _meldung: str) -> None:
        self.verbindungsanzeige.zeigen_status(status)
        if status is not Status.VERBUNDEN:
            self.vorschaubild.text_setzen(self.E.texte.vorschau_keine_verbindung)
        elif not self.vorschaubild.hat_bild():
            self.vorschaubild.text_setzen(self.E.texte.vorschau_wartet)
        self._meldungsleiste_auffrischen()

    def _sammlung(self, text: str) -> None:
        self._sammlung_text = text
        self._meldungsleiste_auffrischen()

    def _meldungsleiste_auffrischen(self) -> None:
        v, m, t = self.verbindung, self.motor, self.E.texte
        text, obs_knopf, neu_knopf = "", False, False
        if v.verbunden:
            text = self._sammlung_text
        elif m.zustand is MotorZustand.STARTET:
            text = t.meldung_obs_startet  # bleibt stehen, bis OBS verbunden ist (kein Flackern)
        elif m.zustand is MotorZustand.FEHLER:
            text, obs_knopf, neu_knopf = m.meldung, True, True
        elif v.status is Status.GETRENNT and v.meldung:
            text, neu_knopf = v.meldung, True
            obs_knopf = not m.obs_laeuft()
        self.meldungsleiste.setVisible(bool(text))
        self.meldungstext.setText(text)
        self.knopf_obs_starten.setVisible(obs_knopf and not m.obs_laeuft())
        self.knopf_neu.setVisible(neu_knopf)

    def _sendung(self, sendung: Sendung) -> None:
        self.on_air.zeigen_sendung(sendung)
        self.vorschaubild.live_setzen(sendung is Sendung.AN)
        if self._stoppt_fuer_ende and sendung is Sendung.AUS:
            self._endgueltig_schliessen()

    def _szene(self, name: str) -> None:
        self.szenenname.setText(name)

    def _bild(self, bild) -> None:
        if self.verbindung.verbunden:
            self.vorschaubild.bild_setzen(bild)

    def obs_starten(self) -> None:
        self.motor.starten()
        self._meldungsleiste_auffrischen()

    # --- Schließen ----------------------------------------------------------
    def frage_beenden(self) -> bool:
        """Große, einfache Nachfrage, wenn gerade live gestreamt wird."""
        t, g = self.E.texte, self.E.groessen
        box = QMessageBox(self)
        box.setWindowTitle(t.frage_beenden_live_titel)
        box.setText(t.frage_beenden_live)
        box.setIcon(QMessageBox.Icon.Warning)
        ja = box.addButton(t.knopf_beenden_ja, QMessageBox.ButtonRole.DestructiveRole)
        nein = box.addButton(t.knopf_beenden_nein, QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(nein)
        box.setStyleSheet(stylesheet(self.E) + f"QMessageBox {{ background-color: {self.E.farben.flaeche}; }}"
                          f"QLabel {{ font-size: {g.schrift}px; }} QPushButton {{ min-width: 340px; }}")
        box.exec()
        return box.clickedButton() is ja

    def closeEvent(self, e):
        if self._schliessen_erlaubt:
            e.accept()
            return
        if self._stoppt_fuer_ende:
            e.ignore()
            return
        if self.motor.braucht_nachfrage_beim_beenden:
            if not self.frage_beenden():
                e.ignore()
                return
            # Erst den Stream sauber beenden, dann schließen (spätestens nach 15 s)
            log.info("Beende Stream vor dem Schließen")
            self._stoppt_fuer_ende = True
            self.verbindung.anfrage("StopStream")
            self._stopp_uhr.start(STREAM_STOPP_WARTEN_MS)
            e.ignore()
            return
        e.accept()

    def _endgueltig_schliessen(self) -> None:
        self._stopp_uhr.stop()
        self._schliessen_erlaubt = True
        self.close()
