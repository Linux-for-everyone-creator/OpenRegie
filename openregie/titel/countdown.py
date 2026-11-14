"""Der Countdown – die reine Rechenlogik, ohne Fenster.

Der Countdown wird aus dem Fenster bedient und gleichzeitig von der
Countdown-Webseite (eigener Thread) gelesen, deshalb ist alles mit einem
Schloss (Lock) geschützt.
"""

from __future__ import annotations

import math
import threading
import time
from enum import Enum
from typing import Callable

from .basis import Antrieb, Titel


class Zustand(Enum):
    BEREIT = "bereit"
    LAEUFT = "laeuft"
    PAUSIERT = "pausiert"
    ABGELAUFEN = "abgelaufen"


def als_text(sekunden: float) -> str:
    """Sekunden als MM:SS. Es wird aufgerundet: 4,2 s Rest zeigen „00:05“,
    damit „00:00“ erst erscheint, wenn die Zeit wirklich vorbei ist."""
    ganze = max(0, math.ceil(round(sekunden, 6)))
    minuten, sek = divmod(ganze, 60)
    return f"{minuten:02d}:{sek:02d}"


class Countdown(Titel):
    def __init__(
        self,
        name: str,
        startdauer: int,
        hoechstdauer: int,
        uhr: Callable[[], float] = time.monotonic,
    ):
        super().__init__("countdown", name, Antrieb.LOKAL)
        self._uhr = uhr
        self._schloss = threading.RLock()
        self.hoechstdauer = int(hoechstdauer)
        self._dauer = self._begrenzen(startdauer)
        self._zustand = Zustand.BEREIT
        self._rest = float(self._dauer)  # Rest, als zuletzt angehalten/gesetzt wurde
        self._gestartet_um: float | None = None  # Uhrzeit, seit der er läuft

    # --- Hilfen -----------------------------------------------------------
    def _begrenzen(self, sekunden: float) -> int:
        return int(min(max(0, sekunden), self.hoechstdauer))

    def _aktueller_rest(self) -> float:
        if self._zustand is Zustand.LAEUFT:
            vergangen = self._uhr() - self._gestartet_um
            return max(0.0, self._rest - vergangen)
        return self._rest

    def _ablauf_pruefen(self) -> None:
        if self._zustand is Zustand.LAEUFT and self._aktueller_rest() <= 0:
            self._zustand = Zustand.ABGELAUFEN
            self._rest = 0.0
            self._gestartet_um = None

    # --- Abfragen ---------------------------------------------------------
    @property
    def dauer(self) -> int:
        with self._schloss:
            return self._dauer

    @property
    def zustand(self) -> Zustand:
        with self._schloss:
            self._ablauf_pruefen()
            return self._zustand

    def rest(self) -> float:
        with self._schloss:
            self._ablauf_pruefen()
            return self._aktueller_rest()

    def text(self) -> str:
        return als_text(self.rest())

    def momentaufnahme(self) -> dict:
        """Alles auf einmal (für die Webseite), in einem Zug gelesen."""
        with self._schloss:
            self._ablauf_pruefen()
            rest = self._aktueller_rest()
            return {"text": als_text(rest), "zustand": self._zustand.value, "rest": rest}

    # --- Bedienung --------------------------------------------------------
    def aendern(self, sekunden: int) -> None:
        """Plus/Minus. Steht der Countdown, ändert sich die Dauer.
        Läuft oder pausiert er, ändert sich die restliche Zeit."""
        with self._schloss:
            self._ablauf_pruefen()
            if self._zustand in (Zustand.BEREIT, Zustand.ABGELAUFEN):
                self._dauer = self._begrenzen(self._dauer + sekunden)
                self._rest = float(self._dauer)
                self._zustand = Zustand.BEREIT
            else:
                neu = min(max(0.0, self._aktueller_rest() + sekunden), self.hoechstdauer)
                self._rest = neu
                if self._zustand is Zustand.LAEUFT:
                    self._gestartet_um = self._uhr()
                    if neu <= 0:
                        self._ablauf_pruefen()
                # Pausiert auf 0 gesetzt: bleibt pausiert bei 00:00, Start beendet ihn.

    def start(self) -> None:
        with self._schloss:
            self._ablauf_pruefen()
            if self._zustand is Zustand.LAEUFT:
                return
            if self._zustand is Zustand.ABGELAUFEN:
                self._rest = float(self._dauer)
            if self._rest <= 0:
                if self._zustand is Zustand.PAUSIERT:
                    self._zustand = Zustand.ABGELAUFEN
                return  # Dauer 0: nichts zu zählen
            self._zustand = Zustand.LAEUFT
            self._gestartet_um = self._uhr()

    def pause(self) -> None:
        with self._schloss:
            self._ablauf_pruefen()
            if self._zustand is Zustand.LAEUFT:
                self._rest = self._aktueller_rest()
                self._zustand = Zustand.PAUSIERT
                self._gestartet_um = None

    def stopp(self) -> None:
        """Zurück auf die eingestellte Dauer."""
        with self._schloss:
            self._zustand = Zustand.BEREIT
            self._rest = float(self._dauer)
            self._gestartet_um = None
