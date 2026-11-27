"""Verbindung zu OBS über den OBS-WebSocket (Protokoll Version 5).

OpenRegie ist hier der „Fernbediener“, OBS der Motor. Die Klasse
  - verbindet sich und meldet sich mit Passwort an,
  - versucht es bei Abbruch automatisch immer wieder,
  - schickt Anfragen und ruft bei der Antwort eine Funktion auf,
  - meldet, ob OBS live ist (On-Air) und welche Szene gesendet wird.

Alle Meldungen für Menschen kommen aus einstellungen.toml ([texte]).
"""

from __future__ import annotations

import base64
import hashlib
import itertools
import json
import logging
import time
from enum import Enum
from typing import Callable

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtNetwork import QAbstractSocket
from PySide6.QtWebSockets import QWebSocket

from . import zugang as zugang_modul

log = logging.getLogger("openregie.obs")

# Protokoll-Nummern (OpCodes) aus der OBS-WebSocket-Beschreibung
OP_HELLO, OP_IDENTIFY, OP_IDENTIFIED = 0, 1, 2
OP_EVENT, OP_REQUEST, OP_REQUEST_RESPONSE = 5, 6, 7

# Welche Nachrichten wir von OBS hören wollen
EREIGNISSE_ALLGEMEIN = 1 << 0
EREIGNISSE_KONFIGURATION = 1 << 1  # z. B. Szenensammlung gewechselt
EREIGNISSE_SZENEN = 1 << 2
EREIGNISSE_EINGAENGE = 1 << 3  # Quelle angelegt, entfernt, umbenannt (keine Pegel – die wären 1 << 16)
EREIGNISSE_AUSGABEN = 1 << 6
EREIGNISSE_SZENENELEMENTE = 1 << 7  # Quelle in Szene hinzugefügt, Reihenfolge geändert
EREIGNIS_MASKE = (EREIGNISSE_ALLGEMEIN | EREIGNISSE_KONFIGURATION | EREIGNISSE_SZENEN | EREIGNISSE_EINGAENGE
                  | EREIGNISSE_AUSGABEN
                  | EREIGNISSE_SZENENELEMENTE)

# Schließ-Codes von OBS
CODE_PASSWORT_FALSCH = 4009
CODE_VERSION_ZU_ALT = 4010

ANMELDE_ZEITLIMIT_MS = 5000
ANFRAGE_ZEITLIMIT_MS = 10000
STREAM_ABFRAGE_MS = 5000
# So lange nach einem Stream-Ereignis von OBS gilt das Ereignis mehr als eine Abfrage. Grund (echtes OBS 33
# gemessen): Direkt nach „gestoppt“ meldet GetStreamStatus noch ~130 ms „läuft“ – sonst leuchtete ON AIR
# kurz wieder rot, und „Stream startet“-Regeln lösten fälschlich aus.
EREIGNIS_VORRANG_S = 3.0
ZEITLIMIT_TEXT = "OBS hat nicht geantwortet."


class Status(Enum):
    GETRENNT = "getrennt"
    VERBINDE = "verbinde"
    VERBUNDEN = "verbunden"


class Sendung(Enum):
    AUS = "aus"
    STARTET = "startet"
    AN = "an"
    WIEDER = "wieder"  # live gewesen, Verbindung zum Streaming-Dienst weg – OBS verbindet neu
    STOPPT = "stoppt"


# In diesen Zuständen läuft ein Stream (auch wenn er gerade neu verbindet)
LIVE = (Sendung.AN, Sendung.WIEDER)


def anmeldeschluessel(passwort: str, salz: str, aufgabe: str) -> str:
    """Passwort-Antwort nach OBS-Vorgabe: base64(sha256(base64(sha256(pw+salz)) + aufgabe))."""
    geheim = base64.b64encode(hashlib.sha256((passwort + salz).encode("utf-8")).digest()).decode()
    return base64.b64encode(hashlib.sha256((geheim + aufgabe).encode("utf-8")).digest()).decode()


# Rückruf für Anfragen: (erfolgreich, antwortdaten, fehlertext)
Rueckruf = Callable[[bool, dict, str], None]


class ObsVerbindung(QObject):
    status_geaendert = Signal(object, str)  # (Status, Meldung für Menschen)
    sendung_geaendert = Signal(object)  # Sendung
    szene_geaendert = Signal(str)  # Name der gesendeten Szene
    ereignis = Signal(str, dict)  # alle OBS-Ereignisse, für spätere Builds
    # Echte Übergänge für Wenn-dann: „ist live gegangen“ / „ist wirklich zu Ende“ – nicht bei
    # „verbindet neu → wieder da“, nicht bei einem Fehlstart und nicht, nur weil OBS kurz weg war.
    live_begonnen = Signal()
    live_beendet = Signal()
    # Nach dem (Neu-)Verbinden: OBS hat gesagt, ob der Stream läuft (vorher weiß es niemand)
    stream_bekannt_geaendert = Signal(bool)

    def __init__(self, obs_einstellungen, texte, parent=None, zugang_finden=None, obs_laeuft=None):
        super().__init__(parent)
        self._obs = obs_einstellungen
        self._texte = texte
        self._zugang_finden = zugang_finden or (lambda: zugang_modul.ermitteln(self._obs))
        self._obs_laeuft = obs_laeuft or zugang_modul.obs_laeuft

        self.status = Status.GETRENNT
        self.meldung = ""
        self.sendung = Sendung.AUS
        self._war_live = False
        self._letztes_stream_ereignis = -1e9  # time.monotonic() des letzten StreamStateChanged
        self.stream_bekannt = False
        self.szene = ""
        self.szene_kennung = ""  # eindeutige OBS-Kennung (UUID) der gesendeten Szene – bleibt beim Umbenennen gleich

        self._socket: QWebSocket | None = None
        self._passwort = ""
        self._still = False  # läuft gerade ein stiller Neuversuch?
        self._offene_anfragen: dict[str, tuple[Rueckruf | None, QTimer]] = {}
        self._zaehler = itertools.count(1)
        self._aktiv = False  # soll überhaupt verbunden sein?

        self._neu_timer = QTimer(self)
        self._neu_timer.setSingleShot(True)
        self._neu_timer.timeout.connect(lambda: self._verbindung_aufbauen(still=True))

        self._anmelde_timer = QTimer(self)
        self._anmelde_timer.setSingleShot(True)
        self._anmelde_timer.timeout.connect(self._anmeldung_zu_langsam)

        self._stream_timer = QTimer(self)
        self._stream_timer.setInterval(STREAM_ABFRAGE_MS)
        self._stream_timer.timeout.connect(self._stream_status_abfragen)

    # ------------------------------------------------------------------
    #  Öffentliche Bedienung
    # ------------------------------------------------------------------
    @property
    def verbunden(self) -> bool:
        return self.status is Status.VERBUNDEN

    def starten(self) -> None:
        """Verbinden und ab jetzt immer wieder versuchen."""
        self._aktiv = True
        self._neu_timer.stop()
        self._verbindung_aufbauen()

    def jetzt_neu_verbinden(self) -> None:
        """Knopf „Neu verbinden“: alte Verbindung weg, sofort neu."""
        self._aktiv = True
        self._alte_verbindung_weg()
        self._neu_timer.stop()
        self._verbindung_aufbauen()

    def beenden(self) -> None:
        self._aktiv = False
        self._neu_timer.stop()
        self._alte_verbindung_weg()
        self._status_setzen(Status.GETRENNT, "")

    def anfrage(self, typ: str, daten: dict | None = None, rueckruf: Rueckruf | None = None) -> None:
        """Schickt eine Anfrage an OBS. Der Rückruf kommt immer – auch bei Fehlern."""
        if not self.verbunden or self._socket is None:
            if rueckruf:
                QTimer.singleShot(0, lambda: rueckruf(False, {}, self._texte.meldung_nicht_verbunden))
            return
        kennung = f"r{next(self._zaehler)}"
        zeitlimit = QTimer(self)
        zeitlimit.setSingleShot(True)
        zeitlimit.timeout.connect(lambda: self._anfrage_beenden(kennung, False, {}, ZEITLIMIT_TEXT))
        zeitlimit.start(ANFRAGE_ZEITLIMIT_MS)
        self._offene_anfragen[kennung] = (rueckruf, zeitlimit)
        nachricht = {"op": OP_REQUEST, "d": {"requestType": typ, "requestId": kennung}}
        if daten:
            nachricht["d"]["requestData"] = daten
        self._socket.sendTextMessage(json.dumps(nachricht))

    # ------------------------------------------------------------------
    #  Verbindungsaufbau
    # ------------------------------------------------------------------
    def _verbindung_aufbauen(self, still: bool = False) -> None:
        """still=True: automatischer Neuversuch. Dann bleibt die letzte Erklärung
        (z. B. „OBS ist nicht geöffnet“) stehen, statt alle paar Sekunden zu flackern."""
        if not self._aktiv:
            return
        self._alte_verbindung_weg()
        zugang = self._zugang_finden()  # jedes Mal neu lesen: Passwort könnte geändert sein
        self._passwort = zugang.passwort
        self._still = still and self.status is Status.GETRENNT and bool(self.meldung)
        if not self._still:
            self._status_setzen(Status.VERBINDE, self._texte.status_verbinde)

        socket = QWebSocket()
        socket.setParent(self)
        socket.connected.connect(lambda s=socket: self._verbunden(s))
        socket.disconnected.connect(lambda s=socket: self._getrennt(s))
        socket.errorOccurred.connect(lambda _fehler, s=socket: self._getrennt(s))
        socket.textMessageReceived.connect(lambda text, s=socket: self._nachricht(s, text))
        self._socket = socket
        adresse = f"ws://{self._obs.adresse}:{zugang.port}"
        # Stille Neuversuche nur ins ausführliche Protokoll, sonst wird die Datei voll
        log.log(logging.DEBUG if self._still else logging.INFO, "Verbinde mit %s", adresse)
        self._anmelde_timer.start(ANMELDE_ZEITLIMIT_MS)
        socket.open(QUrl(adresse))

    def _alte_verbindung_weg(self) -> None:
        self._anmelde_timer.stop()
        self._stream_timer.stop()
        socket, self._socket = self._socket, None
        if socket is not None:
            for signal in (socket.connected, socket.disconnected, socket.errorOccurred, socket.textMessageReceived):
                try:
                    signal.disconnect()
                except (RuntimeError, TypeError):
                    pass
            socket.abort()
            socket.deleteLater()
        self._alle_anfragen_abbrechen()

    def _verbunden(self, socket: QWebSocket) -> None:
        if socket is not self._socket:
            return
        log.info("Netzverbindung steht, warte auf Begrüßung von OBS")

    def _anmeldung_zu_langsam(self) -> None:
        log.warning("Anmeldung bei OBS dauerte zu lange")
        if self._socket is not None:
            self._getrennt(self._socket, zeitueberschreitung=True)

    def _getrennt(self, socket: QWebSocket, zeitueberschreitung: bool = False) -> None:
        if socket is not self._socket:
            return  # alte Verbindung, schon erledigt
        code = socket.closeCode()
        fehler = socket.error()
        war_verbunden = self.status is Status.VERBUNDEN
        code_zahl = int(code.value if hasattr(code, "value") else code)
        log.log(logging.DEBUG if self._still else logging.INFO, "Getrennt (Code %s, Fehler %s)", code_zahl, fehler)
        self._alte_verbindung_weg()

        if code_zahl == CODE_PASSWORT_FALSCH:
            meldung = self._texte.meldung_passwort_falsch
        elif code_zahl == CODE_VERSION_ZU_ALT:
            meldung = self._texte.meldung_obs_zu_alt
        elif war_verbunden:
            meldung = self._texte.meldung_verbindung_weg
        elif not self._obs_laeuft():
            meldung = self._texte.meldung_obs_nicht_offen
        else:
            meldung = self._texte.meldung_websocket_aus

        # Erst „getrennt“, dann „aus“: so hält niemand das „aus“ für einen gescheiterten Stream-Start
        self._status_setzen(Status.GETRENNT, meldung)
        self._sendung_setzen(Sendung.AUS, getrennt=True)
        if self._aktiv:
            self._neu_timer.start(int(float(self._obs.neu_verbinden_sekunden) * 1000))

    # ------------------------------------------------------------------
    #  Nachrichten von OBS
    # ------------------------------------------------------------------
    def _nachricht(self, socket: QWebSocket, text: str) -> None:
        if socket is not self._socket:
            return
        try:
            nachricht = json.loads(text)
            op, d = nachricht["op"], nachricht.get("d") or {}
        except (ValueError, KeyError, TypeError):
            log.warning("Unverständliche Nachricht von OBS: %.200s", text)
            return

        if op == OP_HELLO:
            self._begruessung(d)
        elif op == OP_IDENTIFIED:
            self._angemeldet()
        elif op == OP_EVENT:
            self._ereignis(d)
        elif op == OP_REQUEST_RESPONSE:
            status = d.get("requestStatus") or {}
            ok = bool(status.get("result"))
            fehlertext = "" if ok else (status.get("comment") or f"Fehler {status.get('code')}")
            daten = d.get("responseData") or {}
            if not ok:
                daten = dict(daten, fehlercode=status.get("code"))  # z. B. 500 = läuft schon
            self._anfrage_beenden(d.get("requestId", ""), ok, daten, fehlertext)

    def _begruessung(self, d: dict) -> None:
        identify = {"rpcVersion": 1, "eventSubscriptions": EREIGNIS_MASKE}
        auth = d.get("authentication")
        if auth:
            identify["authentication"] = anmeldeschluessel(self._passwort, auth.get("salt", ""), auth.get("challenge", ""))
        self._socket.sendTextMessage(json.dumps({"op": OP_IDENTIFY, "d": identify}))

    def _angemeldet(self) -> None:
        self._anmelde_timer.stop()
        log.info("Bei OBS angemeldet")
        self._status_setzen(Status.VERBUNDEN, self._texte.status_verbunden)
        self._stream_status_abfragen()
        self._stream_timer.start()
        self.anfrage("GetCurrentProgramScene", rueckruf=self._szene_antwort)

    def _ereignis(self, d: dict) -> None:
        typ = d.get("eventType", "")
        daten = d.get("eventData") or {}
        if typ == "StreamStateChanged":
            self._sendung_aus_obs(daten.get("outputActive"), daten.get("outputState"))
        elif typ == "CurrentProgramSceneChanged":
            self._szene_setzen(daten.get("sceneName", ""), daten.get("sceneUuid", ""))
        elif typ == "SceneNameChanged":
            # Die gesendete Szene wurde umbenannt: sofort den neuen Namen übernehmen (nicht erst nach Fehlern)
            gleiche = (daten.get("sceneUuid") and daten.get("sceneUuid") == self.szene_kennung) \
                or (daten.get("oldSceneName") and daten.get("oldSceneName") == self.szene)
            if gleiche:
                self._szene_setzen(daten.get("sceneName", ""), daten.get("sceneUuid") or self.szene_kennung)
        elif typ == "ExitStarted":
            log.info("OBS wird beendet")
        self.ereignis.emit(typ, daten)

    # ------------------------------------------------------------------
    #  Anfragen verwalten
    # ------------------------------------------------------------------
    def _anfrage_beenden(self, kennung: str, ok: bool, daten: dict, fehlertext: str) -> None:
        eintrag = self._offene_anfragen.pop(kennung, None)
        if eintrag is None:
            return
        rueckruf, zeitlimit = eintrag
        zeitlimit.stop()
        zeitlimit.deleteLater()
        if not ok:
            log.info("Anfrage %s fehlgeschlagen: %s", kennung, fehlertext)
        if rueckruf:
            try:
                rueckruf(ok, daten, fehlertext)
            except Exception:
                log.exception("Fehler beim Verarbeiten einer OBS-Antwort")

    def _alle_anfragen_abbrechen(self) -> None:
        for kennung in list(self._offene_anfragen):
            self._anfrage_beenden(kennung, False, {}, self._texte.meldung_nicht_verbunden)

    # ------------------------------------------------------------------
    #  Stream (On Air) und Szene
    # ------------------------------------------------------------------
    def _stream_status_abfragen(self) -> None:
        self.stream_status_pruefen()

    def stream_status_pruefen(self, erzwingen: bool = False) -> None:
        """Fragt OBS, ob der Stream läuft. GetStreamStatus kennt nur an/aus (und „verbindet neu“);
        „startet/stoppt“ kommen als Ereignis und werden darum sonst nicht überschrieben.
        erzwingen=True: auch ein hängendes „startet …“ auf „aus“ setzen (OBS meldet sich nicht mehr)."""
        def antwort(ok, daten, _fehler):
            if ok:
                aktiv = bool(daten.get("outputActive"))
                frisch = time.monotonic() - self._letztes_stream_ereignis < EREIGNIS_VORRANG_S
                if frisch and not erzwingen and self.stream_bekannt:
                    pass  # OBS hat eben selbst gemeldet, was los ist – das gilt (siehe EREIGNIS_VORRANG_S)
                elif aktiv and self.sendung is not Sendung.STOPPT:
                    self._sendung_setzen(Sendung.WIEDER if daten.get("outputReconnecting") else Sendung.AN)
                elif not aktiv and (erzwingen or self.sendung is not Sendung.STARTET):
                    self._sendung_setzen(Sendung.AUS)
                if not self.stream_bekannt:  # erst NACH dem Setzen melden – sonst kurz der falsche Zustand
                    self.stream_bekannt = True
                    self.stream_bekannt_geaendert.emit(True)

        self.anfrage("GetStreamStatus", rueckruf=antwort)

    def _sendung_aus_obs(self, aktiv, zustand) -> None:
        self._letztes_stream_ereignis = time.monotonic()
        zuordnung = {
            "OBS_WEBSOCKET_OUTPUT_STARTING": Sendung.STARTET,
            "OBS_WEBSOCKET_OUTPUT_STARTED": Sendung.AN,
            "OBS_WEBSOCKET_OUTPUT_RECONNECTING": Sendung.WIEDER,
            "OBS_WEBSOCKET_OUTPUT_RECONNECTED": Sendung.AN,
            "OBS_WEBSOCKET_OUTPUT_STOPPING": Sendung.STOPPT,
            "OBS_WEBSOCKET_OUTPUT_STOPPED": Sendung.AUS,
        }
        self._sendung_setzen(zuordnung.get(zustand, Sendung.AN if aktiv else Sendung.AUS))

    def _szene_antwort(self, ok, daten, _fehler) -> None:
        if ok:
            self._szene_setzen(daten.get("sceneName") or daten.get("currentProgramSceneName") or "",
                               daten.get("sceneUuid") or daten.get("currentProgramSceneUuid") or "")

    def szene_neu_abfragen(self) -> None:
        self.anfrage("GetCurrentProgramScene", rueckruf=self._szene_antwort)

    # ------------------------------------------------------------------
    def _status_setzen(self, status: Status, meldung: str) -> None:
        if status is self.status and meldung == self.meldung:
            return
        self.status, self.meldung = status, meldung
        if status is not Status.VERBUNDEN:
            self._szene_setzen("")
            if self.stream_bekannt:
                self.stream_bekannt = False
                self.stream_bekannt_geaendert.emit(False)
        self.status_geaendert.emit(status, meldung)

    def _sendung_setzen(self, sendung: Sendung, getrennt: bool = False) -> None:
        """getrennt=True: „aus“ nur, weil die Verbindung zu OBS weg ist – der Stream kann weiterlaufen.
        Dann zählt das (noch) nicht als „Stream zu Ende“."""
        if sendung is not self.sendung:
            self.sendung = sendung
            log.info("Sendung: %s", sendung.value)
            self.sendung_geaendert.emit(sendung)
        if sendung in LIVE and not self._war_live:
            self._war_live = True
            self.live_begonnen.emit()
        elif sendung is Sendung.AUS and self._war_live and not getrennt:
            self._war_live = False
            self.live_beendet.emit()

    def _szene_setzen(self, name: str, kennung: str = "") -> None:
        self.szene_kennung = kennung if name else ""
        if name != self.szene:
            self.szene = name
            self.szene_geaendert.emit(name)
