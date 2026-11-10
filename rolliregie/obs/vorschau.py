"""Live-Vorschau: holt regelmäßig ein Standbild der gesendeten Szene von OBS.

Es ist immer höchstens eine Bild-Anfrage unterwegs. Ist OBS mal langsam,
staut sich nichts auf – die Vorschau wird dann nur kurz weniger flüssig.
"""

from __future__ import annotations

import base64
import logging

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QImage

from .verbindung import ObsVerbindung

log = logging.getLogger("rolliregie.vorschau")


def bild_aus_daten(bilddaten: str) -> QImage | None:
    """OBS schickt „data:image/jpg;base64,....“ – daraus ein Bild machen."""
    if not bilddaten:
        return None
    _, _, roh = bilddaten.partition(",")
    try:
        inhalt = base64.b64decode(roh or bilddaten, validate=False)
    except (ValueError, TypeError):
        return None
    bild = QImage()
    if not bild.loadFromData(inhalt):
        return None
    return bild


class Vorschau(QObject):
    neues_bild = Signal(QImage)

    def __init__(self, verbindung: ObsVerbindung, vorschau_einstellungen, parent=None):
        super().__init__(parent)
        self._verbindung = verbindung
        self._breite = int(vorschau_einstellungen.bildbreite)
        self._qualitaet = max(1, min(100, int(vorschau_einstellungen.qualitaet)))
        fps = max(1, min(30, int(vorschau_einstellungen.bilder_pro_sekunde)))
        self._wartet = False
        self._fehler_in_folge = 0
        self.bilder_erhalten = 0

        self._timer = QTimer(self)
        self._timer.setInterval(int(1000 / fps))
        self._timer.timeout.connect(self._bild_holen)
        self._timer.start()

    def anhalten(self) -> None:
        self._timer.stop()

    def _bild_holen(self) -> None:
        if self._wartet or not self._verbindung.verbunden:
            return
        szene = self._verbindung.szene
        if not szene:
            return
        self._wartet = True
        self._verbindung.anfrage(
            "GetSourceScreenshot",
            {
                "sourceName": szene,
                "imageFormat": "jpg",
                "imageWidth": self._breite,
                "imageCompressionQuality": self._qualitaet,
            },
            self._antwort,
        )

    def _antwort(self, ok: bool, daten: dict, fehler: str) -> None:
        self._wartet = False
        if not ok:
            self._fehler_in_folge += 1
            # z. B. Szene wurde umbenannt: aktuelle Szene neu erfragen
            if self._fehler_in_folge in (3, 30) or self._fehler_in_folge % 100 == 0:
                log.warning("Vorschaubild fehlgeschlagen (%sx): %s", self._fehler_in_folge, fehler)
                self._verbindung.szene_neu_abfragen()
            return
        bild = bild_aus_daten(daten.get("imageData", ""))
        if bild is None:
            self._fehler_in_folge += 1
            return
        self._fehler_in_folge = 0
        self.bilder_erhalten += 1
        self.neues_bild.emit(bild)
