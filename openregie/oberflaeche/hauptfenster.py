"""Das Hauptfenster im Regiepult-Look.

  ┌──────────────────────────────────────────────────────────────┐
  │ OpenRegie            ● OBS verbunden              [ON AIR]  │  Kopfleiste
  ├──────────────────────────────────────────────────────────────┤
  │ (Hinweis, wenn OBS nicht verbunden ist)  [OBS starten] [Neu] │  Meldungsleiste
  ├──────────┬──────────────────────────────┬────────────────────┤
  │ Titel    │  Live-Vorschau               │  Bedienfeld des    │
  │ ▸ Countd.│                              │  gewählten Titels  │
  ├──────────┴──────────────────────────────┴────────────────────┤
  │ OpenRegie Build 1.0                                         │  Fußzeile
  └──────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import logging
import shlex

from PySide6.QtCore import QProcess, Qt, QTimer
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QMainWindow, QSizePolicy, QStackedWidget, QVBoxLayout,
                               QWidget)

from .. import einstellungen
from ..obs import zugang
from ..obs.einrichten import CountdownEinrichten
from ..obs.verbindung import ObsVerbindung, Status
from ..obs.vorschau import Vorschau
from ..titel.countdown import Countdown
from .bausteine import OnAirLicht, VerbindungsAnzeige, VorschauBild, beschriftung, flaeche, knopf
from .countdown_bereich import CountdownBereich
from .stil import stylesheet
from .titelliste import TitelListe

log = logging.getLogger("openregie.fenster")


class Hauptfenster(QMainWindow):
    def __init__(self, E, verbindung: ObsVerbindung, vorschau: Vorschau, countdown: Countdown,
                 countdown_adresse: str | None, start_meldung: str = ""):
        super().__init__()
        self.E = E
        self.verbindung = verbindung
        self.vorschau = vorschau
        self.countdown = countdown
        self.countdown_adresse = countdown_adresse
        self._einrichten_laeuft = None
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
        haupt.addWidget(kopf)

        inhalt = QVBoxLayout()
        inhalt.setContentsMargins(g.abstand, g.abstand, g.abstand, 0)
        inhalt.setSpacing(g.abstand)
        haupt.addLayout(inhalt, 1)

        # --- Meldungsleiste (nur sichtbar, wenn etwas nicht stimmt) --------
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
        inhalt.addWidget(self.meldungsleiste)

        # --- Mitte: Titel | Vorschau | Bedienfeld --------------------------
        reihe = QHBoxLayout()
        reihe.setSpacing(g.abstand)
        inhalt.addLayout(reihe, 1)

        links = flaeche()
        links.setFixedWidth(int(g.titelliste_breite))
        ll = QVBoxLayout(links)
        ll.setContentsMargins(g.abstand, g.abstand, g.abstand, g.abstand)
        self.titelliste = TitelListe(E)
        ll.addWidget(self.titelliste)
        reihe.addWidget(links)

        vorschau_flaeche = flaeche()
        vl = QVBoxLayout(vorschau_flaeche)
        vl.setContentsMargins(g.abstand, g.abstand, g.abstand, g.abstand)
        szenenzeile = QHBoxLayout()
        szenenzeile.addWidget(beschriftung(t.vorschau_ueberschrift, "ueberschrift"))
        szenenzeile.addStretch(1)
        self.szenenname = beschriftung("", "gedimmt")
        szenenzeile.addWidget(self.szenenname)
        vl.addLayout(szenenzeile)
        self.vorschaubild = VorschauBild(E)
        vl.addWidget(self.vorschaubild, 1)
        reihe.addWidget(vorschau_flaeche, 1)

        rechts = flaeche()
        rechts.setFixedWidth(int(g.seitenleiste_breite))
        rl = QVBoxLayout(rechts)
        rl.setContentsMargins(g.abstand, g.abstand, g.abstand, g.abstand)
        self.bedienfelder = QStackedWidget()
        rl.addWidget(self.bedienfelder)
        reihe.addWidget(rechts)

        # --- Fußzeile mit Build-Anzeige -----------------------------------
        fuss = QHBoxLayout()
        fuss.setContentsMargins(g.abstand + 4, 4, g.abstand, 8)
        self.build = beschriftung(einstellungen.build_anzeige(E), "build")
        fuss.addWidget(self.build)
        fuss.addStretch(1)
        haupt.addLayout(fuss)

        # --- Titel eintragen ---------------------------------------------
        self._bedienfeld_index: dict[str, int] = {}
        self.countdown_bereich = CountdownBereich(E, countdown)
        self.countdown_bereich.einrichten_geklickt.connect(self.countdown_einrichten)
        self._titel_eintragen(countdown, self.countdown_bereich)
        self.titelliste.titel_gewaehlt.connect(self._titel_zeigen)
        self.titelliste.waehlen(countdown.kennung)
        if start_meldung:
            self.countdown_bereich.meldung_zeigen(start_meldung, False)
            self.countdown_bereich.einrichten.setEnabled(False)

        # --- Signale ------------------------------------------------------
        verbindung.status_geaendert.connect(self._status)
        verbindung.sendung_geaendert.connect(self.on_air.zeigen)
        verbindung.szene_geaendert.connect(self._szene)
        vorschau.neues_bild.connect(self._bild)

        self._obs_start_sperre = QTimer(self)
        self._obs_start_sperre.setSingleShot(True)
        self._obs_start_sperre.timeout.connect(self._meldungsleiste_auffrischen)

        self._status(verbindung.status, verbindung.meldung)
        self.on_air.zeigen(verbindung.sendung)
        mitte.setFocus()

    # ------------------------------------------------------------------
    def _titel_eintragen(self, titel, bedienfeld: QWidget) -> None:
        self._bedienfeld_index[titel.kennung] = self.bedienfelder.addWidget(bedienfeld)
        self.titelliste.hinzufuegen(titel)

    def _titel_zeigen(self, kennung: str) -> None:
        if kennung in self._bedienfeld_index:
            self.bedienfelder.setCurrentIndex(self._bedienfeld_index[kennung])

    def _status(self, status: Status, _meldung: str) -> None:
        self.verbindungsanzeige.zeigen(status)
        if status is not Status.VERBUNDEN:
            self.vorschaubild.text_setzen(self.E.texte.vorschau_keine_verbindung)
        elif not self.vorschaubild.hat_bild():
            self.vorschaubild.text_setzen(self.E.texte.vorschau_wartet)
        self._meldungsleiste_auffrischen()

    def _meldungsleiste_auffrischen(self) -> None:
        v = self.verbindung
        startet = self._obs_start_sperre.isActive()
        # Nach „OBS starten“ bleibt der Hinweis stehen, bis OBS verbunden ist (kein Flackern).
        zeigen = not v.verbunden and (startet or (v.status is Status.GETRENNT and bool(v.meldung)))
        self.meldungsleiste.setVisible(zeigen)
        if not zeigen:
            return
        if startet:
            self.meldungstext.setText(self.E.texte.meldung_obs_startet)
            self.knopf_obs_starten.setVisible(False)
        else:
            self.meldungstext.setText(v.meldung)
            self.knopf_obs_starten.setVisible(not zugang.obs_laeuft())

    def _szene(self, name: str) -> None:
        self.szenenname.setText(name)

    def _bild(self, bild) -> None:
        if self.verbindung.verbunden:
            self.vorschaubild.bild_setzen(bild)

    # ------------------------------------------------------------------
    def obs_starten(self) -> None:
        teile = shlex.split(str(self.E.obs.startbefehl))
        if not teile:
            return
        ok = QProcess.startDetached(teile[0], teile[1:])
        if isinstance(ok, tuple):  # je nach PySide-Version (ok, prozessnummer)
            ok = ok[0]
        if ok:
            log.info("OBS gestartet")
            self._obs_start_sperre.start(15000)  # 15 s lang nicht doppelt starten
            self.verbindung.jetzt_neu_verbinden()
        else:
            log.warning("OBS ließ sich nicht starten: %s", teile)
            self.meldungstext.setText(self.E.texte.meldung_obs_start_fehler)
            return
        self._meldungsleiste_auffrischen()

    def countdown_einrichten(self) -> None:
        if self._einrichten_laeuft is not None or not self.countdown_adresse:
            return
        knopf_ = self.countdown_bereich.einrichten
        knopf_.setEnabled(False)
        self.countdown_bereich.meldung_zeigen("…")

        def fertig(erfolg: bool, meldung: str):
            self._einrichten_laeuft = None
            knopf_.setEnabled(True)
            self.countdown_bereich.meldung_zeigen(meldung, erfolg)

        self._einrichten_laeuft = CountdownEinrichten(
            self.verbindung, str(self.E.countdown.obs_quellenname), self.countdown_adresse, self.E.texte, fertig)
        self._einrichten_laeuft.los()
