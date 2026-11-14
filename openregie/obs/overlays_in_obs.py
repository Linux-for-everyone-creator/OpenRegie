"""Uno-Overlays in OBS: anlegen, ganz nach oben legen, alte Quellen aufräumen.

Damit die Overlays im Stream zu sehen sind, braucht OBS eine Browserquelle mit der
Ausgabe-Adresse des Uno-Projekts. OpenRegie sorgt automatisch dafür:

  1. Die alte, leere Quelle „Rolliregie Countdown“ (eigener Countdown aus Build 1.0,
     Adresse http://127.0.0.1:8787/countdown gibt es nicht mehr) wird entfernt.
  2. Für jedes Uno-Projekt gibt es eine Browserquelle „Uno: <Name>“ (so groß wie das Bild)
     – in JEDER Szene ([obs] uno_in_jede_szene).
  3. Uno-Quellen liegen in jeder Szene immer ganz OBEN ([obs] overlays_immer_oben), sonst
     verdeckt z. B. die Bildschirmaufnahme den Countdown. Schiebt man in OBS etwas darüber
     oder fügt etwas hinzu, rückt OpenRegie die Overlays sofort wieder nach oben.

Erkannt werden Uno-Quellen an ihrer Adresse (…singular.live/output/… bzw. …overlays.uno/output…),
auch wenn sie von Hand angelegt wurden.
"""

from __future__ import annotations

import logging
import re

from PySide6.QtCore import QObject, QTimer

from ..uno.verwaltung import UnoVerwaltung
from .verbindung import ObsVerbindung, Status

log = logging.getLogger("openregie.obs_overlays")

BROWSER = "browser_source"
_AUSGABE = re.compile(r"(?:singular\.live|overlays\.uno)/output/([^/?#\s]+)", re.IGNORECASE)
ALTE_NAMEN = ("Rolliregie Countdown", "OpenRegie Countdown")
_ALTE_ADRESSE = re.compile(r"^https?://(?:127\.0\.0\.1|localhost):\d+/countdown\b", re.IGNORECASE)


def ausgabe_kennung(url: str) -> str | None:
    """Kennung einer Uno-Ausgabe aus ihrer Adresse (None = keine Uno-Ausgabe)."""
    treffer = _AUSGABE.search(url or "")
    return treffer.group(1) if treffer else None


def ist_alter_countdown(name: str, url: str) -> bool:
    """Nur die alte Countdown-Seite aus Build 1.0 – sonst nichts."""
    return bool(_ALTE_ADRESSE.match(url or "")) and (name in ALTE_NAMEN or "countdown" in name.lower())


def neue_reihenfolge(eintraege: list[dict], oben: set[str]) -> list[dict]:
    """Szenenelemente (unten → oben) so ordnen, dass die mit Namen in `oben` ganz oben liegen.
    Ihre Reihenfolge untereinander bleibt, genauso die der anderen."""
    sortiert = sorted(eintraege, key=lambda e: e.get("sceneItemIndex", 0))
    return [e for e in sortiert if e.get("sourceName") not in oben] + \
           [e for e in sortiert if e.get("sourceName") in oben]


class ObsOverlays(QObject):
    def __init__(self, obs_einstellungen, verbindung: ObsVerbindung, uno: UnoVerwaltung, parent=None):
        super().__init__(parent)
        self._E = obs_einstellungen
        self.v = verbindung
        self.uno = uno
        self.uno_namen: set[str] = set()  # Namen der Uno-Quellen in OBS (zuletzt gesehen)
        self._laeuft = False
        self._nochmal = None  # "ganz" oder "stapeln", wenn während eines Durchlaufs etwas passierte
        self.durchlaeufe = 0  # für Tests

        # Viele Ereignisse kurz hintereinander (z. B. beim Umsortieren) → ein Durchlauf
        self._sammeln = QTimer(self)
        self._sammeln.setSingleShot(True)
        self._sammeln.setInterval(300)
        self._sammeln.timeout.connect(self._los)
        self._art = None

        verbindung.status_geaendert.connect(self._status)
        verbindung.ereignis.connect(self._ereignis)
        uno.ausgaben_geaendert.connect(lambda: self.anstossen("ganz"))

    # ------------------------------------------------------------------
    def _status(self, status: Status, _meldung: str) -> None:
        if status is Status.VERBUNDEN:
            self.anstossen("ganz")

    def _ereignis(self, typ: str, _daten: dict) -> None:
        if typ in ("SceneCreated", "SceneItemCreated", "CurrentSceneCollectionChanged", "InputCreated"):
            self.anstossen("ganz")
        elif typ in ("SceneItemListReindexed",):
            self.anstossen("stapeln")

    def anstossen(self, art: str = "ganz") -> None:
        if not self.v.verbunden:
            return
        if self._art != "ganz":
            self._art = art
        self._sammeln.start()

    def _los(self) -> None:
        art, self._art = self._art or "ganz", None
        if self._laeuft:
            self._nochmal = "ganz" if "ganz" in (art, self._nochmal) else "stapeln"
            return
        self._laeuft = True
        self.durchlaeufe += 1
        self._ablauf(self._abgleich(nur_stapeln=(art == "stapeln")))

    # ------------------------------------------------------------------
    #  Ablauf: nacheinander Anfragen an OBS (jede wartet auf die Antwort, ohne die Oberfläche
    #  anzuhalten). Geschrieben als Generator: yield (Anfrage, Daten) → bekommt (ok, Antwort).
    # ------------------------------------------------------------------
    def _ablauf(self, schritte) -> None:
        def weiter(ergebnis=None):
            try:
                typ, daten = schritte.send(ergebnis)
            except StopIteration:
                self._fertig()
                return
            except Exception:
                log.exception("Fehler beim Abgleich der Overlays in OBS")
                self._fertig()
                return
            self.v.anfrage(typ, daten, lambda ok, antwort, fehler: weiter((ok, antwort, fehler)))

        weiter(None)

    def _fertig(self) -> None:
        self._laeuft = False
        if self._nochmal:
            art, self._nochmal = self._nochmal, None
            self.anstossen(art)

    def _abgleich(self, nur_stapeln: bool):
        ok, d, _ = yield ("GetSceneList", None)
        if not ok:
            return
        szenen = [s.get("sceneName") for s in d.get("scenes", []) if s.get("sceneName")]

        if not nur_stapeln or not self.uno_namen:
            ok, d, _ = yield ("GetInputList", None)
            if not ok:
                return
            alle_namen = {e.get("inputName") for e in d.get("inputs", []) if e.get("inputName")}
            adressen: dict[str, str] = {}
            for eingang in d.get("inputs", []):
                name = eingang.get("inputName")
                if not name or eingang.get("inputKind") != BROWSER:
                    continue
                ok, e, _ = yield ("GetInputSettings", {"inputName": name})
                adressen[name] = str((e.get("inputSettings") or {}).get("url") or "") if ok else ""

            # 1. alte Countdown-Quelle aus Build 1.0 entfernen
            for name, url in list(adressen.items()):
                if ist_alter_countdown(name, url):
                    ok, _, fehler = yield ("RemoveInput", {"inputName": name})
                    log.info("Alte Quelle „%s“ entfernt: %s", name, "ok" if ok else fehler)
                    if ok:
                        del adressen[name]

            # 2. jedes Uno-Projekt als Browserquelle – in jeder Szene
            if bool(self._E.uno_in_jede_szene) and szenen:
                breite, hoehe = 1920, 1080
                ok, video, _ = yield ("GetVideoSettings", None)
                if ok:
                    breite, hoehe = int(video.get("baseWidth") or breite), int(video.get("baseHeight") or hoehe)
                for projektname, ausgabe in self.uno.ausgaben():
                    kennung = ausgabe_kennung(ausgabe)
                    name = next((n for n, u in adressen.items()
                                 if u == ausgabe or (kennung and ausgabe_kennung(u) == kennung)), None)
                    for szene in szenen:
                        ok, liste, _ = yield ("GetSceneItemList", {"sceneName": szene})
                        if not ok:
                            continue
                        if name and any(i.get("sourceName") == name for i in liste.get("sceneItems", [])):
                            continue
                        if name is None:
                            name = self._freier_name(f"Uno: {projektname}", alle_namen)
                            ok, _, fehler = yield ("CreateInput", {
                                "sceneName": szene, "inputName": name, "inputKind": BROWSER,
                                "inputSettings": {"url": ausgabe, "width": breite, "height": hoehe},
                                "sceneItemEnabled": True})
                            if not ok:
                                log.warning("Uno-Quelle „%s“ nicht angelegt: %s", name, fehler)
                                name = None
                                break
                            adressen[name] = ausgabe
                            alle_namen.add(name)
                            log.info("Uno-Quelle „%s“ in Szene „%s“ angelegt", name, szene)
                        else:
                            ok, _, fehler = yield ("CreateSceneItem", {
                                "sceneName": szene, "sourceName": name, "sceneItemEnabled": True})
                            log.info("Uno-Quelle „%s“ in Szene „%s“ eingefügt: %s", name, szene,
                                     "ok" if ok else fehler)

            self.uno_namen = {n for n, u in adressen.items() if ausgabe_kennung(u)}

        # 3. Uno-Quellen in jeder Szene ganz nach oben
        if bool(self._E.overlays_immer_oben) and self.uno_namen:
            for szene in szenen:
                ok, liste, _ = yield ("GetSceneItemList", {"sceneName": szene})
                if not ok:
                    continue
                jetzt = sorted(liste.get("sceneItems", []), key=lambda e: e.get("sceneItemIndex", 0))
                soll = neue_reihenfolge(jetzt, self.uno_namen)
                if [e.get("sceneItemId") for e in jetzt] == [e.get("sceneItemId") for e in soll]:
                    continue
                oben = [e for e in jetzt if e.get("sourceName") in self.uno_namen]
                log.info("Szene „%s“: %d Uno-Quelle(n) nach ganz oben", szene, len(oben))
                for e in oben:  # nacheinander nach oben: Reihenfolge untereinander bleibt
                    yield ("SetSceneItemIndex", {"sceneName": szene, "sceneItemId": e["sceneItemId"],
                                                 "sceneItemIndex": len(jetzt) - 1})

    @staticmethod
    def _freier_name(wunsch: str, vorhanden) -> str:
        name, nr = wunsch, 2
        while name in vorhanden:
            name, nr = f"{wunsch} ({nr})", nr + 1
        return name
