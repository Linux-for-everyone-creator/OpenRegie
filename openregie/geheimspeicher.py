"""Sicherer Speicher für Zugangsdaten (Uno-Adressen, Twitch-Anmeldung).

Die Daten kommen in den Passwortspeicher des Systems (KDE-Wallet / GNOME-Schlüsselbund
über die „Secret Service“-Schnittstelle, Werkzeug `secret-tool`). Sie liegen also
verschlüsselt und nie als lesbarer Text in einer Datei von OpenRegie.

Jeder Eintrag hat einen Schlüssel (z. B. "uno" oder "twitch") und einen Text-Wert
(bei uns JSON).
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess

log = logging.getLogger("openregie.geheim")

PROGRAMM = "openregie"
ZEITLIMIT = 30  # Sekunden – das System fragt evtl. nach dem Passwort für den Speicher


class SpeicherFehler(Exception):
    """Der Passwortspeicher ist nicht erreichbar."""


class Geheimspeicher:
    """Passwortspeicher des Systems über `secret-tool`."""

    def __init__(self, programm: str = PROGRAMM, werkzeug: str | None = None):
        self._programm = programm
        self._werkzeug = werkzeug or shutil.which("secret-tool")

    def _aufruf(self, argumente: list[str], eingabe: str | None = None) -> subprocess.CompletedProcess:
        if not self._werkzeug:
            raise SpeicherFehler("secret-tool fehlt")
        try:
            return subprocess.run([self._werkzeug, *argumente], input=eingabe, capture_output=True,
                                  text=True, timeout=ZEITLIMIT)
        except (OSError, subprocess.TimeoutExpired) as fehler:
            raise SpeicherFehler(str(fehler)) from None

    def _merkmale(self, schluessel: str) -> list[str]:
        return ["programm", self._programm, "eintrag", schluessel]

    def lesen(self, schluessel: str) -> str | None:
        ergebnis = self._aufruf(["lookup", *self._merkmale(schluessel)])
        if ergebnis.returncode != 0:
            # 1 ohne Fehlertext = es gibt den Eintrag einfach noch nicht
            if ergebnis.stderr.strip():
                raise SpeicherFehler(ergebnis.stderr.strip())
            return None
        return ergebnis.stdout

    def schreiben(self, schluessel: str, wert: str) -> None:
        bezeichnung = f"OpenRegie – {schluessel}"
        ergebnis = self._aufruf(["store", "--label", bezeichnung, *self._merkmale(schluessel)], eingabe=wert)
        if ergebnis.returncode != 0:
            raise SpeicherFehler(ergebnis.stderr.strip() or "Speichern fehlgeschlagen")

    def loeschen(self, schluessel: str) -> None:
        self._aufruf(["clear", *self._merkmale(schluessel)])

    # --- Bequem: JSON ----------------------------------------------------
    def json_lesen(self, schluessel: str, ersatz=None):
        roh = self.lesen(schluessel)
        if not roh:
            return ersatz
        try:
            return json.loads(roh)
        except ValueError:
            log.warning("Eintrag %r im Passwortspeicher ist beschädigt", schluessel)
            return ersatz

    def json_schreiben(self, schluessel: str, wert) -> None:
        self.schreiben(schluessel, json.dumps(wert, ensure_ascii=False))


class Arbeitsspeicher(Geheimspeicher):
    """Nur für Tests: merkt sich alles im Arbeitsspeicher."""

    def __init__(self):
        super().__init__(werkzeug="-")
        self.daten: dict[str, str] = {}
        self.kaputt = False
        self.verzoegerung = 0.0  # Sekunden – wie ein Passwortspeicher, der nach dem Passwort fragt

    def lesen(self, schluessel):
        if self.verzoegerung:
            import time
            time.sleep(self.verzoegerung)
        if self.kaputt:
            raise SpeicherFehler("kaputt")
        return self.daten.get(schluessel)

    def schreiben(self, schluessel, wert):
        if self.kaputt:
            raise SpeicherFehler("kaputt")
        self.daten[schluessel] = wert

    def loeschen(self, schluessel):
        self.daten.pop(schluessel, None)
