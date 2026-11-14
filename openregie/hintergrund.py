"""Arbeit im Hintergrund – damit das Regiepult NIE einfriert.

Grundregel: Alles, was warten kann (Passwortspeicher, Dateien, Programme), läuft nicht im
Haupt-Thread der Oberfläche. Internet-Anfragen laufen ohnehin ohne Warten (siehe netz.py).

Die Arbeit läuft nacheinander in EINEM Hintergrund-Thread (so bleibt die Reihenfolge, z. B.
beim Speichern, immer erhalten). Das Ergebnis kommt im Haupt-Thread zurück:
    hintergrund.ausfuehren(lambda: speicher.lesen("uno"), fertig)   # fertig(ergebnis, fehler)
"""

from __future__ import annotations

import logging
import queue
import threading
from typing import Callable

from PySide6.QtCore import QObject, Signal

log = logging.getLogger("openregie.hintergrund")


class Hintergrund(QObject):
    _fertig = Signal(object, object, object)  # (rueckruf, ergebnis, fehler)

    def __init__(self, parent=None, name: str = "openregie-hintergrund"):
        super().__init__(parent)
        self._auftraege: queue.Queue = queue.Queue()
        self._fertig.connect(self._ausliefern)  # kommt automatisch im Haupt-Thread an
        self._thread = threading.Thread(target=self._arbeiten, name=name, daemon=True)
        self._thread.start()
        self.offen = 0

    def ausfuehren(self, arbeit: Callable[[], object], fertig: Callable[[object, Exception | None], None] | None = None):
        self.offen += 1
        self._auftraege.put((arbeit, fertig))

    def _arbeiten(self) -> None:
        while True:
            auftrag = self._auftraege.get()
            if auftrag is None:
                return
            arbeit, fertig = auftrag
            try:
                ergebnis, fehler = arbeit(), None
            except Exception as e:  # Fehler gehören zum Ergebnis, nicht in den Absturz
                ergebnis, fehler = None, e
            try:
                self._fertig.emit(fertig, ergebnis, fehler)
            except RuntimeError:
                return  # Programm wird gerade beendet

    def _ausliefern(self, fertig, ergebnis, fehler) -> None:
        self.offen -= 1
        if fertig is None:
            if fehler is not None:
                log.error("Hintergrund-Arbeit fehlgeschlagen: %s", fehler)
            return
        try:
            fertig(ergebnis, fehler)
        except Exception:
            log.exception("Fehler beim Verarbeiten eines Hintergrund-Ergebnisses")

    def beenden(self) -> None:
        self._auftraege.put(None)
