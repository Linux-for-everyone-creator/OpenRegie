"""Anbindung an Overlays.uno.

So funktioniert Uno: Jedes Uno-Projekt (eine „Control App“) hat eine geheime
API-Adresse, z. B.
    https://app.overlays.uno/apiv2/controlapps/AbC123…/api
An diese Adresse schickt OpenRegie Befehle (HTTP PUT mit JSON):
    {"command": "GetOverlays"}                       → Liste der Overlays
    {"command": "ShowOverlay", "id": "…"}            → einblenden
    {"command": "HideOverlay", "id": "…"}            → ausblenden
    {"command": "GetOverlayContent", "id": "…"}      → Texte/Felder lesen
    {"command": "SetOverlayContentField", "id": "…", "fieldId": "…", "value": "…"}
Antwort: {"status": 200, "result": "ok", "payload": …}

Es gibt zwei Arten von Uno-Adressen:
  - Projekte mit mehreren Overlays verstehen „GetOverlays“; jedes Overlay hat eine „id“.
  - Einzel-Unos (z. B. ein einzelnes „Countdown | Circles“) sind EIN Overlay. Sie lehnen
    „GetOverlays“ mit HTTP 400 „Invalid command: GetOverlays“ ab – die Adresse ist trotzdem
    gültig. Befehle an Einzel-Unos gehen ohne „id“.
Nur „nicht gefunden“ (404) bzw. ein ungültiger Schlüssel (401/403) heißt: Adresse falsch.

Wer die Adresse kennt, kann die Overlays steuern. Darum liegt sie nur im
Passwortspeicher des Systems (siehe geheimspeicher.py), nie im Klartext.

OpenRegie zeichnet keine eigenen Grafiken – das Aussehen kommt komplett von Uno.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from PySide6.QtCore import QObject, QTimer, Signal

from ..geheimspeicher import Geheimspeicher, SpeicherFehler
from ..netz import Netz

log = logging.getLogger("openregie.uno")

SPEICHER_SCHLUESSEL = "uno"
_TOKEN_MUSTER = re.compile(r"^[A-Za-z0-9_-]{8,200}$")
_ADRESS_MUSTER = re.compile(r"/apiv2/controlapps/([A-Za-z0-9_-]{8,200})(?:/api)?/?(?:[?#].*)?$")


def token_aus_text(text: str) -> str | None:
    """Holt den geheimen Teil aus einer eingefügten Uno-API-Adresse (oder nimmt ihn direkt)."""
    text = (text or "").strip().strip('"').strip("'")
    treffer = _ADRESS_MUSTER.search(text)
    if treffer:
        return treffer.group(1)
    if _TOKEN_MUSTER.match(text):
        return text
    return None


# ---------------------------------------------------------------------------
#  Antworten von Uno verstehen (Uno beschreibt das Format nicht genau –
#  darum werden mehrere übliche Schreibweisen erkannt)
# ---------------------------------------------------------------------------
_ID_SCHLUESSEL = ("id", "overlayId", "overlay_id", "uuid", "_id")
_NAME_SCHLUESSEL = ("name", "title", "overlayName", "label", "displayName")
_SICHTBAR_SCHLUESSEL = ("visible", "isVisible", "shown", "isShown", "show", "onAir", "onair", "active", "live")
_ZUSTAND_SCHLUESSEL = ("state", "status", "visibility")


def _erster(eintrag: dict, schluessel: tuple) -> object:
    for s in schluessel:
        if s in eintrag and eintrag[s] not in (None, ""):
            return eintrag[s]
    return None


def sichtbarkeit_lesen(eintrag: dict) -> bool | None:
    """True = im Stream sichtbar, False = ausgeblendet, None = Uno sagt es nicht."""
    wert = _erster(eintrag, _SICHTBAR_SCHLUESSEL)
    if isinstance(wert, bool):
        return wert
    if isinstance(wert, (int, float)):
        return bool(wert)
    if isinstance(wert, str) and wert.lower() in ("true", "false"):
        return wert.lower() == "true"
    zustand = _erster(eintrag, _ZUSTAND_SCHLUESSEL)
    if isinstance(zustand, str):
        z = zustand.strip().lower()
        if z in ("in", "on", "shown", "visible", "show", "live", "onair"):
            return True
        if z.startswith("out") or z in ("off", "hidden", "hide", "invisible"):
            return False
    return None


def overlays_lesen(payload) -> list[tuple[str, str, bool | None]]:
    """GetOverlays-Antwort → [(kennung, name, sichtbar)]."""
    if isinstance(payload, dict):
        for innen in ("overlays", "items", "data", "list"):
            if isinstance(payload.get(innen), (list, dict)):
                return overlays_lesen(payload[innen])
        # {kennung: {...}} oder {kennung: "Name"}
        eintraege = []
        for kennung, wert in payload.items():
            if isinstance(wert, dict):
                eintraege.append(dict(wert, id=wert.get("id", kennung)))
            elif isinstance(wert, str):
                eintraege.append({"id": kennung, "name": wert})
        payload = eintraege
    ergebnis = []
    if not isinstance(payload, list):
        return ergebnis
    for nr, eintrag in enumerate(payload, 1):
        if isinstance(eintrag, str):
            ergebnis.append((eintrag, eintrag, None))
            continue
        if not isinstance(eintrag, dict):
            continue
        kennung = _erster(eintrag, _ID_SCHLUESSEL)
        if kennung is None:
            continue
        name = _erster(eintrag, _NAME_SCHLUESSEL) or f"Overlay {nr}"
        ergebnis.append((str(kennung), str(name), sichtbarkeit_lesen(eintrag)))
    return ergebnis


_FARBE = re.compile(r"^#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")


def ist_textfeld(wert) -> bool:
    """Nur echte Texte zum Bearbeiten anzeigen – keine Farben, Bilder oder Schalter."""
    if not isinstance(wert, str):
        return False
    w = wert.strip()
    if _FARBE.match(w):
        return False
    if w.startswith(("http://", "https://", "data:")):
        return False
    return True


def felder_lesen(payload) -> list[tuple[str, str]]:
    """GetOverlayContent-Antwort → [(feldkennung, text)] – nur Textfelder."""
    if isinstance(payload, dict):
        for innen in ("content", "fields", "data", "payload"):
            if isinstance(payload.get(innen), (dict, list)):
                return felder_lesen(payload[innen])
        return [(str(k), v) for k, v in payload.items() if ist_textfeld(v)]
    felder = []
    if isinstance(payload, list):
        for eintrag in payload:
            if not isinstance(eintrag, dict):
                continue
            kennung = _erster(eintrag, ("fieldId", "id", "key", "name"))
            wert = eintrag.get("value")
            if kennung is not None and ist_textfeld(wert):
                felder.append((str(kennung), wert))
    return felder


# Arten von Fehlern bei Uno
UNBEKANNTER_BEFEHL = "unbekannter_befehl"  # Adresse gültig, Befehl passt nur nicht zu dieser Art Uno
NICHT_GEFUNDEN = "nicht_gefunden"  # Adresse/Schlüssel gibt es nicht
KEIN_INTERNET = "kein_internet"
SONSTIGER_FEHLER = "fehler"


def uno_fehlermeldung(daten) -> str:
    """Die Fehlermeldung von Uno, z. B. „Invalid command: GetOverlays“ (leer, wenn keine)."""
    if isinstance(daten, dict):
        fehler = daten.get("error")
        if isinstance(fehler, dict):
            return str(fehler.get("message") or "")
        if isinstance(fehler, str):
            return fehler
        return str(daten.get("message") or "")
    return ""


def fehlerart(code: int, daten) -> str:
    if code == 0:
        return KEIN_INTERNET
    meldung = uno_fehlermeldung(daten).strip().lower()
    if meldung.startswith("invalid command"):
        return UNBEKANNTER_BEFEHL
    if code in (401, 403, 404):
        return NICHT_GEFUNDEN
    return SONSTIGER_FEHLER


def uno_ok(code: int, daten) -> bool:
    if not 200 <= code < 300:
        return False
    if isinstance(daten, dict):
        if "error" in daten:
            return False
        if str(daten.get("result", "ok")).lower() not in ("ok", "success", "true"):
            return False
    return True


# ---------------------------------------------------------------------------
@dataclass
class Overlay:
    projekt: "UnoProjekt"
    kennung: str
    name: str
    sichtbar: bool | None = None  # None = noch unbekannt
    felder: list[tuple[str, str]] = field(default_factory=list)
    beschaeftigt: bool = False  # Befehl unterwegs

    @property
    def schluessel(self) -> str:
        """Eindeutig über alle Projekte hinweg."""
        return f"{self.projekt.token}/{self.kennung}"


class UnoProjekt:
    def __init__(self, name: str, token: str, einzeln: bool = False):
        self.name = name
        self.token = token
        self.einzeln = einzeln  # True = Einzel-Uno (genau ein Overlay, kennt kein „GetOverlays“)
        self.erreichbar: bool | None = None


class UnoVerwaltung(QObject):
    """Kennt alle Uno-Projekte und ihre Overlays, schickt Befehle, hält Tally-Lichter aktuell."""

    liste_geaendert = Signal()  # Overlays dazugekommen/weg
    overlay_geaendert = Signal(object)  # ein Overlay (Sichtbarkeit, Felder) hat sich geändert
    meldung = Signal(str, bool)  # (Text für Menschen, ist_fehler)

    def __init__(self, einstellungen_uno, texte, speicher: Geheimspeicher, parent=None, netz: Netz | None = None):
        super().__init__(parent)
        self._E = einstellungen_uno
        self._texte = texte
        self._speicher = speicher
        self._netz = netz or Netz(self)
        self.projekte: list[UnoProjekt] = []
        self.overlays: dict[str, Overlay] = {}  # schluessel -> Overlay (Reihenfolge bleibt)
        self.speicher_fehler = False

        self._abfrage = QTimer(self)
        self._abfrage.setInterval(max(1000, int(float(self._E.abfrage_sekunden) * 1000)))
        self._abfrage.timeout.connect(self._still_auffrischen)
        self._laedt = 0  # wie viele GetOverlays-Anfragen gerade unterwegs sind

    # ------------------------------------------------------------------
    #  Projekte (gespeichert im Passwortspeicher)
    # ------------------------------------------------------------------
    def laden(self) -> None:
        try:
            gespeichert = self._speicher.json_lesen(SPEICHER_SCHLUESSEL, []) or []
            self.speicher_fehler = False
        except SpeicherFehler as fehler:
            log.error("Passwortspeicher nicht erreichbar: %s", fehler)
            self.speicher_fehler = True
            self.meldung.emit(self._texte.meldung_speicher_fehler, True)
            gespeichert = []
        self.projekte = [UnoProjekt(str(p.get("name") or ""), str(p["token"]), bool(p.get("einzeln", False)))
                         for p in gespeichert if isinstance(p, dict) and p.get("token")]
        log.info("%d Uno-Projekt(e) geladen", len(self.projekte))
        self.auffrischen()
        self._abfrage.start()

    def _speichern(self) -> bool:
        try:
            self._speicher.json_schreiben(SPEICHER_SCHLUESSEL,
                                          [{"name": p.name, "token": p.token, "einzeln": p.einzeln}
                                           for p in self.projekte])
            return True
        except SpeicherFehler as fehler:
            log.error("Speichern im Passwortspeicher fehlgeschlagen: %s", fehler)
            self.meldung.emit(self._texte.meldung_speicher_fehler, True)
            return False

    def projekt_hinzufuegen(self, eingefuegter_text: str, fertig) -> None:
        """Prüft die Adresse bei Uno und speichert sie. fertig(erfolg, meldung)."""
        token = token_aus_text(eingefuegter_text)
        if not token:
            fertig(False, self._texte.meldung_uno_adresse_falsch)
            return
        if any(p.token == token for p in self.projekte):
            fertig(False, self._texte.meldung_uno_schon_da)
            return
        projekt = UnoProjekt(self._texte.uno_projekt_name.format(nummer=len(self.projekte) + 1), token)

        def antwort(ok, payload, fehler, art):
            if not ok and art == UNBEKANNTER_BEFEHL:
                # Adresse gültig, aber ein Einzel-Uno (kennt „GetOverlays“ nicht)
                projekt.einzeln = True
                projekt.name = self._texte.uno_einzel_name.format(nummer=len(self.projekte) + 1)
            elif not ok:
                # Nur „nicht gefunden“ heißt „Adresse falsch“ – sonst die echte Ursache nennen
                fertig(False, self._texte.meldung_uno_adresse_unbekannt if art == NICHT_GEFUNDEN else fehler)
                return
            projekt.erreichbar = True
            self.projekte.append(projekt)
            if not self._speichern():
                self.projekte.remove(projekt)
                fertig(False, self._texte.meldung_speicher_fehler)
                return
            if projekt.einzeln:
                self._einzel_overlay(projekt)
                fertig(True, self._texte.meldung_uno_einzel_ok)
            else:
                self._overlays_uebernehmen(projekt, payload)
                fertig(True, self._texte.meldung_uno_projekt_ok.format(anzahl=len(overlays_lesen(payload))))

        self._befehl(projekt, {"command": "GetOverlays"}, antwort)

    def projekt_entfernen(self, projekt: UnoProjekt) -> None:
        if projekt in self.projekte:
            self.projekte.remove(projekt)
            self._speichern()
            for s in [s for s, o in self.overlays.items() if o.projekt is projekt]:
                del self.overlays[s]
            self.liste_geaendert.emit()

    # ------------------------------------------------------------------
    #  Overlays
    # ------------------------------------------------------------------
    def auffrischen(self, still: bool = False) -> None:
        """Holt die Overlay-Listen aller Projekte neu (Knopf „Liste neu laden“)."""
        for projekt in self.projekte:
            if projekt.einzeln:
                # Einzel-Uno: immer genau ein Overlay, keine Liste zum Abfragen
                self._einzel_overlay(projekt)
                continue
            self._laedt += 1

            def antwort(ok, payload, fehler, art, p=projekt):
                self._laedt -= 1
                war = p.erreichbar
                if not ok and art == UNBEKANNTER_BEFEHL:
                    # Gespeichertes Projekt ist in Wahrheit ein Einzel-Uno: merken
                    log.info("Uno-Projekt %s ist ein Einzel-Uno", p.name)
                    p.einzeln, ok = True, True
                    self._speichern()
                    self._einzel_overlay(p)
                    payload = None
                p.erreichbar = ok
                if ok:
                    if not p.einzeln:
                        self._overlays_uebernehmen(p, payload)
                    if war is False:
                        self.meldung.emit("", False)
                elif not still or war is not False:
                    log.warning("Uno-Projekt %s nicht erreichbar: %s", p.name, fehler)
                    self.meldung.emit(fehler, True)

            self._befehl(projekt, {"command": "GetOverlays"}, antwort)

    def _still_auffrischen(self) -> None:
        if self._laedt == 0:  # nicht stapeln, wenn Uno langsam ist
            self.auffrischen(still=True)

    def _einzel_overlay(self, projekt: UnoProjekt) -> None:
        """Ein Einzel-Uno ist genau ein Overlay (ohne Kennung)."""
        schluessel = f"{projekt.token}/"
        anders = False
        for s in [s for s, o in self.overlays.items() if o.projekt is projekt and s != schluessel]:
            del self.overlays[s]
            anders = True
        if schluessel not in self.overlays:
            self.overlays[schluessel] = Overlay(projekt, "", projekt.name)
            anders = True
        if anders:
            self.liste_geaendert.emit()

    def _overlays_uebernehmen(self, projekt: UnoProjekt, payload) -> None:
        neu = overlays_lesen(payload)
        vorher = [s for s, o in self.overlays.items() if o.projekt is projekt]
        gesehen = []
        liste_anders = False
        for kennung, name, sichtbar in neu:
            schluessel = f"{projekt.token}/{kennung}"
            gesehen.append(schluessel)
            o = self.overlays.get(schluessel)
            if o is None:
                self.overlays[schluessel] = Overlay(projekt, kennung, name, sichtbar)
                liste_anders = True
                continue
            geaendert = False
            if o.name != name:
                o.name, liste_anders = name, True
            # Während ein eigener Befehl unterwegs ist, nicht vom alten Stand überschreiben lassen
            if sichtbar is not None and sichtbar != o.sichtbar and not o.beschaeftigt:
                o.sichtbar, geaendert = sichtbar, True
            if geaendert:
                self.overlay_geaendert.emit(o)
        for schluessel in vorher:
            if schluessel not in gesehen:
                del self.overlays[schluessel]
                liste_anders = True
        if liste_anders:
            self.liste_geaendert.emit()

    def umschalten(self, overlay: Overlay, fertig=None) -> None:
        """Einblenden, wenn aus – ausblenden, wenn an (Tally-Licht zeigt den Zustand)."""
        self.sichtbar_setzen(overlay, not bool(overlay.sichtbar), fertig)

    def sichtbar_setzen(self, overlay: Overlay, sichtbar: bool, fertig=None) -> None:
        if overlay.beschaeftigt:
            return
        overlay.beschaeftigt = True
        self.overlay_geaendert.emit(overlay)
        befehl = "ShowOverlay" if sichtbar else "HideOverlay"

        def antwort(ok, _payload, fehler, _art):
            overlay.beschaeftigt = False
            if ok:
                overlay.sichtbar = sichtbar
            else:
                self.meldung.emit(fehler, True)
            self.overlay_geaendert.emit(overlay)
            if fertig:
                fertig(ok, fehler)

        self._befehl(overlay.projekt, self._overlay_befehl(overlay, befehl), antwort)

    def felder_laden(self, overlay: Overlay, fertig=None) -> None:
        def antwort(ok, payload, fehler, _art):
            if ok:
                overlay.felder = felder_lesen(payload)
                self.overlay_geaendert.emit(overlay)
            if fertig:
                fertig(ok, fehler)

        self._befehl(overlay.projekt, self._overlay_befehl(overlay, "GetOverlayContent"), antwort)

    def feld_setzen(self, overlay: Overlay, feld: str, text: str, fertig=None) -> None:
        def antwort(ok, _payload, fehler, _art):
            if ok:
                overlay.felder = [(k, text if k == feld else v) for k, v in overlay.felder]
                self.overlay_geaendert.emit(overlay)
            if fertig:
                fertig(ok, fehler)

        self._befehl(overlay.projekt, self._overlay_befehl(overlay, "SetOverlayContentField",
                                                           fieldId=feld, value=text), antwort)

    # ------------------------------------------------------------------
    @staticmethod
    def _overlay_befehl(overlay: Overlay, befehl: str, **mehr) -> dict:
        """Befehl für ein Overlay. Einzel-Unos bekommen keine „id“."""
        nachricht = {"command": befehl}
        if overlay.kennung:
            nachricht["id"] = overlay.kennung
        nachricht.update(mehr)
        return nachricht

    def _befehl(self, projekt: UnoProjekt, befehl: dict, rueckruf) -> None:
        """Schickt einen Befehl. rueckruf(ok, payload, fehlertext_fuer_menschen, fehlerart)."""
        adresse = f"{str(self._E.basisadresse).rstrip('/')}/apiv2/controlapps/{projekt.token}/api"

        def fertig(code, daten, netzfehler):
            if uno_ok(code, daten):
                rueckruf(True, daten.get("payload") if isinstance(daten, dict) else daten, "", "")
                return
            art = fehlerart(code, daten)
            text = {
                KEIN_INTERNET: self._texte.meldung_uno_kein_internet,
                NICHT_GEFUNDEN: self._texte.meldung_uno_adresse_unbekannt,
                UNBEKANNTER_BEFEHL: self._texte.meldung_uno_befehl_unbekannt,
            }.get(art, self._texte.meldung_uno_fehler)
            # Den geheimen Teil der Adresse nie ins Protokoll schreiben
            log.info("Uno-Befehl %s abgelehnt (HTTP %s, %s): %.200s %s",
                     befehl.get("command"), code, art, daten, netzfehler)
            rueckruf(False, None, text, art)

        self._netz.anfrage("PUT", adresse, fertig, json_daten=befehl)

    def beenden(self) -> None:
        self._abfrage.stop()
        self._netz.alle_abbrechen()
