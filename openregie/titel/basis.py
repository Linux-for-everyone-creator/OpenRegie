"""Grundbaustein für alle OpenRegie-Titel.

Ein Titel ist etwas, das OpenRegie im Stream anzeigt: Countdown, später Uhr,
Bauchbinde, News-Ticker …  Jeder Titel hat einen „Antrieb“:

  lokal – OpenRegie erzeugt die Grafik selbst (lokale Webseite als OBS-Browserquelle)
  uno   – Overlays.uno erzeugt die Grafik, OpenRegie schickt nur Texte und
          Ein-/Ausblenden über die Uno-API (ab Build 1.1)
"""

from __future__ import annotations

from enum import Enum


class Antrieb(Enum):
    LOKAL = "lokal"
    UNO = "uno"


class Titel:
    def __init__(self, kennung: str, name: str, antrieb: Antrieb):
        self.kennung = kennung  # fester, technischer Name, z. B. "countdown"
        self.name = name  # Anzeigename in der Titelliste
        self.antrieb = antrieb

    # Ab Build 1.1 (Tally-Licht, Uno): ob der Titel gerade im Stream sichtbar ist.
    def ist_auf_sendung(self) -> bool | None:
        return None
