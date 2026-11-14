"""OBS als unsichtbarer Motor: starten, überwachen, beim Schließen beenden.

OpenRegie startet OBS selbst – nur als kleines Symbol in der Taskleiste
(`--minimize-to-tray`), ohne sichtbares OBS-Fenster. Läuft OBS schon (z. B. von
Hand geöffnet), startet OpenRegie kein zweites und beendet es später auch nicht.

Nach dem Verbinden sorgt der Motor dafür, dass die richtige Szenensammlung
geladen ist (Eintrag `szenensammlung` in einstellungen.toml).
"""

from __future__ import annotations

import logging
import shlex
from enum import Enum

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

from . import zugang as zugang_modul
from .verbindung import ObsVerbindung, Sendung, Status

log = logging.getLogger("openregie.motor")


class MotorZustand(Enum):
    AUS = "aus"  # OBS läuft nicht
    STARTET = "startet"  # OpenRegie hat OBS gerade gestartet
    LAEUFT = "laeuft"  # OBS läuft (von OpenRegie oder von Hand gestartet)
    FEHLER = "fehler"  # OBS ließ sich nicht starten oder ist abgestürzt


class ObsMotor(QObject):
    # (Zustand, Meldung für Menschen – leer, wenn alles gut ist)
    zustand_geaendert = Signal(object, str)
    # Meldung zur Szenensammlung (leer = alles gut)
    sammlung_meldung = Signal(str)

    def __init__(self, obs_einstellungen, texte, verbindung: ObsVerbindung, parent=None, obs_laeuft=None):
        super().__init__(parent)
        self._obs = obs_einstellungen
        self._texte = texte
        self._verbindung = verbindung
        self._obs_laeuft = obs_laeuft or zugang_modul.obs_laeuft
        self._prozess: QProcess | None = None
        self._beendet_gewollt = False
        self.zustand = MotorZustand.AUS
        self.meldung = ""
        self.selbst_gestartet = False

        self._start_zeitlimit = QTimer(self)
        self._start_zeitlimit.setSingleShot(True)
        self._start_zeitlimit.timeout.connect(self._start_zu_langsam)

        verbindung.status_geaendert.connect(self._verbindungsstatus)

    # ------------------------------------------------------------------
    def befehl(self) -> list[str]:
        """Der Startbefehl: OBS unsichtbar, ohne „Abgesichert starten?“-Frage, mit Szenensammlung."""
        teile = shlex.split(str(self._obs.startbefehl))
        if bool(self._obs.unsichtbar):
            teile.append("--minimize-to-tray")
        # Nach einem Absturz würde OBS sonst ein Fenster „Im abgesicherten Modus starten?“ zeigen.
        teile.append("--disable-shutdown-check")
        sammlung = str(self._obs.szenensammlung).strip()
        if sammlung:
            teile += ["--collection", sammlung]
        return teile

    def starten(self) -> None:
        """OBS starten – aber nur, wenn es nicht schon läuft."""
        if self._prozess is not None and self._prozess.state() != QProcess.ProcessState.NotRunning:
            return
        if self._obs_laeuft():
            log.info("OBS läuft schon – OpenRegie startet kein zweites")
            self.selbst_gestartet = False
            self._zustand_setzen(MotorZustand.LAEUFT, "")
            self._verbindung.starten()
            return

        teile = self.befehl()
        if not teile:
            self._zustand_setzen(MotorZustand.FEHLER, self._texte.meldung_obs_start_fehler)
            return
        log.info("Starte OBS: %s", " ".join(teile))
        prozess = QProcess(self)
        prozess.setProgram(teile[0])
        prozess.setArguments(teile[1:])
        # OBS soll nichts in unser Protokoll schreiben (es hat ein eigenes).
        prozess.setStandardOutputFile(QProcess.nullDevice())
        prozess.setStandardErrorFile(QProcess.nullDevice())
        prozess.errorOccurred.connect(lambda fehler, p=prozess: self._prozessfehler(p, fehler))
        prozess.finished.connect(lambda code, _status, p=prozess: self._prozess_ende(p, code))
        self._prozess = prozess
        self._beendet_gewollt = False
        self.selbst_gestartet = True
        self._zustand_setzen(MotorZustand.STARTET, self._texte.meldung_obs_startet)
        prozess.start()
        self._start_zeitlimit.start(int(float(self._obs.start_zeitlimit_sekunden) * 1000))
        self._verbindung.starten()

    def beenden(self, warten_ms: int = 8000) -> None:
        """Beim Schließen von OpenRegie: das selbst gestartete OBS sauber beenden."""
        self._start_zeitlimit.stop()
        prozess = self._prozess
        if prozess is None or not self.selbst_gestartet or not bool(self._obs.beim_beenden_schliessen):
            return
        if prozess.state() == QProcess.ProcessState.NotRunning:
            return
        self._beendet_gewollt = True
        log.info("Beende OBS")
        prozess.terminate()  # „bitte beenden“ – OBS speichert dann noch seine Einstellungen
        if not prozess.waitForFinished(warten_ms):
            log.warning("OBS hat sich nicht beendet – wird hart beendet")
            prozess.kill()
            prozess.waitForFinished(2000)

    def obs_laeuft(self) -> bool:
        return bool(self._obs_laeuft())

    @property
    def braucht_nachfrage_beim_beenden(self) -> bool:
        """Läuft gerade ein Stream aus dem OBS, das OpenRegie beenden würde?"""
        return (self.selbst_gestartet and bool(self._obs.beim_beenden_schliessen)
                and self._verbindung.sendung in (Sendung.AN, Sendung.STARTET))

    # ------------------------------------------------------------------
    def _verbindungsstatus(self, status: Status, _meldung: str) -> None:
        if status is Status.VERBUNDEN:
            self._start_zeitlimit.stop()
            self._zustand_setzen(MotorZustand.LAEUFT, "")
            self._sammlung_pruefen()

    def _start_zu_langsam(self) -> None:
        if not self._verbindung.verbunden:
            log.warning("OBS ist gestartet, aber nach dem Zeitlimit nicht verbunden")
            self._zustand_setzen(MotorZustand.FEHLER, self._texte.meldung_obs_start_zu_langsam)

    def _prozessfehler(self, prozess: QProcess, fehler) -> None:
        if prozess is not self._prozess:
            return
        if fehler == QProcess.ProcessError.FailedToStart:
            log.error("OBS ließ sich nicht starten (%s)", prozess.program())
            self._start_zeitlimit.stop()
            self._prozess = None
            self.selbst_gestartet = False
            self._zustand_setzen(MotorZustand.FEHLER, self._texte.meldung_obs_start_fehler)

    def _prozess_ende(self, prozess: QProcess, code: int) -> None:
        if prozess is not self._prozess:
            return
        self._prozess = None
        self._start_zeitlimit.stop()
        if self._beendet_gewollt:
            self._zustand_setzen(MotorZustand.AUS, "")
            return
        log.warning("OBS wurde unerwartet beendet (Code %s)", code)
        self.selbst_gestartet = False
        self._zustand_setzen(MotorZustand.FEHLER, self._texte.meldung_obs_abgestuerzt)

    # ------------------------------------------------------------------
    def _sammlung_pruefen(self) -> None:
        """Ist die richtige Szenensammlung geladen? Sonst umschalten."""
        gewuenscht = str(self._obs.szenensammlung).strip()
        if not gewuenscht:
            return

        def liste(ok, daten, fehler):
            if not ok:
                log.warning("Szenensammlungen nicht lesbar: %s", fehler)
                return
            aktuell = daten.get("currentSceneCollectionName", "")
            alle = daten.get("sceneCollections") or []
            if aktuell == gewuenscht:
                self.sammlung_meldung.emit("")
                return
            if gewuenscht not in alle:
                log.warning("Szenensammlung %r fehlt (vorhanden: %s)", gewuenscht, alle)
                self.sammlung_meldung.emit(self._texte.meldung_sammlung_fehlt.format(name=gewuenscht))
                return
            log.info("Wechsle Szenensammlung %r → %r", aktuell, gewuenscht)
            self._verbindung.anfrage("SetCurrentSceneCollection", {"sceneCollectionName": gewuenscht}, gewechselt)

        def gewechselt(ok, _daten, fehler):
            if ok:
                self.sammlung_meldung.emit("")
                self._verbindung.szene_neu_abfragen()
            else:
                log.warning("Szenensammlung wechseln fehlgeschlagen: %s", fehler)
                self.sammlung_meldung.emit(self._texte.meldung_sammlung_fehler)

        self._verbindung.anfrage("GetSceneCollectionList", rueckruf=liste)

    def _zustand_setzen(self, zustand: MotorZustand, meldung: str) -> None:
        if zustand is self.zustand and meldung == self.meldung:
            return
        self.zustand, self.meldung = zustand, meldung
        self.zustand_geaendert.emit(zustand, meldung)
