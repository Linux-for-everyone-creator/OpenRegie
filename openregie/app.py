"""Programmstart von OpenRegie."""

from __future__ import annotations

import logging
import logging.handlers
import os
import signal
import sys
from pathlib import Path

from PySide6.QtCore import QLockFile, QStandardPaths, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from . import einstellungen
from .einstellungen import PROJEKT_ORDNER, EinstellungsFehler

SYMBOL = PROJEKT_ORDNER / "daten" / "openregie.svg"


def protokoll_einrichten() -> Path:
    """Schreibt ein Protokoll (für die Fehlersuche) nach ~/.local/state/openregie/."""
    ordner = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state") / "openregie"
    ordner.mkdir(parents=True, exist_ok=True)
    datei = ordner / "openregie.log"
    handler = logging.handlers.RotatingFileHandler(datei, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    wurzel = logging.getLogger()
    wurzel.setLevel(logging.INFO)
    wurzel.addHandler(handler)
    wurzel.addHandler(logging.StreamHandler(sys.stderr))
    return datei


def hinweis(titel: str, text: str) -> None:
    """Einfaches Hinweisfenster mit einem großen OK-Knopf."""
    box = QMessageBox()
    box.setWindowTitle(titel)
    box.setText(text)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    box.setStyleSheet("QLabel { font-size: 20px; } QPushButton { font-size: 20px; min-height: 64px; min-width: 160px; }")
    box.exec()


def main() -> int:
    log_datei = protokoll_einrichten()
    log = logging.getLogger("openregie")

    app = QApplication(sys.argv)
    app.setApplicationName("OpenRegie")
    app.setDesktopFileName("openregie")  # passt zum Startmenü-Eintrag (Symbol in der Taskleiste)
    if SYMBOL.exists():
        app.setWindowIcon(QIcon(str(SYMBOL)))

    try:
        E = einstellungen.lade()
        log.info("Starte %s (Protokoll: %s)", einstellungen.build_anzeige(E), log_datei)
    except EinstellungsFehler as fehler:
        hinweis("OpenRegie", str(fehler))
        return 1

    # Nur ein OpenRegie-Fenster gleichzeitig
    ordner = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.RuntimeLocation) or "/tmp"
    sperre = QLockFile(os.path.join(ordner, "openregie.lock"))
    sperre.setStaleLockTime(0)
    if not sperre.tryLock(200):
        hinweis("OpenRegie", E.texte.meldung_schon_offen)
        return 0

    from .obs.verbindung import ObsVerbindung
    from .obs.vorschau import Vorschau
    from .oberflaeche.hauptfenster import Hauptfenster
    from .titel.countdown import Countdown
    from .web.server import LokaleWebseite

    try:
        countdown = Countdown(E.texte.countdown_titelname, int(E.countdown.startdauer_sekunden),
                              int(E.countdown.hoechstdauer_sekunden))

        webseite = LokaleWebseite(int(E.countdown.webseiten_port), countdown, E.countdown)
        start_meldung, adresse = "", None
        try:
            webseite.starten()
            adresse = webseite.countdown_adresse
            log.info("Countdown-Seite: %s", adresse)
        except OSError as fehler:
            log.error("Countdown-Seite startet nicht: %s", fehler)
            start_meldung = E.texte.meldung_webseite_port_belegt.format(port=E.countdown.webseiten_port)

        verbindung = ObsVerbindung(E.obs, E.texte)
        vorschau = Vorschau(verbindung, E.vorschau)
        fenster = Hauptfenster(E, verbindung, vorschau, countdown, adresse, start_meldung)
    except EinstellungsFehler as fehler:
        hinweis("OpenRegie", str(fehler))
        return 1

    def aufraeumen():
        vorschau.anhalten()
        verbindung.beenden()
        webseite.beenden()
        sperre.unlock()
        log.info("OpenRegie beendet")

    app.aboutToQuit.connect(aufraeumen)

    # Beim Abmelden/Herunterfahren schickt das System „bitte beenden“ (SIGTERM):
    # dann sauber schließen. Der kleine Timer gibt Python regelmäßig die Gelegenheit dazu.
    signal.signal(signal.SIGTERM, lambda *_: app.quit())
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    wach = QTimer()
    wach.start(500)
    wach.timeout.connect(lambda: None)

    if bool(E.groessen.fenster_maximiert):
        fenster.showMaximized()
    else:
        fenster.show()
    verbindung.starten()
    return app.exec()
