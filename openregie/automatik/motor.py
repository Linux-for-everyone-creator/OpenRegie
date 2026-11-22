"""Die Automatik: führt die Wenn-dann-Regeln aus und verwaltet den Zeitplan.

Sparsam: Die Automatik läuft nur, wenn mindestens eine Regel aktiv ist. Dann – und nur dann – richtet sie
genau die Auslöser ein, die aktive Regeln brauchen. Ohne aktive Regel hängt nichts an OBS, es läuft kein
Takt, keine Pegelmessung und keine Abfrage (`laeuft` ist dann False, `eingerichtet` leer).

Regeln und Zeitplan liegen in ~/.local/share/openregie/automatik.json (nur für den eigenen Benutzer
lesbar). Lesen und Schreiben passiert im Hintergrund – das Regiepult friert nie ein.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from ..hintergrund import Hintergrund
from . import register
from .zeitplan import Termin, naechster

log = logging.getLogger("openregie.automatik")

SPERRE_SEKUNDEN = 2.0  # eine Regel löst höchstens alle 2 s aus (schützt vor Ping-Pong zwischen Regeln)
WECKER_HOECHSTENS_MS = 3600 * 1000  # spätestens nach einer Stunde neu rechnen (Ruhezustand, Uhr verstellt)


def standard_datei() -> Path:
    basis = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    return basis / "openregie" / "automatik.json"


@dataclass
class Regel:
    wenn: str
    dann: str
    wenn_wert: str | None = None
    dann_wert: str | None = None
    aktiv: bool = True
    kennung: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def als_dict(self) -> dict:
        return {"id": self.kennung, "aktiv": self.aktiv, "wenn": {"art": self.wenn, "wert": self.wenn_wert},
                "dann": {"art": self.dann, "wert": self.dann_wert}}

    @staticmethod
    def aus_dict(d: dict) -> "Regel | None":
        try:
            return Regel(wenn=str(d["wenn"]["art"]), dann=str(d["dann"]["art"]),
                         wenn_wert=d["wenn"].get("wert"), dann_wert=d["dann"].get("wert"),
                         aktiv=bool(d.get("aktiv", True)), kennung=str(d.get("id") or uuid.uuid4().hex[:12]))
        except (KeyError, TypeError, AttributeError):
            return None

    @property
    def gueltig(self) -> bool:
        a, b = register.AUSLOESER.get(self.wenn), register.AKTIONEN.get(self.dann)
        if a is None or b is None:
            return False
        return (not a.wahl or bool(self.wenn_wert)) and (not b.wahl or bool(self.dann_wert))


def _datei_lesen(pfad: Path) -> dict:
    if not pfad.exists():
        return {}
    return json.loads(pfad.read_text(encoding="utf-8"))


def _datei_schreiben(pfad: Path, daten: dict) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    neu = pfad.with_suffix(".neu")
    neu.write_text(json.dumps(daten, ensure_ascii=False, indent=2), encoding="utf-8")
    neu.chmod(0o600)
    neu.replace(pfad)  # erst ganz schreiben, dann tauschen: nie eine halbe Datei


class Automatik(QObject):
    geaendert = Signal()  # Regeln oder Zeitplan haben sich geändert
    ausgeloest = Signal(str)  # Kennung der Regel, die gerade ausgelöst hat
    meldung = Signal(str, bool)  # (Text, ist_fehler) – z. B. „Konnte nicht speichern“

    def __init__(self, texte, verbindung, quellen, uno, parent=None, datei: Path | None = None,
                 hintergrund: Hintergrund | None = None):
        super().__init__(parent)
        self.t = texte
        self._v = verbindung
        self._quellen = quellen
        self._uno = uno
        self._datei = datei or standard_datei()
        self._hintergrund = hintergrund or Hintergrund(self, name="openregie-automatik")
        self.regeln: list[Regel] = []
        self.zeitplan: list[Termin] = []
        self.geladen = False
        self.eingerichtet: dict[str, register.Abbauen] = {}  # Kennung der Regel → abbauen
        self._zuletzt: dict[str, float] = {}
        self.ausloesungen = 0  # für Tests

        # Was Auslöser benutzen dürfen (Signale, die OBS ohnehin schickt)
        self.sendung_geaendert = verbindung.sendung_geaendert
        self.szene_geaendert = verbindung.szene_geaendert

    # ------------------------------------------------------------------
    @property
    def laeuft(self) -> bool:
        return bool(self.eingerichtet)

    def aktive_regeln(self) -> list[Regel]:
        return [r for r in self.regeln if r.aktiv and r.gueltig]

    def regel(self, kennung: str) -> Regel | None:
        return next((r for r in self.regeln if r.kennung == kennung), None)

    # --- Laden / Speichern (im Hintergrund) -----------------------------
    def laden(self) -> None:
        pfad = self._datei

        def fertig(daten, fehler):
            if fehler is not None:
                log.error("Automatik nicht lesbar (%s): %s", pfad, fehler)
                self.meldung.emit(self.t.meldung_automatik_lesen, True)
                daten = {}
            self.regeln = [r for r in (Regel.aus_dict(d) for d in (daten or {}).get("regeln", [])) if r]
            self.zeitplan = sorted({t for t in (Termin.aus_dict(d) for d in (daten or {}).get("zeitplan", [])) if t})
            self.geladen = True
            log.info("Automatik geladen: %d Regel(n), %d aktiv, %d Termin(e)", len(self.regeln),
                     len(self.aktive_regeln()), len(self.zeitplan))
            self._neu_einrichten()
            self.geaendert.emit()

        self._hintergrund.ausfuehren(lambda: _datei_lesen(pfad), fertig)

    def _speichern(self) -> None:
        daten = {"version": 1, "regeln": [r.als_dict() for r in self.regeln],
                 "zeitplan": [t.als_dict() for t in self.zeitplan]}
        pfad = self._datei

        def fertig(_e, fehler):
            if fehler is not None:
                log.error("Automatik nicht gespeichert: %s", fehler)
                self.meldung.emit(self.t.meldung_automatik_speichern, True)

        self._hintergrund.ausfuehren(lambda: _datei_schreiben(pfad, daten), fertig)

    # --- Bearbeiten -----------------------------------------------------
    def regel_speichern(self, regel: Regel) -> None:
        """Neue Regel anfügen oder eine vorhandene (gleiche Kennung) ersetzen."""
        for i, r in enumerate(self.regeln):
            if r.kennung == regel.kennung:
                self.regeln[i] = replace(regel)
                break
        else:
            self.regeln.append(replace(regel))
        self._geaendert()

    def regel_loeschen(self, kennung: str) -> None:
        self.regeln = [r for r in self.regeln if r.kennung != kennung]
        self._geaendert()

    def regel_aktiv(self, kennung: str, aktiv: bool) -> None:
        r = self.regel(kennung)
        if r is not None and r.aktiv != aktiv:
            r.aktiv = aktiv
            self._geaendert()

    def zeitplan_setzen(self, termine) -> None:
        self.zeitplan = sorted(set(termine))
        self._geaendert()

    def _geaendert(self) -> None:
        self._speichern()
        self._neu_einrichten()
        self.geaendert.emit()

    def naechster_termin(self, jetzt: datetime | None = None) -> datetime | None:
        return naechster(self.zeitplan, jetzt)

    # --- Auslöser einrichten / abbauen ------------------------------------
    def _neu_einrichten(self) -> None:
        for kennung, abbauen in list(self.eingerichtet.items()):
            try:
                abbauen()
            except Exception:
                log.exception("Auslöser nicht sauber abgebaut")
        self.eingerichtet.clear()
        for r in self.aktive_regeln():
            a = register.AUSLOESER[r.wenn]
            try:
                self.eingerichtet[r.kennung] = a.einrichten(self, r.wenn_wert, lambda k=r.kennung: self._ausloesen(k))
            except Exception:
                log.exception("Auslöser „%s“ ließ sich nicht einrichten", r.wenn)
        log.info("Automatik %s (%d aktive Regel(n))", "läuft" if self.laeuft else "ruht", len(self.eingerichtet))

    def beenden(self) -> None:
        for abbauen in self.eingerichtet.values():
            try:
                abbauen()
            except Exception:
                pass
        self.eingerichtet.clear()
        self._hintergrund.beenden()
        # Beim Schließen: was noch gespeichert werden soll, darf fertig werden (höchstens 2 s)
        thread = getattr(self._hintergrund, "_thread", None)
        if thread is not None and thread.is_alive():
            thread.join(2)

    def _ausloesen(self, kennung: str) -> None:
        r = self.regel(kennung)
        if r is None or not r.aktiv:
            return
        jetzt = time.monotonic()
        if jetzt - self._zuletzt.get(kennung, -1e9) < SPERRE_SEKUNDEN:
            log.info("Regel %s: zu schnell hintereinander – übersprungen", kennung)
            return
        self._zuletzt[kennung] = jetzt
        self.ausloesungen += 1
        log.info("Regel ausgelöst: wenn %s(%s) → dann %s(%s)", r.wenn, r.wenn_wert, r.dann, r.dann_wert)
        try:
            register.AKTIONEN[r.dann].ausfuehren(self, r.dann_wert)
        except Exception:
            log.exception("Aktion „%s“ fehlgeschlagen", r.dann)
        self.ausgeloest.emit(kennung)

    # --- Was Aktionen tun können (alles über die Motor-Schicht) -------------
    def shot_live(self, name: str | None) -> None:
        if name:
            self._quellen.live_schalten(name)

    def overlay_sichtbar(self, schluessel: str | None, sichtbar: bool) -> None:
        overlay = self._uno.overlays.get(schluessel) if schluessel else None
        if overlay is None:
            log.warning("Overlay %s gibt es nicht (mehr)", schluessel)
            return
        self._uno.sichtbar_setzen(overlay, sichtbar)

    def ton_stumm(self, name: str | None, stumm: bool) -> None:
        if name:
            self._quellen.ton_stumm(name, stumm)

    def zeitplan_wecker(self, ausloesen) -> register.Abbauen:
        """EIN Wecker auf den nächsten Termin. Kein Takt: er klingelt nur zum Termin (bzw. stündlich zum
        Nachrechnen, falls der PC geschlafen hat)."""
        wecker = QTimer(self)
        wecker.setSingleShot(True)
        ziel = {"zeit": None}

        def stellen():
            ziel["zeit"] = self.naechster_termin()
            if ziel["zeit"] is None:
                return
            ms = int((ziel["zeit"] - datetime.now()).total_seconds() * 1000)
            wecker.start(max(0, min(ms, WECKER_HOECHSTENS_MS)))

        def klingelt():
            if ziel["zeit"] is not None and datetime.now() >= ziel["zeit"]:
                ausloesen()
            stellen()

        wecker.timeout.connect(klingelt)
        stellen()

        def abbauen():
            wecker.stop()
            wecker.deleteLater()
        return abbauen

    # --- Auswahllisten fürs Fenster (nur, wenn das Fenster offen ist) --------
    def wahl_moeglichkeiten(self, art: str, fertig) -> None:
        """fertig([(wert, text), …]) – Shots, Overlays oder Tonquellen."""
        if art == register.SHOT:
            namen = [s.name for s in self._quellen.shots]
            if namen or not self._quellen.verbunden:
                QTimer.singleShot(0, lambda: fertig([(n, n) for n in namen]))
            else:
                self._quellen.shot_namen(lambda liste: fertig([(n, n) for n in liste]))
        elif art == register.OVERLAY:
            liste = [(s, o.name) for s, o in self._uno.overlays.items()]
            QTimer.singleShot(0, lambda: fertig(liste))
        elif art == register.TON:
            self._quellen.tonquellen(lambda liste: fertig([(n, n) for n in liste]))
        else:
            QTimer.singleShot(0, lambda: fertig([]))
