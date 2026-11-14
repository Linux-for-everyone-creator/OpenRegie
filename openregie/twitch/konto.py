"""Twitch: Anmeldung und Streamtitel ändern.

Anmeldung mit dem „Device Code Flow“ von Twitch – das ist der Weg für Programme
ohne geheimen Schlüssel (OpenRegie ist Open Source, ein Geheimnis im Code wäre
für alle sichtbar). Ablauf:
  1. OpenRegie fragt Twitch nach einem kurzen Code (z. B. „ABCD-EFGH“).
  2. OpenRegie öffnet die Twitch-Seite im Browser, der Code ist dort schon
     eingetragen. Kevin klickt auf „Autorisieren“.
  3. OpenRegie fragt alle paar Sekunden nach, bis Twitch „fertig“ meldet.
Die Anmeldung (Zugangs- und Erneuerungsschlüssel) liegt im Passwortspeicher
des Systems. Bei Programmen ohne Geheimnis gilt sie bei Twitch höchstens
30 Tage – danach einfach neu anmelden.

Benötigt wird nur die öffentliche „Client-ID“ (einstellungen.toml, [twitch]).
Recht: channel:manage:broadcast (Titel ändern).
"""

from __future__ import annotations

import logging
import time
from enum import Enum

from PySide6.QtCore import QObject, QTimer, Signal

from ..geheimspeicher import Geheimspeicher, SpeicherFehler
from ..netz import Netz

log = logging.getLogger("openregie.twitch")

SPEICHER_SCHLUESSEL = "twitch"
RECHTE = "channel:manage:broadcast"
GERAETE_ART = "urn:ietf:params:oauth:grant-type:device_code"
TITEL_HOECHSTLAENGE = 140


class Anmeldung(Enum):
    NICHT_EINGERICHTET = "nicht_eingerichtet"  # keine Client-ID
    ABGEMELDET = "abgemeldet"
    WARTET = "wartet"  # Code wird angezeigt, warten auf Bestätigung im Browser
    ANGEMELDET = "angemeldet"


class TwitchKonto(QObject):
    anmeldung_geaendert = Signal(object)  # Anmeldung
    code_bereit = Signal(str, str)  # (Code zum Anzeigen, Adresse zum Öffnen)
    titel_geladen = Signal(str)
    meldung = Signal(str, bool)  # (Text, ist_fehler)

    def __init__(self, einstellungen_twitch, texte, speicher: Geheimspeicher, parent=None, netz: Netz | None = None,
                 uhr=time.time):
        super().__init__(parent)
        self._E = einstellungen_twitch
        self._texte = texte
        self._speicher = speicher
        self._netz = netz or Netz(self)
        self._uhr = uhr
        self.client_id = str(self._E.client_id).strip()
        self.zustand = Anmeldung.NICHT_EINGERICHTET if not self.client_id else Anmeldung.ABGEMELDET
        self.name = ""  # Twitch-Anzeigename
        self.titel = ""
        self._daten: dict = {}  # access_token, refresh_token, user_id, login
        self._geraet: dict = {}
        self._erneuert_gerade = False

        self._nachfragen = QTimer(self)
        self._nachfragen.setSingleShot(True)
        self._nachfragen.timeout.connect(self._token_abholen)

    @property
    def _id_adresse(self) -> str:
        return str(self._E.anmelde_adresse).rstrip("/")

    @property
    def _api_adresse(self) -> str:
        return str(self._E.api_adresse).rstrip("/")

    # ------------------------------------------------------------------
    #  Start: gespeicherte Anmeldung prüfen
    # ------------------------------------------------------------------
    def laden(self) -> None:
        if self.zustand is Anmeldung.NICHT_EINGERICHTET:
            self.anmeldung_geaendert.emit(self.zustand)
            return
        try:
            daten = self._speicher.json_lesen(SPEICHER_SCHLUESSEL, {}) or {}
        except SpeicherFehler as fehler:
            log.error("Passwortspeicher nicht erreichbar: %s", fehler)
            self.meldung.emit(self._texte.meldung_speicher_fehler, True)
            daten = {}
        if not daten.get("access_token"):
            self._zustand_setzen(Anmeldung.ABGEMELDET)
            return
        self._daten = daten
        self._pruefen()

    def _pruefen(self) -> None:
        """Gilt die gespeicherte Anmeldung noch? Wenn nicht: erneuern."""
        def antwort(code, daten, _fehler):
            if code == 200 and isinstance(daten, dict) and daten.get("user_id"):
                self._daten.update(user_id=str(daten["user_id"]), login=str(daten.get("login", "")))
                self.name = self._daten.get("name") or self._daten["login"]
                self._zustand_setzen(Anmeldung.ANGEMELDET)
                self.titel_laden()
            elif code == 401:
                self._erneuern(danach=self._pruefen)
            elif code == 0:
                # Kein Internet: angemeldet bleiben, später klappt es wieder
                self.name = self._daten.get("name") or self._daten.get("login", "")
                self._zustand_setzen(Anmeldung.ANGEMELDET)
                self.meldung.emit(self._texte.meldung_twitch_kein_internet, True)
            else:
                self._abmelden_wegen_fehler()

        self._netz.anfrage("GET", f"{self._id_adresse}/oauth2/validate", antwort,
                           kopfzeilen={"Authorization": f"OAuth {self._daten.get('access_token', '')}"})

    # ------------------------------------------------------------------
    #  Anmelden (Device Code Flow)
    # ------------------------------------------------------------------
    def anmelden(self) -> None:
        if not self.client_id or self.zustand is Anmeldung.WARTET:
            return

        def antwort(code, daten, _fehler):
            if code != 200 or not isinstance(daten, dict) or not daten.get("device_code"):
                log.warning("Twitch-Code anfordern fehlgeschlagen: HTTP %s %.200s", code, daten)
                self._zustand_setzen(Anmeldung.ABGEMELDET)
                self.meldung.emit(self._texte.meldung_twitch_kein_internet if code == 0
                                  else self._texte.meldung_twitch_client_id_falsch, True)
                return
            self._geraet = {
                "device_code": daten["device_code"],
                "ablauf": self._uhr() + float(daten.get("expires_in", 1800)),
                "abstand": max(1.0, float(daten.get("interval", 5))),
            }
            self._zustand_setzen(Anmeldung.WARTET)
            self.code_bereit.emit(str(daten.get("user_code", "")), str(daten.get("verification_uri", "")))
            self._nachfragen.start(int(self._geraet["abstand"] * 1000))

        self._netz.anfrage("POST", f"{self._id_adresse}/oauth2/device", antwort,
                           formular={"client_id": self.client_id, "scopes": RECHTE})

    def anmeldung_abbrechen(self) -> None:
        self._nachfragen.stop()
        self._geraet = {}
        if self.zustand is Anmeldung.WARTET:
            self._zustand_setzen(Anmeldung.ABGEMELDET)

    def _token_abholen(self) -> None:
        if self.zustand is not Anmeldung.WARTET or not self._geraet:
            return
        if self._uhr() > self._geraet["ablauf"]:
            self.anmeldung_abbrechen()
            self.meldung.emit(self._texte.meldung_twitch_code_abgelaufen, True)
            return

        def antwort(code, daten, _fehler):
            if self.zustand is not Anmeldung.WARTET:
                return  # inzwischen abgebrochen
            if code == 200 and isinstance(daten, dict) and daten.get("access_token"):
                self._geraet = {}
                self._daten = {"access_token": daten["access_token"], "refresh_token": daten.get("refresh_token", "")}
                self._pruefen_nach_anmeldung()
                return
            nachricht = str((daten or {}).get("message", "")) if isinstance(daten, dict) else ""
            if code == 0 or "authorization_pending" in nachricht or "slow_down" in nachricht:
                if "slow_down" in nachricht:
                    self._geraet["abstand"] += 5
                self._nachfragen.start(int(self._geraet["abstand"] * 1000))
                return
            # access_denied, invalid device code (abgelaufen) …
            log.info("Twitch-Anmeldung beendet: HTTP %s %s", code, nachricht)
            self.anmeldung_abbrechen()
            self.meldung.emit(self._texte.meldung_twitch_abgelehnt, True)

        self._netz.anfrage("POST", f"{self._id_adresse}/oauth2/token", antwort, formular={
            "client_id": self.client_id, "scopes": RECHTE,
            "device_code": self._geraet["device_code"], "grant_type": GERAETE_ART})

    def _pruefen_nach_anmeldung(self) -> None:
        def antwort(code, daten, _fehler):
            if code != 200 or not isinstance(daten, dict) or not daten.get("user_id"):
                self._abmelden_wegen_fehler()
                return
            self._daten.update(user_id=str(daten["user_id"]), login=str(daten.get("login", "")))
            self.name = self._daten["login"]
            self._speichern()
            self._zustand_setzen(Anmeldung.ANGEMELDET)
            self.meldung.emit(self._texte.meldung_twitch_angemeldet.format(name=self.name), False)
            self._anzeigenamen_laden()
            self.titel_laden()

        self._netz.anfrage("GET", f"{self._id_adresse}/oauth2/validate", antwort,
                           kopfzeilen={"Authorization": f"OAuth {self._daten['access_token']}"})

    def abmelden(self) -> None:
        """Knopf „Abmelden“: Anmeldung löschen (und bei Twitch ungültig machen)."""
        token = self._daten.get("access_token")
        if token:
            self._netz.anfrage("POST", f"{self._id_adresse}/oauth2/revoke", lambda *_: None,
                               formular={"client_id": self.client_id, "token": token})
        self._daten = {}
        self.name = self.titel = ""
        try:
            self._speicher.loeschen(SPEICHER_SCHLUESSEL)
        except SpeicherFehler:
            pass
        self.anmeldung_abbrechen()
        self._zustand_setzen(Anmeldung.ABGEMELDET)

    # ------------------------------------------------------------------
    #  Titel
    # ------------------------------------------------------------------
    def titel_laden(self) -> None:
        def antwort(code, daten, _fehler):
            if code == 200 and isinstance(daten, dict) and daten.get("data"):
                self.titel = str(daten["data"][0].get("title", ""))
                self.titel_geladen.emit(self.titel)

        self._helix("GET", f"channels?broadcaster_id={self._daten.get('user_id', '')}", antwort)

    def titel_setzen(self, titel: str, fertig=None) -> None:
        """Ändert den Streamtitel. fertig(erfolg, meldung)."""
        titel = " ".join((titel or "").split())  # keine Zeilenumbrüche/doppelten Leerzeichen
        if not titel:
            if fertig:
                fertig(False, self._texte.meldung_twitch_titel_leer)
            return
        if len(titel) > TITEL_HOECHSTLAENGE:
            if fertig:
                fertig(False, self._texte.meldung_twitch_titel_zu_lang.format(anzahl=TITEL_HOECHSTLAENGE))
            return

        def antwort(code, daten, _fehler):
            if 200 <= code < 300:
                self.titel = titel
                self.titel_geladen.emit(titel)
                if fertig:
                    fertig(True, self._texte.meldung_twitch_titel_ok)
                return
            log.warning("Titel ändern fehlgeschlagen: HTTP %s %.200s", code, daten)
            if code == 0:
                text = self._texte.meldung_twitch_kein_internet
            elif code == 401:
                text = self._texte.meldung_twitch_neu_anmelden
            else:
                text = self._texte.meldung_twitch_titel_fehler
            if fertig:
                fertig(False, text)

        self._helix("PATCH", f"channels?broadcaster_id={self._daten.get('user_id', '')}", antwort,
                    json_daten={"title": titel})

    def _anzeigenamen_laden(self) -> None:
        def antwort(code, daten, _fehler):
            if code == 200 and isinstance(daten, dict) and daten.get("data"):
                name = str(daten["data"][0].get("display_name") or "")
                if name and name != self.name:
                    self.name = self._daten["name"] = name
                    self._speichern()
                    self.anmeldung_geaendert.emit(self.zustand)

        self._helix("GET", f"users?id={self._daten.get('user_id', '')}", antwort)

    # ------------------------------------------------------------------
    def _helix(self, methode: str, pfad: str, rueckruf, json_daten=None, nochmal: bool = True) -> None:
        """Anfrage an die Twitch-API. Ist die Anmeldung abgelaufen, wird sie einmal erneuert."""
        if self.zustand is not Anmeldung.ANGEMELDET:
            rueckruf(401, None, "")
            return

        def antwort(code, daten, fehler):
            if code == 401 and nochmal:
                self._erneuern(danach=lambda: self._helix(methode, pfad, rueckruf, json_daten, nochmal=False),
                               sonst=lambda c: rueckruf(c, None, ""))
                return
            rueckruf(code, daten, fehler)

        self._netz.anfrage(methode, f"{self._api_adresse}/{pfad}", antwort, json_daten=json_daten, kopfzeilen={
            "Client-Id": self.client_id, "Authorization": f"Bearer {self._daten.get('access_token', '')}"})

    def _erneuern(self, danach, sonst=None) -> None:
        """Anmeldung mit dem Erneuerungsschlüssel verlängern (ohne Geheimnis erlaubt).
        Klappt es nicht, wird sonst(http_code) aufgerufen."""
        sonst = sonst or (lambda _code: None)
        erneuerung = self._daten.get("refresh_token")
        if not erneuerung or self._erneuert_gerade:
            self._abmelden_wegen_fehler()
            sonst(401)
            return
        self._erneuert_gerade = True

        def antwort(code, daten, _fehler):
            self._erneuert_gerade = False
            if code == 200 and isinstance(daten, dict) and daten.get("access_token"):
                self._daten["access_token"] = daten["access_token"]
                self._daten["refresh_token"] = daten.get("refresh_token", erneuerung)
                self._speichern()
                log.info("Twitch-Anmeldung erneuert")
                danach()
            elif code == 0:
                self.meldung.emit(self._texte.meldung_twitch_kein_internet, True)
                sonst(0)
            else:
                self._abmelden_wegen_fehler()
                sonst(401)

        self._netz.anfrage("POST", f"{self._id_adresse}/oauth2/token", antwort, formular={
            "client_id": self.client_id, "grant_type": "refresh_token", "refresh_token": erneuerung})

    def _abmelden_wegen_fehler(self) -> None:
        log.info("Twitch-Anmeldung ungültig – bitte neu anmelden")
        self._daten = {}
        self.name = self.titel = ""
        try:
            self._speicher.loeschen(SPEICHER_SCHLUESSEL)
        except SpeicherFehler:
            pass
        self._zustand_setzen(Anmeldung.ABGEMELDET)
        self.meldung.emit(self._texte.meldung_twitch_neu_anmelden, True)

    def _speichern(self) -> None:
        try:
            self._speicher.json_schreiben(SPEICHER_SCHLUESSEL, self._daten)
        except SpeicherFehler as fehler:
            log.error("Twitch-Anmeldung nicht speicherbar: %s", fehler)
            self.meldung.emit(self._texte.meldung_speicher_fehler, True)

    def _zustand_setzen(self, zustand: Anmeldung) -> None:
        if zustand is not self.zustand:
            self.zustand = zustand
            log.info("Twitch: %s", zustand.value)
        self.anmeldung_geaendert.emit(zustand)

    def beenden(self) -> None:
        self._nachfragen.stop()
        self._netz.alle_abbrechen()
