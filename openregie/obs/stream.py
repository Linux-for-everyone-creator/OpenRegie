"""Stream starten und beenden – die Zwischenschicht für den Knopf „Stream starten“ (ab Build 1.2.3).

Die Oberfläche ruft nur `starten()` / `beenden()` auf und zeigt `knopf` und `meldung` an. Mit OBS spricht
allein dieses Bauteil (über die ObsVerbindung). Ändert sich etwas an OBS, betrifft es nur diese Datei.

Was OBS 33 wirklich tut (mit echtem OBS geprüft, 27.11.2026):
  - Ohne Stream-Key sagt StartStream trotzdem „ok“, meldet „startet …“ – und dann nie wieder etwas.
    Dazu zeigt das (unsichtbare) OBS ein eigenes Fehlerfenster. Darum prüfen wir VOR dem Start, ob ein
    Ziel eingetragen ist, und schicken sonst gar nichts.
  - Server nicht erreichbar: „startet …“, eine halbe Sekunde später „aus“, ohne je live zu sein (Fehlstart).
  - Läuft schon: StartStream → Fehler 500. Läuft nicht: StopStream → Fehler 501.
  - Verbindung zum Dienst weg: „verbindet neu …“ (Sendung.WIEDER), bis OBS aufgibt oder es wieder klappt.

Der Knopf zeigt immer den echten Zustand von OBS – auch wenn in OBS selbst gestartet oder gestoppt wird.
"""

from __future__ import annotations

import logging
from enum import Enum

from PySide6.QtCore import QObject, QTimer, Signal

from .verbindung import LIVE, ObsVerbindung, Sendung

log = logging.getLogger("openregie.stream")

# So lange darf „Verbinde …“ höchstens dauern, dann gilt der Start als gescheitert
START_ZEITLIMIT_MS = 30000
# So lange darf „Stoppe …“ höchstens dauern, dann fragt OpenRegie OBS noch einmal
STOPP_ZEITLIMIT_MS = 15000

# Fehlernummern von obs-websocket
CODE_LAEUFT_SCHON = 500
CODE_LAEUFT_NICHT = 501


class Knopf(Enum):
    GESPERRT = "gesperrt"  # keine Verbindung zu OBS
    STARTEN = "starten"  # „▶ Stream starten“
    VERBINDE = "verbinde"  # „Verbinde …“ (gesperrt – kein Doppelklick)
    BEENDEN = "beenden"  # „■ Stream beenden“
    STOPPE = "stoppe"  # „Stoppe …“ (gesperrt)


def ziel_fehlt(art: str, einstellungen: dict) -> str:
    """Ist in OBS ein Ziel für den Stream eingetragen? Gibt zurück, was fehlt: "key", "server" oder ""."""
    e = einstellungen or {}
    if art == "rtmp_common":  # Twitch, YouTube & Co. aus der OBS-Liste: der Key ist Pflicht
        if not str(e.get("key") or "").strip():
            return "key"
        return ""
    if art in ("rtmp_custom", "whip_custom"):  # eigener Server: der Key darf in der Adresse stecken
        if not str(e.get("server") or "").strip():
            return "server"
        return ""
    return ""  # andere Arten kennen wir nicht – OBS entscheidet


class StreamSteuerung(QObject):
    knopf_geaendert = Signal(object)  # Knopf
    meldung_geaendert = Signal(str)  # Meldung für Menschen ("" = keine)

    def __init__(self, verbindung: ObsVerbindung, texte, parent=None):
        super().__init__(parent)
        self._v = verbindung
        self._t = texte
        self._prueft = False  # Klick auf „Stream starten“, OBS hat noch nicht „startet“ gemeldet
        self._stoppt = False  # Klick auf „Stream beenden“, OBS hat noch nicht „stoppt“ gemeldet
        self._startversuch = False  # seit „startet …“ noch nicht live gewesen
        self.meldung = ""
        self.knopf = Knopf.GESPERRT

        self._start_uhr = QTimer(self)
        self._start_uhr.setSingleShot(True)
        self._start_uhr.timeout.connect(self._start_zu_langsam)
        self._stopp_uhr = QTimer(self)
        self._stopp_uhr.setSingleShot(True)
        self._stopp_uhr.timeout.connect(lambda: self._v.stream_status_pruefen(erzwingen=True))

        verbindung.sendung_geaendert.connect(self._sendung)
        verbindung.status_geaendert.connect(lambda *_: self._verbindung_geaendert())
        verbindung.stream_bekannt_geaendert.connect(lambda _: self._knopf_auffrischen())
        self._knopf_auffrischen()

    # ------------------------------------------------------------------
    #  Bedienung
    # ------------------------------------------------------------------
    def starten(self) -> None:
        """Knopf „Stream starten“: erst prüfen, ob in OBS ein Ziel eingetragen ist, dann StartStream."""
        if self.knopf is not Knopf.STARTEN:
            return  # kein Doppelklick, nicht ohne Verbindung, nicht während es schon läuft
        # Eine alte Meldung bleibt stehen, bis OBS den Start annimmt – sonst flackert dieselbe Meldung
        self._prueft = True
        self._knopf_auffrischen()
        log.info("Stream starten: prüfe Stream-Ziel in OBS")
        self._v.anfrage("GetStreamServiceSettings", rueckruf=self._ziel_geprueft)

    def beenden(self) -> None:
        """Knopf „Stream beenden“ (nach der Nachfrage in der Oberfläche)."""
        if self.knopf is not Knopf.BEENDEN:
            return
        self._meldung_setzen("")
        self._stoppt = True
        self._knopf_auffrischen()
        log.info("Stream beenden")
        self._stopp_uhr.start(STOPP_ZEITLIMIT_MS)
        self._v.anfrage("StopStream", rueckruf=self._stopp_antwort)

    def meldung_weg(self) -> None:
        """Knopf „Verstanden“ neben der Meldung."""
        self._meldung_setzen("")

    @property
    def live(self) -> bool:
        return self._v.sendung in LIVE

    # ------------------------------------------------------------------
    #  Antworten von OBS
    # ------------------------------------------------------------------
    def _ziel_geprueft(self, ok: bool, daten: dict, fehler: str) -> None:
        if not self._prueft:
            return  # inzwischen abgebrochen (z. B. Verbindung weg)
        if not self._v.verbunden:
            self._fehlschlag("")  # die Meldungsleiste sagt schon „Verbindung zu OBS weg“
            return
        if ok:
            fehlt = ziel_fehlt(daten.get("streamServiceType", ""), daten.get("streamServiceSettings") or {})
            if fehlt == "key":
                log.warning("Stream nicht gestartet: in OBS ist kein Stream-Key eingetragen")
                self._fehlschlag(self._t.stream_meldung_kein_key)
                return
            if fehlt == "server":
                log.warning("Stream nicht gestartet: in OBS ist kein Server eingetragen")
                self._fehlschlag(self._t.stream_meldung_kein_server)
                return
        else:
            # Prüfen ging nicht – trotzdem versuchen; scheitert der Start, merken wir es am Ergebnis
            log.info("Stream-Ziel nicht lesbar (%s) – starte trotzdem", fehler)
        log.info("StartStream")
        self._v.anfrage("StartStream", rueckruf=self._start_antwort)

    def _start_antwort(self, ok: bool, daten: dict, fehler: str) -> None:
        if ok:
            if self._prueft:
                self._start_uhr.start(START_ZEITLIMIT_MS)  # falls OBS gar nichts mehr meldet
            return
        if not self._prueft:
            return
        if daten.get("fehlercode") == CODE_LAEUFT_SCHON:
            # läuft schon (z. B. gleichzeitig in OBS gestartet): einfach den echten Zustand holen
            self._prueft = False
            self._v.stream_status_pruefen()
            self._knopf_auffrischen()
            return
        log.warning("StartStream abgelehnt: %s", fehler)
        self._fehlschlag("" if not self._v.verbunden else self._t.stream_meldung_start_fehler)

    def _stopp_antwort(self, ok: bool, daten: dict, fehler: str) -> None:
        if ok or not self._stoppt:
            return
        self._stoppt = False
        self._stopp_uhr.stop()
        if daten.get("fehlercode") == CODE_LAEUFT_NICHT:
            self._v.stream_status_pruefen(erzwingen=True)  # war schon aus
        elif self._v.verbunden:
            log.warning("StopStream abgelehnt: %s", fehler)
            self._meldung_setzen(self._t.stream_meldung_stopp_fehler)
        self._knopf_auffrischen()

    def _fehlschlag(self, meldung: str) -> None:
        self._prueft = False
        self._startversuch = False
        self._start_uhr.stop()
        self._meldung_setzen(meldung)
        self._knopf_auffrischen()

    # ------------------------------------------------------------------
    #  Zustand aus OBS (Ereignis StreamStateChanged / GetStreamStatus)
    # ------------------------------------------------------------------
    def _sendung(self, sendung: Sendung) -> None:
        if sendung is Sendung.STARTET:
            self._prueft = False  # ab jetzt sagt OBS, wie es steht
            self._startversuch = True
            self._meldung_setzen("")  # OBS versucht es: die alte Meldung gilt nicht mehr
            if not self._start_uhr.isActive():
                self._start_uhr.start(START_ZEITLIMIT_MS)  # auch bei einem Start in OBS selbst
        elif sendung in LIVE:
            self._prueft = False
            self._startversuch = False
            self._start_uhr.stop()
            if sendung is Sendung.AN:
                self._meldung_setzen("")  # live: alte Fehlermeldung ist erledigt
        elif sendung is Sendung.STOPPT:
            self._stoppt = False
            self._startversuch = False
            self._start_uhr.stop()
        elif sendung is Sendung.AUS:
            self._stoppt = False
            self._stopp_uhr.stop()
            self._start_uhr.stop()
            if self._startversuch and self._v.verbunden:
                log.warning("Stream ist nicht live gegangen (Fehlstart)")
                self._meldung_setzen(self._t.stream_meldung_fehlstart)
            self._startversuch = False
            self._prueft = False
        self._knopf_auffrischen()

    def _verbindung_geaendert(self) -> None:
        # Verbindung weg: das meldet schon die Meldungsleiste („Verbindung zu OBS abgebrochen …“).
        # Nach dem Neuverbinden zeigt der Knopf wieder den echten Zustand von OBS.
        if not self._v.verbunden:
            self._prueft = self._stoppt = self._startversuch = False
            self._start_uhr.stop()
            self._stopp_uhr.stop()
        self._knopf_auffrischen()

    def _start_zu_langsam(self) -> None:
        if self._v.sendung in LIVE:
            return
        log.warning("Stream: nach %s s noch nicht live – gebe auf", START_ZEITLIMIT_MS // 1000)
        self._startversuch = False
        self._prueft = False
        self._meldung_setzen(self._t.stream_meldung_zeitlimit)
        self._v.stream_status_pruefen(erzwingen=True)  # „startet …“ hängt sonst für immer
        self._knopf_auffrischen()

    # ------------------------------------------------------------------
    def _knopf_auffrischen(self) -> None:
        s = self._v.sendung
        if not self._v.verbunden or not self._v.stream_bekannt:
            knopf = Knopf.GESPERRT  # ohne OBS – oder OBS hat noch nicht gesagt, ob der Stream läuft
        elif self._stoppt or s is Sendung.STOPPT:
            knopf = Knopf.STOPPE
        elif s in LIVE:
            knopf = Knopf.BEENDEN
        elif self._prueft or s is Sendung.STARTET:
            knopf = Knopf.VERBINDE
        else:
            knopf = Knopf.STARTEN
        if knopf is not self.knopf:
            self.knopf = knopf
            self.knopf_geaendert.emit(knopf)

    def _meldung_setzen(self, text: str) -> None:
        if text != self.meldung:
            self.meldung = text
            self.meldung_geaendert.emit(text)
