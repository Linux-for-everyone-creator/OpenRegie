"""Programmstart von OpenRegie.

Ablauf: Ladebildschirm zeigen → OBS unsichtbar starten (oder das laufende nehmen)
→ verbinden, Szenensammlung prüfen → Regiepult öffnen. Uno-Overlays und
Twitch-Anmeldung werden aus dem Passwortspeicher geladen.
"""

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
# Höchstens so lange bleibt der Ladebildschirm stehen, auch wenn OBS noch nicht bereit ist.
STARTBILD_HOECHSTENS_MS = 20000
STARTBILD_FERTIG_MS = 600  # „Alles bereit!“ kurz zeigen


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

    from .geheimspeicher import Geheimspeicher
    from .obs.motor import MotorZustand, ObsMotor
    from .obs.verbindung import ObsVerbindung
    from .obs.vorschau import Vorschau
    from .oberflaeche.hauptfenster import Hauptfenster
    from .oberflaeche.startbild import Startbild
    from .twitch.konto import TwitchKonto
    from .uno.verwaltung import UnoVerwaltung

    try:
        startbild = Startbild(E, SYMBOL)
        startbild.text_setzen(E.texte.start_obs)
        startbild.show()
        app.processEvents()

        speicher = Geheimspeicher()
        verbindung = ObsVerbindung(E.obs, E.texte)
        motor = ObsMotor(E.obs, E.texte, verbindung)
        vorschau = Vorschau(verbindung, E.vorschau)
        uno = UnoVerwaltung(E.uno, E.texte, speicher)
        twitch = TwitchKonto(E.twitch, E.texte, speicher)
        fenster = Hauptfenster(E, verbindung, vorschau, motor, uno, twitch)
    except EinstellungsFehler as fehler:
        hinweis("OpenRegie", str(fehler))
        return 1

    def aufraeumen():
        vorschau.anhalten()
        uno.beenden()
        twitch.beenden()
        verbindung.beenden()
        motor.beenden()  # das selbst gestartete OBS mit beenden
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

    # --- Ladebildschirm, bis OBS bereit ist (oder etwas schiefgeht) ------------
    def fenster_zeigen():
        if not startbild.isVisible():
            return
        # erst das Regiepult zeigen, dann den Ladebildschirm schließen
        # (sonst denkt Qt kurz, das letzte Fenster sei zu, und beendet sich)
        if bool(E.groessen.fenster_maximiert):
            fenster.showMaximized()
        else:
            fenster.show()
        startbild.close()

    def motor_meldet(zustand, _meldung):
        if zustand is MotorZustand.FEHLER:
            fenster_zeigen()  # das Regiepult zeigt die Meldung und die Knöpfe

    def verbindung_meldet(status, _meldung):
        if verbindung.verbunden:
            startbild.text_setzen(E.texte.start_fertig)
            QTimer.singleShot(STARTBILD_FERTIG_MS, fenster_zeigen)
        elif motor.zustand is not MotorZustand.STARTET:
            startbild.text_setzen(E.texte.start_verbinde)

    motor.zustand_geaendert.connect(motor_meldet)
    verbindung.status_geaendert.connect(verbindung_meldet)
    QTimer.singleShot(STARTBILD_HOECHSTENS_MS, fenster_zeigen)

    uno.laden()
    twitch.laden()
    motor.starten()
    return app.exec()
