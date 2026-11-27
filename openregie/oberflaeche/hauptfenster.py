"""Das Hauptfenster – Aussehen nach dem Entwurf „Hauptfenster (Build 1)“.

  ┌──────────────────────────────────────────────────────────────────────┐
  │ [■] OpenRegie   ( ● OBS verbunden )   [▶ Stream starten] ( ● ON AIR ) 18:57 │  Kopfleiste
  ├──────────────────────────────────────────────────────────────────────┤
  │ (Hinweis, wenn mit OBS etwas nicht stimmt)  [OBS starten] [Neu]       │  Meldungsleiste
  ├──────────────┬──────────────────────────────┬────────────────────────┤
  │ Bibliothek ↻+│  Live-Bild (roter Rahmen,    │ AUSGEWÄHLT             │
  │ ┌────┐┌────┐ │  wenn live)                  │ Countdown | Circles    │
  │ │Kach││Kach│ │                              │ Countdown / Texte      │
  │ └────┘└────┘ ├──────────────────────────────┤                        │
  │ LAMPEN ● ● ● │  Twitch-Streamtitel          │ [▶ Einblenden][■ Aus…] │
  │              ├──────────────────────────────┤                        │
  │              │ [✎][▾] [Shot][Shot][Shot][+] │                        │  Shots (wie Wirecast)
  └──────────────┴──────────────────────────────┴────────────────────────┘
   OpenRegie · Vorabversion · Build 1.1   ← Wasserzeichen unten links
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QTime, Qt, QTimer
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import (QGraphicsOpacityEffect, QHBoxLayout, QLabel, QMainWindow,
                               QSizePolicy, QStackedWidget, QVBoxLayout, QWidget)

from .. import einstellungen
from ..obs.motor import MotorZustand, ObsMotor
from ..automatik.motor import Automatik
from ..obs.quellen import ObsQuellen
from ..obs.stream import StreamSteuerung
from ..obs.verbindung import ObsVerbindung, Sendung, Status
from ..obs.vorschau import Vorschau
from ..twitch.konto import TwitchKonto
from ..uno.verwaltung import UnoVerwaltung
from .bausteine import Logo, OnAirLicht, VerbindungsAnzeige, VorschauBild, beschriftung, flaeche, knopf
from .overlay_bereich import Bibliothek, OverlayBedienfeld, UnoEinrichtung
from .shot_bereich import ShotBedienfeld, ShotLeiste, ShotNeu, ShotNeuFenster
from .stil import stylesheet
from .stream_knopf import StreamKnopf, frage_ja_nein
from .twitch_bereich import TwitchBereich
from .wenn_dann import WennDannFenster, WennDannKnopf, naechster_text

log = logging.getLogger("openregie.fenster")

STREAM_STOPP_WARTEN_MS = 15000


class Hauptfenster(QMainWindow):
    def __init__(self, E, verbindung: ObsVerbindung, vorschau: Vorschau, motor: ObsMotor,
                 uno: UnoVerwaltung, twitch: TwitchKonto, quellen: ObsQuellen | None = None,
                 automatik: Automatik | None = None, stream: StreamSteuerung | None = None):
        super().__init__()
        # Shots/Quellen und Automatik: Motor-Schicht – das Fenster spricht nie direkt mit OBS
        self.quellen = quellen or ObsQuellen(verbindung, E.texte, E.quellen, self)
        self.automatik = automatik or Automatik(E.texte, verbindung, self.quellen, uno, self)
        self.stream = stream or StreamSteuerung(verbindung, E.texte, self)  # Stream starten/beenden
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
        kl.setContentsMargins(g.abstand * 2, 8, g.abstand * 2, 8)
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
        # Wenn-dann (Automatik) und der nächste Termin aus dem Zeitplan
        self.naechster_stream = beschriftung("", "gedimmt")
        kl.addWidget(self.naechster_stream)
        self.knopf_wenn_dann = knopf(t.knopf_wenn_dann)
        self.knopf_wenn_dann.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.knopf_wenn_dann.setMinimumWidth(260)
        self.knopf_wenn_dann.clicked.connect(self.wenn_dann_oeffnen)
        kl.addWidget(self.knopf_wenn_dann)
        kl.addSpacing(g.abstand)
        # „▶ Stream starten“ direkt neben ON AIR: Knopf und Licht gehören zusammen
        self.stream_knopf = StreamKnopf(E, self.stream, self)
        self.knopf_stream = self.stream_knopf.knopf
        kl.addWidget(self.knopf_stream)
        self.on_air = OnAirLicht(E)
        kl.addWidget(self.on_air)
        kl.addSpacing(g.abstand)
        self.uhr = beschriftung("", "uhr")
        uhr_schrift = QFont(str(g.schriftart))
        uhr_schrift.setPixelSize(int(g.schrift_uhr))
        uhr_schrift.setBold(True)
        # feste Breite: schmale Ziffern (11:11:11) sollen die Kopfleiste nicht verschieben
        self.uhr.setFixedWidth(QFontMetrics(uhr_schrift).horizontalAdvance("00:00:00") + 2)
        self.uhr.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
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
        self.knopf_neu.clicked.connect(self.motor.neu_verbinden)
        ml.addWidget(self.knopf_neu)
        # Meldung vom Stream-Knopf (z. B. „Stream-Key fehlt“) wegklicken
        self.knopf_verstanden = knopf(t.knopf_meldung_verstanden)
        self.knopf_verstanden.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.knopf_verstanden.clicked.connect(self.stream.meldung_weg)
        ml.addWidget(self.knopf_verstanden)

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
        tl.setContentsMargins(rand, g.abstand - 2, rand, g.abstand - 2)  # flacher: Platz für die Shots
        self.twitch_bereich = TwitchBereich(E, twitch)
        tl.addWidget(self.twitch_bereich)
        spalte.addWidget(twitch_flaeche)

        # Shots unten wie bei Wirecast: ein Klick schaltet live
        shot_flaeche = flaeche()
        sl = QVBoxLayout(shot_flaeche)
        sl.setContentsMargins(g.abstand // 2 + 2, 5, g.abstand // 2 + 2, 5)
        self.shot_leiste = ShotLeiste(E, self.quellen)
        sl.addWidget(self.shot_leiste)
        spalte.addWidget(shot_flaeche)
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
        self.shot_bedienfeld = ShotBedienfeld(E, self.quellen)
        self.bedienfelder.addWidget(self.shot_bedienfeld)
        # „Shot hinzufügen“ / „Quelle hinzufügen“: eigenes Fenster (ab Build 1.2.2) – rechts bleibt der Countdown
        self.shot_neu = ShotNeu(E, self.quellen)
        self.shot_neu_fenster = ShotNeuFenster(E, self.shot_neu, self)
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
        self.shot_leiste.bearbeiten_geklickt.connect(self._shot_bearbeiten)
        self.shot_leiste.hinzufuegen_geklickt.connect(self._shot_neu)
        self.shot_leiste.bearbeiten_beendet.connect(self._shots_fertig)
        self.shot_bedienfeld.fertig.connect(lambda: self.shot_leiste.bearbeiten_setzen(False))
        self.shot_bedienfeld.quelle_hinzufuegen.connect(self._quelle_neu)
        self.shot_neu.fertig.connect(self._shot_neu_fertig)
        uno.liste_geaendert.connect(self._liste_geaendert)
        uno.meldung.connect(lambda text, fehler: self.bibliothek.meldung.zeigen(text, False if fehler else None))

        verbindung.status_geaendert.connect(self._status)
        verbindung.sendung_geaendert.connect(self._sendung)
        verbindung.szene_geaendert.connect(self._szene)
        self.stream.meldung_geaendert.connect(lambda _text: self._meldungsleiste_auffrischen())
        vorschau.neues_bild.connect(self._bild)
        motor.zustand_geaendert.connect(lambda *_: self._meldungsleiste_auffrischen())
        motor.sammlung_meldung.connect(self._sammlung)

        self.wenn_dann = WennDannFenster(E, self.automatik, self)  # bleibt zu, bis man es öffnet (kostet nichts)
        self.automatik.geaendert.connect(self._automatik_zeigen)
        self._automatik_zeigen()

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
        jetzt = QTime.currentTime()
        self.uhr.setText(jetzt.toString("HH:mm:ss"))
        if jetzt.minute() != getattr(self, "_minute", None):  # „Nächster Stream“ einmal pro Minute
            self._minute = jetzt.minute()
            if hasattr(self, "automatik"):
                self._naechster_zeigen()

    # --- Wenn-dann ----------------------------------------------------------
    def wenn_dann_oeffnen(self) -> None:
        self.wenn_dann.show()
        self.wenn_dann.raise_()
        self.wenn_dann.activateWindow()

    def _automatik_zeigen(self) -> None:
        self.knopf_wenn_dann.setText(WennDannKnopf.text(self.E, self.automatik))
        self._naechster_zeigen()

    def _naechster_zeigen(self) -> None:
        text = naechster_text(self.E, self.automatik)
        self.naechster_stream.setText(text)
        self.naechster_stream.setVisible(bool(text))  # leer: kein Platz in der Kopfleiste verschenken

    def resizeEvent(self, e):
        super().resizeEvent(e)
        g = self.E.groessen
        self.build.adjustSize()
        mitte = self.centralWidget()
        self.build.move(g.abstand + 4, mitte.height() - self.build.height() - 6)
        self.build.raise_()

    def changeEvent(self, e):
        super().changeEvent(e)
        # Minimiert: keine Vorschaubilder für die Kacheln holen
        if e.type() == e.Type.WindowStateChange:
            self.shot_leiste.aktiv_pruefen()
            self.shot_bedienfeld.aktiv_pruefen()

    # --- Shots ----------------------------------------------------------------
    def _shot_bearbeiten(self, name: str) -> None:
        self.bibliothek.auswahl_aufheben()
        self.shot_bedienfeld.zeigen(name)
        self.bedienfelder.setCurrentWidget(self.shot_bedienfeld)

    def _shot_neu(self) -> None:
        """„+“ in der Shot-Leiste: eigenes Fenster. Rechts bleibt, was war (z. B. der Countdown)."""
        self.shot_neu.shot_zeigen()
        self.shot_neu_fenster.oeffnen()

    def _quelle_neu(self, shot: str) -> None:
        self.shot_neu.quelle_zeigen(shot)
        self.shot_neu_fenster.oeffnen()

    def _shot_neu_fertig(self, name: str) -> None:
        self.shot_neu_fenster.schliessen()
        if name and self.shot_neu.modus == "quelle":
            self._shot_bearbeiten(name)
        elif name:
            # Neuen Shot gleich zum Bearbeiten zeigen (geht nicht live)
            self.shot_leiste.bearbeiten_setzen(True)
            self.shot_leiste.gewaehlt_setzen(name)
            self._shot_bearbeiten(name)
        # abgebrochen: nichts zu tun – rechts hat sich nichts geändert

    def _shots_fertig(self) -> None:
        """Bearbeiten beendet: rechts wieder das Overlay."""
        if self.bedienfelder.currentWidget() is self.shot_bedienfeld:
            self._zurueck_zur_auswahl()

    # --- Overlays ---------------------------------------------------------
    def _overlay_zeigen(self, schluessel: str) -> None:
        overlay = self.uno.overlays.get(schluessel)
        if overlay is None:
            self._zurueck_zur_auswahl()
            return
        self.overlay_bedienfeld.zeigen(overlay)
        self.bedienfelder.setCurrentWidget(self.overlay_bedienfeld)
        self.shot_leiste.bearbeiten_setzen(False)  # erst jetzt: rechts steht schon das Overlay

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
        text, obs_knopf, neu_knopf, verstanden = "", False, False, False
        if v.verbunden and self.stream.meldung:
            text, verstanden = self.stream.meldung, True  # z. B. „Stream-Key fehlt“
        elif v.verbunden:
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
        self.knopf_verstanden.setVisible(verstanden)

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
        t = self.E.texte
        return frage_ja_nein(self.E, self, t.frage_beenden_live_titel, t.frage_beenden_live,
                             t.knopf_beenden_ja, t.knopf_beenden_nein)

    def closeEvent(self, e):
        if self._schliessen_erlaubt:
            self.shot_neu_fenster.reject()  # offenes „Shot hinzufügen“ geht mit zu
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
            self.motor.stream_beenden()
            self._stopp_uhr.start(STREAM_STOPP_WARTEN_MS)
            e.ignore()
            return
        self.shot_neu_fenster.reject()  # offenes „Shot hinzufügen“ geht mit zu
        e.accept()

    def _endgueltig_schliessen(self) -> None:
        self._stopp_uhr.stop()
        self._schliessen_erlaubt = True
        self.close()
