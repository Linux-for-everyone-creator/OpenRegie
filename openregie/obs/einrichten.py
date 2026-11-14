"""Knopf „Countdown in OBS einrichten“.

Legt in der gerade gesendeten Szene eine Browserquelle mit der Countdown-Seite
an (oder repariert eine vorhandene). Die Quelle ist so groß wie das ganze Bild
und liegt genau darauf – die Position des Countdowns kommt aus
einstellungen.toml, damit niemand in OBS etwas verschieben muss.

Die Schritte laufen nacheinander; jeder wartet auf die Antwort von OBS.
"""

from __future__ import annotations

import logging
from typing import Callable

from .verbindung import ZEITLIMIT_TEXT, ObsVerbindung

log = logging.getLogger("openregie.einrichten")

BROWSER_ART = "browser_source"
CODE_NICHT_GEFUNDEN = "600"  # OBS: „ResourceNotFound“


def _einfacher_grund(technisch: str, texte) -> str:
    if not technisch:
        return ZEITLIMIT_TEXT
    if technisch in (ZEITLIMIT_TEXT, texte.meldung_nicht_verbunden):  # schon verständlich
        return technisch
    # Fehlertexte von OBS selbst sind englisch und technisch – nur als Zusatz in Klammern
    return f"OBS hat die Anfrage abgelehnt ({technisch})."


class CountdownEinrichten:
    """Ein Durchlauf. fertig(erfolg, meldung) wird genau einmal aufgerufen."""

    def __init__(self, verbindung: ObsVerbindung, quellenname: str, adresse: str, texte,
                 fertig: Callable[[bool, str], None]):
        self.v = verbindung
        self.name = quellenname
        self.adresse = adresse
        self.texte = texte
        self._fertig = fertig
        self._erledigt = False
        self.breite = 1920
        self.hoehe = 1080
        self.szene = ""

    def los(self) -> None:
        if not self.v.verbunden:
            self._ende(False, self.texte.meldung_nicht_verbunden)
            return
        self.v.anfrage("GetInputKindList", {"unversioned": True}, self._arten)

    # --- Schritte ---------------------------------------------------------
    def _arten(self, ok, daten, fehler):
        if not ok:
            return self._fehler(fehler)
        if BROWSER_ART not in (daten.get("inputKinds") or []):
            return self._ende(False, self.texte.meldung_einrichten_kein_browser)
        self.v.anfrage("GetVideoSettings", None, self._bildgroesse)

    def _bildgroesse(self, ok, daten, fehler):
        if not ok:
            return self._fehler(fehler)
        self.breite = int(daten.get("baseWidth") or 1920)
        self.hoehe = int(daten.get("baseHeight") or 1080)
        self.v.anfrage("GetCurrentProgramScene", None, self._szene)

    def _szene(self, ok, daten, fehler):
        if not ok:
            return self._fehler(fehler)
        self.szene = daten.get("sceneName") or daten.get("currentProgramSceneName") or ""
        if not self.szene:
            return self._fehler("")
        self.v.anfrage("GetInputSettings", {"inputName": self.name}, self._quelle_vorhanden)

    def _quellen_einstellungen(self) -> dict:
        return {
            "url": self.adresse,
            "width": self.breite,
            "height": self.hoehe,
            "is_local_file": False,
            "reroute_audio": False,
            "shutdown": False,
        }

    def _quelle_vorhanden(self, ok, daten, fehler):
        if ok:
            if daten.get("inputKind") not in (BROWSER_ART, None):
                return self._ende(False, self.texte.meldung_einrichten_fehler.format(
                    grund=f"Es gibt in OBS schon eine andere Quelle mit dem Namen „{self.name}“."))
            self.v.anfrage("SetInputSettings",
                           {"inputName": self.name, "inputSettings": self._quellen_einstellungen()},
                           self._aktualisiert)
        else:
            self.v.anfrage("CreateInput", {
                "sceneName": self.szene,
                "inputName": self.name,
                "inputKind": BROWSER_ART,
                "inputSettings": self._quellen_einstellungen(),
                "sceneItemEnabled": True,
            }, self._angelegt)

    def _angelegt(self, ok, daten, fehler):
        if not ok:
            return self._fehler(fehler)
        kennung = daten.get("sceneItemId")
        if kennung is None:
            return self._fehler("")
        self._lage_setzen(int(kennung))

    def _aktualisiert(self, ok, _daten, fehler):
        if not ok:
            return self._fehler(fehler)
        # Seite neu laden lassen, damit neue Einstellungen sofort wirken
        self.v.anfrage("PressInputPropertiesButton", {"inputName": self.name, "propertyName": "refreshnocache"})
        self.v.anfrage("GetSceneItemId", {"sceneName": self.szene, "sourceName": self.name}, self._in_szene)

    def _in_szene(self, ok, daten, fehler):
        if ok and daten.get("sceneItemId") is not None:
            kennung = int(daten["sceneItemId"])
            self.v.anfrage("SetSceneItemEnabled",
                           {"sceneName": self.szene, "sceneItemId": kennung, "sceneItemEnabled": True},
                           lambda ok2, _d, f2: self._lage_setzen(kennung) if ok2 else self._fehler(f2))
        else:
            self.v.anfrage("CreateSceneItem",
                           {"sceneName": self.szene, "sourceName": self.name, "sceneItemEnabled": True},
                           self._angelegt)

    def _lage_setzen(self, kennung: int):
        """Quelle genau aufs ganze Bild legen (kein Verschieben nötig)."""
        self.v.anfrage("SetSceneItemTransform", {
            "sceneName": self.szene,
            "sceneItemId": kennung,
            "sceneItemTransform": {
                "positionX": 0.0, "positionY": 0.0,
                "scaleX": 1.0, "scaleY": 1.0, "rotation": 0.0,
                "alignment": 5,  # oben links
                "boundsType": "OBS_BOUNDS_NONE",
                "cropLeft": 0, "cropRight": 0, "cropTop": 0, "cropBottom": 0,
            },
        }, self._fertig_gelegt)

    def _fertig_gelegt(self, ok, _daten, fehler):
        if not ok:
            return self._fehler(fehler)
        self._ende(True, self.texte.meldung_einrichten_ok.format(szene=self.szene))

    # --- Abschluss --------------------------------------------------------
    def _fehler(self, technisch: str):
        log.warning("Countdown einrichten fehlgeschlagen: %s", technisch)
        self._ende(False, self.texte.meldung_einrichten_fehler.format(grund=_einfacher_grund(technisch, self.texte)))

    def _ende(self, erfolg: bool, meldung: str):
        if self._erledigt:
            return
        self._erledigt = True
        self._fertig(erfolg, meldung)
