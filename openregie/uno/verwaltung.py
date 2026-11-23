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
    gültig. Gesteuert werden sie über die Singular-Schnittstelle (siehe einzel.py), denn
    „ShowOverlay“ über …/api wird bei ihnen angenommen, zeigt aber nichts an.
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

import time

from ..geheimspeicher import Geheimspeicher, SpeicherFehler
from ..hintergrund import Hintergrund
from ..netz import Netz
from . import einzel
from .einzel import Bauplan, Feld

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


def felder_lesen(payload) -> list[Feld]:
    """GetOverlayContent-Antwort → Textfelder (keine Farben, Bilder, Schalter)."""
    if isinstance(payload, dict):
        for innen in ("content", "fields", "data", "payload"):
            if isinstance(payload.get(innen), (dict, list)):
                return felder_lesen(payload[innen])
        return [Feld(str(k), str(k), v) for k, v in payload.items() if ist_textfeld(v)]
    felder = []
    if isinstance(payload, list):
        for eintrag in payload:
            if not isinstance(eintrag, dict):
                continue
            kennung = _erster(eintrag, ("fieldId", "id", "key", "name"))
            wert = eintrag.get("value")
            if kennung is not None and ist_textfeld(wert):
                felder.append(Feld(str(kennung), str(kennung), wert))
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
    felder: list[Feld] = field(default_factory=list)
    beschaeftigt: bool = False  # Befehl unterwegs
    vorschaubild: str = ""  # Adresse eines kleinen Vorschaubilds (nur Einzel-Unos)
    bauplan: Bauplan | None = None  # nur Einzel-Unos
    timer: dict | None = None  # Zeitgeber-Zustand von Uno (nur mit Countdown)
    dauer: int | None = None  # Countdown-Dauer in Sekunden
    stand_ms: float = 0.0  # wann Timer/Dauer zuletzt von Uno kamen (für die Anzeige)
    # Zählt eigene Countdown-Änderungen. Eine Antwort von Uno, die VOR der letzten Änderung angefragt
    # wurde, darf Dauer und Zeitgeber nicht mit dem alten Stand überschreiben (sonst springt die Zeit kurz zurück).
    countdown_stand: int = 0
    # Countdown-Befehle gehen NACHEINANDER zu Uno (sonst kann ein späterer Befehl einen früheren überholen,
    # z. B. „−1 Min“ und gleich danach eine eingetippte Zeit – dann gilt bei Uno die falsche Zeit).
    countdown_schlange: list = field(default_factory=list)
    countdown_unterwegs: bool = False
    bild_daten: bytes | None = None  # geladenes Vorschaubild (b"" = keins)
    # Funktionen, die dieses Uno nicht kann (Uno sagt „Invalid command“): werden still ausgegraut
    nicht_unterstuetzt: set = field(default_factory=set)

    @property
    def bereit(self) -> bool:
        """False, solange ein Einzel-Uno noch nicht von Uno gelesen wurde (z. B. direkt nach dem Start)."""
        return not (self.projekt.einzeln and self.bauplan is None)

    @property
    def hat_countdown(self) -> bool:
        return bool(self.bauplan and self.bauplan.timer)

    def restzeit_ms(self, jetzt_ms: float | None = None) -> int | None:
        return einzel.restzeit_ms(self.timer, self.dauer, time.time() * 1000 if jetzt_ms is None else jetzt_ms)

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
        self.meldung = ""  # warum nicht erreichbar (für Menschen)
        self.ausgabe = ""  # Ausgabe-Adresse für OBS (Browserquelle), kommt von Uno


# Funktionen eines Overlays (für „nicht unterstützt“)
EIN_AUS, TEXTE, COUNTDOWN = "ein_aus", "texte", "countdown"


class UnoVerwaltung(QObject):
    """Kennt alle Uno-Projekte und ihre Overlays, schickt Befehle, hält Tally-Lichter aktuell."""

    liste_geaendert = Signal()  # Overlays dazugekommen/weg
    ausgaben_geaendert = Signal()  # Ausgabe-Adressen für OBS dazugekommen/weg
    overlay_geaendert = Signal(object)  # ein Overlay (Sichtbarkeit, Felder) hat sich geändert
    meldung = Signal(str, bool)  # (Text für Menschen, ist_fehler)

    def __init__(self, einstellungen_uno, texte, speicher: Geheimspeicher, parent=None, netz: Netz | None = None):
        super().__init__(parent)
        self._E = einstellungen_uno
        self._texte = texte
        self._speicher = speicher
        self._netz = netz or Netz(self, zeitlimit_ms=int(float(self._E.zeitlimit_sekunden) * 1000))
        self._hintergrund = Hintergrund(self, "openregie-uno-speicher")
        self._letzte_meldung: tuple[str, bool] | None = None
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
        """Gespeicherte Projekte aus dem Passwortspeicher holen – im Hintergrund (der kann warten)."""
        self._hintergrund.ausfuehren(lambda: self._speicher.json_lesen(SPEICHER_SCHLUESSEL, []), self._geladen)

    def _geladen(self, gespeichert, fehler) -> None:
        if isinstance(fehler, SpeicherFehler):
            log.error("Passwortspeicher nicht erreichbar: %s", fehler)
            self.speicher_fehler = True
            self._melden(self._texte.meldung_speicher_fehler, True)
            gespeichert = []
        elif fehler is not None:
            raise fehler
        else:
            self.speicher_fehler = False
        gespeichert = gespeichert or []
        self.projekte = [UnoProjekt(str(p.get("name") or ""), str(p["token"]), bool(p.get("einzeln", False)))
                         for p in gespeichert if isinstance(p, dict) and p.get("token")]
        log.info("%d Uno-Projekt(e) geladen", len(self.projekte))
        self.auffrischen()
        self._abfrage.start()

    def _speichern(self, fertig=None) -> None:
        """Projekte im Passwortspeicher sichern – im Hintergrund. fertig(erfolg)."""
        stand = [{"name": p.name, "token": p.token, "einzeln": p.einzeln} for p in self.projekte]

        def gespeichert(_ergebnis, fehler):
            if fehler is not None:
                log.error("Speichern im Passwortspeicher fehlgeschlagen: %s", fehler)
                self._melden(self._texte.meldung_speicher_fehler, True)
            if fertig:
                fertig(fehler is None)

        self._hintergrund.ausfuehren(lambda: self._speicher.json_schreiben(SPEICHER_SCHLUESSEL, stand), gespeichert)

    def _melden(self, text: str, fehler: bool) -> None:
        """Meldung unter der Bibliothek – dieselbe nie zweimal hintereinander."""
        if self._letzte_meldung == (text, fehler):
            return
        self._letzte_meldung = (text, fehler)
        self.meldung.emit(text, fehler)

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

        def speichern(danach) -> None:
            if any(p.token == token for p in self.projekte):
                fertig(False, self._texte.meldung_uno_schon_da)  # zweimal schnell geklickt
                return
            projekt.erreichbar = True
            self.projekte.append(projekt)

            def gespeichert(ok):
                if ok:
                    danach()
                else:
                    if projekt in self.projekte:
                        self.projekte.remove(projekt)
                    fertig(False, self._texte.meldung_speicher_fehler)

            self._speichern(gespeichert)

        def einzel_fertig(overlay, fehler, _art=""):
            if overlay is None:
                fertig(False, fehler)
                return

            def eintragen():
                self._einzel_eintragen(overlay)
                fertig(True, self._texte.meldung_uno_einzel_ok)

            speichern(eintragen)

        def antwort(ok, payload, fehler, art):
            if ok:
                def eintragen():
                    self._overlays_uebernehmen(projekt, payload)
                    self._ausgabe_holen(projekt)
                    fertig(True, self._texte.meldung_uno_projekt_ok.format(anzahl=len(overlays_lesen(payload))))

                speichern(eintragen)
            elif art == UNBEKANNTER_BEFEHL:
                # Adresse gültig, aber ein Einzel-Uno (kennt „GetOverlays“ nicht)
                projekt.einzeln = True
                projekt.name = self._texte.uno_einzel_name.format(nummer=len(self.projekte) + 1)
                self._einzel_einlesen(projekt, einzel_fertig)
            else:
                # Nur „nicht gefunden“ heißt „Adresse falsch“ – sonst die echte Ursache nennen
                fertig(False, self._texte.meldung_uno_adresse_unbekannt if art == NICHT_GEFUNDEN else fehler)

        self._befehl(projekt, {"command": "GetOverlays"}, antwort)

    def projekt_entfernen(self, projekt: UnoProjekt) -> None:
        if projekt in self.projekte:
            self.projekte.remove(projekt)
            self._speichern()
            for s in [s for s, o in self.overlays.items() if o.projekt is projekt]:
                del self.overlays[s]
            self.liste_geaendert.emit()
            if projekt.ausgabe:
                self.ausgaben_geaendert.emit()

    # ------------------------------------------------------------------
    #  Einzel-Unos (Singular-Schnittstelle)
    # ------------------------------------------------------------------
    def _einzel_einlesen(self, projekt: UnoProjekt, fertig, overlay: Overlay | None = None) -> None:
        """Name, Bauplan und Zustand holen (3 Anfragen). fertig(overlay | None, fehlertext, fehlerart).

        Ist schon ein (leeres) Overlay da, wird GENAU DIESES gefüllt – nie ein neues angelegt.
        Sonst würde z. B. der Bereich „Ausgewählt“ an einem leeren Platzhalter hängen bleiben.
        """
        overlay = overlay or Overlay(projekt, "", projekt.name)

        def info(ok, daten, fehler, art):
            if not ok:
                fertig(None, fehler, art)
                return
            if isinstance(daten, dict):
                name = str(daten.get("name") or "").strip()
                if name:
                    overlay.name = projekt.name = name
                self._ausgabe_merken(projekt, daten)
                bild = str(daten.get("thumbnail") or "")
                if bild.startswith("//"):
                    bild = "https:" + bild
                if bild.startswith(("https://", "http://")):
                    overlay.vorschaubild = bild
            self._singular(projekt, "GET", "/model", None, bauplan)

        def bauplan(ok, daten, fehler, art):
            if not ok:
                fertig(None, fehler, art)
                return
            plan = einzel.bauplan_lesen(daten)
            if plan is None:
                log.warning("Bauplan von Uno nicht verständlich: %.300s", daten)
                fertig(None, self._texte.meldung_uno_fehler, SONSTIGER_FEHLER)
                return
            self._singular(projekt, "GET", "/control", None, lambda *a: zustand(plan, *a))

        def zustand(plan, ok, daten, fehler, art):
            if not ok:
                fertig(None, fehler, art)
                return
            einzel.ein_teile_ergaenzen(plan, daten)
            overlay.bauplan = plan  # erst jetzt: vorher gilt das Overlay als „wird geladen“
            self._zustand_uebernehmen(overlay, daten)
            self.overlay_geaendert.emit(overlay)
            fertig(overlay, "", "")

        self._singular(projekt, "GET", "", None, info)

    def _ausgabe_merken(self, projekt: UnoProjekt, info) -> None:
        adresse = str(info.get("outputUrl") or "") if isinstance(info, dict) else ""
        if adresse.startswith("//"):
            adresse = "https:" + adresse
        if adresse.startswith(("https://", "http://")) and adresse != projekt.ausgabe:
            projekt.ausgabe = adresse
            self.ausgaben_geaendert.emit()

    def _ausgabe_holen(self, projekt: UnoProjekt) -> None:
        """Bei Projekten mit mehreren Overlays: Ausgabe-Adresse einmal über GET … holen."""
        if projekt.ausgabe or getattr(projekt, "_ausgabe_unterwegs", False):
            return
        projekt._ausgabe_unterwegs = True

        def antwort(ok, daten, _fehler, _art):
            projekt._ausgabe_unterwegs = False
            if ok:
                self._ausgabe_merken(projekt, daten)
            else:
                log.info("Ausgabe-Adresse von %s nicht lesbar", projekt.name)

        self._singular(projekt, "GET", "", None, antwort)

    def ausgaben(self) -> list[tuple[str, str]]:
        """(Projektname, Ausgabe-Adresse) aller Projekte, deren Adresse bekannt ist."""
        return [(p.name, p.ausgabe) for p in self.projekte if p.ausgabe]

    def _einzel_eintragen(self, overlay: Overlay) -> None:
        schluessel = overlay.schluessel
        anders = False
        for s in [s for s, o in self.overlays.items() if o.projekt is overlay.projekt and s != schluessel]:
            del self.overlays[s]
            anders = True
        if self.overlays.get(schluessel) is not overlay:
            self.overlays[schluessel] = overlay
            anders = True
        if anders:
            self.liste_geaendert.emit()

    def _zustand_uebernehmen(self, overlay: Overlay, control, countdown_stand: int | None = None) -> None:
        """GET …/control → Tally, Countdown und Texte des Overlays.

        countdown_stand: overlay.countdown_stand beim Absenden der Anfrage. Gab es seitdem eine eigene
        Countdown-Änderung, bleiben Dauer und Zeitgeber, wie sie sind (die Antwort ist schon veraltet).
        """
        plan = overlay.bauplan
        if plan is None:
            return
        teile = einzel.teile_lesen(control)
        vorher = (overlay.sichtbar, overlay.timer, overlay.dauer)
        sichtbar = einzel.ist_sichtbar(teile, plan)
        # Während ein eigener Befehl unterwegs ist, nicht vom alten Stand überschreiben lassen
        if sichtbar is not None and not overlay.beschaeftigt:
            overlay.sichtbar = sichtbar
        if countdown_stand is None or countdown_stand == overlay.countdown_stand:
            timer = einzel.wert(teile, plan.timer)
            overlay.timer = dict(timer) if isinstance(timer, dict) else None
            overlay.dauer = einzel.dauer_sekunden(einzel.wert(teile, plan.dauer))
        overlay.felder = einzel.textfelder_lesen(teile, plan)
        overlay.stand_ms = time.time() * 1000
        if (overlay.sichtbar, overlay.timer, overlay.dauer) != vorher:
            self.overlay_geaendert.emit(overlay)

    def _einzel_overlay(self, projekt: UnoProjekt) -> Overlay:
        """Das (evtl. noch leere) Overlay eines Einzel-Unos – damit es auch ohne Internet in der Liste steht."""
        schluessel = f"{projekt.token}/"
        overlay = self.overlays.get(schluessel)
        if overlay is None:
            overlay = Overlay(projekt, "", projekt.name)
            self._einzel_eintragen(overlay)
        return overlay

    # ------------------------------------------------------------------
    #  Overlays
    # ------------------------------------------------------------------
    def auffrischen(self, still: bool = False) -> None:
        """Holt Overlays und Zustände aller Projekte neu (Knopf „Liste neu laden“ und Tally-Abfrage)."""
        for projekt in self.projekte:
            self._laedt += 1
            if projekt.einzeln:
                overlay = self._einzel_overlay(projekt)
                if overlay.bauplan is None:
                    self._einzel_einlesen(projekt, lambda o, f, a, p=projekt: self._einzel_neu(p, o, f, a, still),
                                          overlay)
                else:
                    self._singular(projekt, "GET", "/control", None,
                                   lambda ok, d, f, a, p=projekt, o=overlay, n=overlay.countdown_stand:
                                   self._einzel_stand(p, o, ok, d, f, a, still, n))
                continue

            def antwort(ok, payload, fehler, art, p=projekt):
                if not ok and art == UNBEKANNTER_BEFEHL:
                    # Gespeichertes Projekt ist in Wahrheit ein Einzel-Uno (gespeichert mit Build 1.1)
                    log.info("Uno-Projekt %s ist ein Einzel-Uno", p.name)
                    p.einzeln = True
                    for s in [s for s, o in self.overlays.items() if o.projekt is p]:
                        del self.overlays[s]
                    platzhalter = self._einzel_overlay(p)
                    self._einzel_einlesen(p, lambda o, f, a: self._einzel_neu(p, o, f, a, still, speichern=True),
                                          platzhalter)
                    return
                self._laedt -= 1
                if ok:
                    self._overlays_uebernehmen(p, payload)
                    self._ausgabe_holen(p)
                self._erreichbar(p, ok, fehler, art)

            self._befehl(projekt, {"command": "GetOverlays"}, antwort)

    def _einzel_neu(self, projekt, overlay, fehler, art, still, speichern=False) -> None:
        self._laedt -= 1
        if overlay is not None:
            self._einzel_eintragen(overlay)
            if speichern or overlay.name != projekt.name:
                self._speichern()
        self._erreichbar(projekt, overlay is not None, fehler, art)

    def _einzel_stand(self, projekt, overlay, ok, daten, fehler, art, still, countdown_stand=None) -> None:
        self._laedt -= 1
        if ok:
            self._zustand_uebernehmen(overlay, daten, countdown_stand)
        self._erreichbar(projekt, ok, fehler, art)

    def _erreichbar(self, projekt: UnoProjekt, ok: bool, fehler: str, art: str = "") -> None:
        """Merkt sich, ob ein Projekt erreichbar ist, und meldet es EINMAL unter der Bibliothek.

        „Invalid command“ heißt: Uno ist da, kann nur diesen Befehl nicht – das ist kein Ausfall.
        """
        if not ok and art == UNBEKANNTER_BEFEHL:
            ok = True
        war, alte_meldung = projekt.erreichbar, projekt.meldung
        projekt.erreichbar = ok
        projekt.meldung = "" if ok else fehler
        if (war, alte_meldung) == (ok, projekt.meldung):
            return
        if not ok:
            log.warning("Uno-Projekt %s nicht erreichbar: %s", projekt.name, fehler)
        for o in self.overlays.values():
            if o.projekt is projekt:
                self.overlay_geaendert.emit(o)  # Lampen grau bzw. wieder grün
        meldungen = [p.meldung for p in self.projekte if p.meldung]
        if meldungen:
            self._melden(meldungen[0], True)
        elif self._letzte_meldung and self._letzte_meldung[1]:
            self._melden("", False)

    def _aktion_fehlgeschlagen(self, overlay: Overlay, funktion: str, fehler: str, art: str) -> str:
        """Nach einem fehlgeschlagenen Klick: Was soll im Bedienfeld stehen? ("" = nichts)

        - kein Internet / Zeitüberschreitung, Adresse ungültig: steht EINMAL unter der Bibliothek
        - „Invalid command“: Funktion still ausgrauen, keine rote Meldung
        - sonstiger Fehler (z. B. Uno-Störung): Meldung im Bedienfeld
        """
        if art == UNBEKANNTER_BEFEHL:
            log.info("Uno-Overlay %s kann „%s“ nicht – wird ausgegraut", overlay.name, funktion)
            overlay.nicht_unterstuetzt.add(funktion)
            self.overlay_geaendert.emit(overlay)
            return ""
        if art in (KEIN_INTERNET, NICHT_GEFUNDEN):
            self._erreichbar(overlay.projekt, False, fehler, art)
            return ""
        return fehler

    def _still_auffrischen(self) -> None:
        if self._laedt == 0:  # nicht stapeln, wenn Uno langsam ist
            self.auffrischen(still=True)

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
        if overlay.projekt.einzeln and overlay.bauplan is None:
            self._noch_nicht_bereit(fertig)
            return
        overlay.beschaeftigt = True
        self.overlay_geaendert.emit(overlay)

        def antwort(ok, _payload, fehler, art):
            overlay.beschaeftigt = False
            if ok:
                overlay.sichtbar = sichtbar
                self._erreichbar(overlay.projekt, True, "")
            else:
                fehler = self._aktion_fehlgeschlagen(overlay, EIN_AUS, fehler, art)
            self.overlay_geaendert.emit(overlay)
            if fertig:
                fertig(ok, fehler)

        if overlay.bauplan is not None:
            self._singular(overlay.projekt, "PATCH", "/control", einzel.ein_aus_befehl(overlay.bauplan, sichtbar),
                           antwort)
        else:
            befehl = "ShowOverlay" if sichtbar else "HideOverlay"
            self._befehl(overlay.projekt, self._overlay_befehl(overlay, befehl), antwort)

    def felder_laden(self, overlay: Overlay, fertig=None, countdown_stand: int | None = None) -> None:
        """Texte (und bei Einzel-Unos auch Tally und Countdown) frisch von Uno holen.

        countdown_stand: nach einer eigenen Änderung deren Stand vom START der Änderung – kam seitdem
        eine neuere Countdown-Änderung, ist diese Antwort für Dauer und Zeitgeber schon veraltet.
        """
        if overlay.projekt.einzeln:
            if overlay.bauplan is None:
                self._noch_nicht_bereit(fertig)
                return

            if countdown_stand is None:
                countdown_stand = overlay.countdown_stand

            def stand(ok, daten, fehler, art):
                if ok:
                    self._zustand_uebernehmen(overlay, daten, countdown_stand)
                    self._erreichbar(overlay.projekt, True, "")
                else:
                    fehler = self._aktion_fehlgeschlagen(overlay, TEXTE, fehler, art)
                if fertig:
                    fertig(ok, fehler)

            self._singular(overlay.projekt, "GET", "/control", None, stand)
            return

        def antwort(ok, payload, fehler, art):
            if ok:
                overlay.felder = felder_lesen(payload)
                self.overlay_geaendert.emit(overlay)
            else:
                fehler = self._aktion_fehlgeschlagen(overlay, TEXTE, fehler, art)
            if fertig:
                fertig(ok, fehler)

        self._befehl(overlay.projekt, self._overlay_befehl(overlay, "GetOverlayContent"), antwort)

    def feld_setzen(self, overlay: Overlay, feld: Feld, text: str, fertig=None) -> None:
        def antwort(ok, _payload, fehler, art):
            if ok:
                for f in overlay.felder:
                    if f.kennung == feld.kennung and f.teil == feld.teil:
                        f.wert = text
            else:
                fehler = self._aktion_fehlgeschlagen(overlay, TEXTE, fehler, art)
            if fertig:
                fertig(ok, fehler)

        if overlay.projekt.einzeln:
            self._singular(overlay.projekt, "PATCH", "/control",
                           [{"subCompositionId": feld.teil, "payload": {feld.kennung: text}}], antwort)
        else:
            self._befehl(overlay.projekt, self._overlay_befehl(overlay, "SetOverlayContentField",
                                                               fieldId=feld.kennung, value=text), antwort)

    # --- Countdown (nur Einzel-Unos mit Zeitgeber) ---------------------------
    def timer_befehl(self, overlay: Overlay, befehl: str, fertig=None) -> None:
        """befehl: "play" (Start/Weiter), "pause", "reset" (zurück auf die volle Dauer) oder
        "neu" (abgelaufener Countdown: zurücksetzen und gleich wieder starten)."""
        plan = overlay.bauplan
        if plan is None or plan.timer is None:
            self._noch_nicht_bereit(fertig)
            return
        teil, feld = plan.timer
        befehle = ["reset", "play"] if befehl == "neu" else [befehl]
        overlay.countdown_stand += 1  # ältere Antworten von Uno sollen das nicht zurückdrehen
        mein_stand = overlay.countdown_stand
        self._countdown_einreihen(overlay, [[{"subCompositionId": teil, "payload": {feld: {"command": b}}}]
                                            for b in befehle], mein_stand, fertig)

    def dauer_setzen(self, overlay: Overlay, sekunden: int, fertig=None) -> None:
        plan = overlay.bauplan
        if plan is None or plan.dauer is None:
            self._noch_nicht_bereit(fertig)
            return
        sekunden = max(0, min(int(sekunden), int(self._E.countdown_hoechstdauer_sekunden)))
        teil, feld = plan.dauer
        overlay.dauer = sekunden  # sofort anzeigen, Uno bestätigt gleich
        overlay.countdown_stand += 1  # ältere Antworten von Uno sollen das nicht zurückdrehen
        mein_stand = overlay.countdown_stand
        self.overlay_geaendert.emit(overlay)
        self._countdown_einreihen(overlay, [[{"subCompositionId": teil, "payload": {feld: sekunden}}]], mein_stand,
                                  fertig)

    def countdown_zeit_setzen(self, overlay: Overlay, sekunden: int, fertig=None) -> None:
        """Eingetippte Zeit: Dauer setzen – und hat der Countdown schon gezählt, ihn im selben
        Befehl auf die neue Zeit zurücksetzen. So zeigen OpenRegie und Uno danach genau diese Zeit."""
        plan = overlay.bauplan
        if plan is None or plan.dauer is None:
            self._noch_nicht_bereit(fertig)
            return
        sekunden = max(0, min(int(sekunden), int(self._E.countdown_hoechstdauer_sekunden)))
        teil, feld = plan.dauer
        befehl = [{"subCompositionId": teil, "payload": {feld: sekunden}}]
        zuruecksetzen = plan.timer is not None and einzel.hat_gezaehlt(overlay.timer)
        if zuruecksetzen:
            t_teil, t_feld = plan.timer
            reset = {t_feld: {"command": "reset"}}
            if t_teil == teil:
                befehl[0]["payload"].update(reset)
            else:
                befehl.append({"subCompositionId": t_teil, "payload": reset})

        vorher = (overlay.dauer, overlay.timer)
        overlay.dauer = sekunden  # sofort anzeigen, Uno bestätigt gleich
        overlay.countdown_stand += 1  # ältere Antworten von Uno sollen das nicht zurückdrehen
        mein_stand = overlay.countdown_stand
        if zuruecksetzen:
            overlay.timer = dict(overlay.timer, value=0, isRunning=False)
        self.overlay_geaendert.emit(overlay)

        def abgelehnt():
            # Uno hat die neue Zeit nicht angenommen: wieder den alten Stand zeigen
            if overlay.countdown_stand == mein_stand:  # nur, wenn seitdem nichts anderes geändert wurde
                overlay.dauer, overlay.timer = vorher
                self.overlay_geaendert.emit(overlay)

        self._countdown_einreihen(overlay, [befehl], mein_stand, fertig, abgelehnt)

    def _countdown_einreihen(self, overlay: Overlay, patches: list, mein_stand: int, fertig, abgelehnt=None) -> None:
        """Countdown-Änderung in die Warteschlange des Overlays: Die PATCHes gehen nacheinander zu Uno,
        danach wird der echte Stand gelesen (Uno setzt z. B. die Startzeit selbst). Erst dann kommt
        die nächste Änderung an die Reihe."""
        overlay.countdown_schlange.append((list(patches), mein_stand, fertig, abgelehnt))
        if not overlay.countdown_unterwegs:
            self._countdown_naechster(overlay)

    def _countdown_naechster(self, overlay: Overlay) -> None:
        if not overlay.countdown_schlange:
            overlay.countdown_unterwegs = False
            return
        overlay.countdown_unterwegs = True
        patches, mein_stand, fertig, abgelehnt = overlay.countdown_schlange.pop(0)

        def erledigt(ok, fehler):
            if fertig:
                fertig(ok, fehler)
            self._countdown_naechster(overlay)

        def senden(rest):
            if not rest:
                self.felder_laden(overlay, erledigt, mein_stand)  # angenommen: echten Stand von Uno lesen
                return

            def geaendert(ok, _daten, fehler, art):
                if not ok:
                    fehler = self._aktion_fehlgeschlagen(overlay, COUNTDOWN, fehler, art)
                    if abgelehnt:
                        abgelehnt()
                    erledigt(False, fehler)
                    return
                senden(rest[1:])

            self._singular(overlay.projekt, "PATCH", "/control", rest[0], geaendert)

        senden(patches)

    def bild_laden(self, overlay: Overlay, fertig) -> None:
        """Kleines Vorschaubild von Uno holen. fertig(bytes | None). Wird pro Overlay gemerkt."""
        if overlay.bild_daten is not None:
            fertig(overlay.bild_daten or None)
            return
        if not overlay.vorschaubild.startswith(("https://", "http://")):
            fertig(None)
            return

        def antwort(code, daten, _fehler):
            ok = 200 <= code < 300 and isinstance(daten, bytes) and len(daten) < 5_000_000
            overlay.bild_daten = daten if ok else b""
            fertig(overlay.bild_daten or None)

        self._netz.anfrage("GET", overlay.vorschaubild, antwort, roh=True)

    def _noch_nicht_bereit(self, fertig) -> None:
        """Overlay wird noch von Uno gelesen: still ablehnen (die Oberfläche zeigt „Wird geladen …“)."""
        if fertig:
            QTimer.singleShot(0, lambda: fertig(False, ""))

    # ------------------------------------------------------------------
    @staticmethod
    def _overlay_befehl(overlay: Overlay, befehl: str, **mehr) -> dict:
        """Befehl über …/api für ein Overlay eines Projekts mit mehreren Overlays."""
        nachricht = {"command": befehl}
        if overlay.kennung:
            nachricht["id"] = overlay.kennung
        nachricht.update(mehr)
        return nachricht

    def _fehlertext(self, art: str) -> str:
        return {
            KEIN_INTERNET: self._texte.meldung_uno_kein_internet,
            NICHT_GEFUNDEN: self._texte.meldung_uno_adresse_unbekannt,
            UNBEKANNTER_BEFEHL: self._texte.meldung_uno_befehl_unbekannt,
        }.get(art, self._texte.meldung_uno_fehler)

    def _basis(self, projekt: UnoProjekt) -> str:
        return f"{str(self._E.basisadresse).rstrip('/')}/apiv2/controlapps/{projekt.token}"

    def _befehl(self, projekt: UnoProjekt, befehl: dict, rueckruf) -> None:
        """Befehl über …/api. rueckruf(ok, payload, fehlertext_fuer_menschen, fehlerart)."""
        def fertig(code, daten, netzfehler):
            if uno_ok(code, daten):
                rueckruf(True, daten.get("payload") if isinstance(daten, dict) else daten, "", "")
                return
            art = fehlerart(code, daten)
            # Den geheimen Teil der Adresse nie ins Protokoll schreiben
            log.info("Uno-Befehl %s abgelehnt (HTTP %s, %s): %.200s %s",
                     befehl.get("command"), code, art, daten, netzfehler)
            rueckruf(False, None, self._fehlertext(art), art)

        self._netz.anfrage("PUT", self._basis(projekt) + "/api", fertig, json_daten=befehl)

    def _singular(self, projekt: UnoProjekt, methode: str, pfad: str, daten, rueckruf) -> None:
        """Anfrage an die Singular-Schnittstelle (Einzel-Unos). rueckruf(ok, antwort, fehlertext, fehlerart)."""
        def fertig(code, antwort, netzfehler):
            if 200 <= code < 300 and not (isinstance(antwort, dict) and "error" in antwort):
                rueckruf(True, antwort, "", "")
                return
            art = fehlerart(code, antwort)
            log.info("Uno %s %s abgelehnt (HTTP %s, %s): %.200s %s", methode, pfad or "/", code, art, antwort,
                     netzfehler)
            rueckruf(False, None, self._fehlertext(art), art)

        self._netz.anfrage(methode, self._basis(projekt) + pfad, fertig, json_daten=daten)

    def beenden(self) -> None:
        self._abfrage.stop()
        self._netz.alle_abbrechen()
        self._hintergrund.beenden()
