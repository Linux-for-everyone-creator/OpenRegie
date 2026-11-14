"""Prüft das unsichtbare Starten und Beenden von OBS und die Szenensammlung."""

import json
import os
import shlex
import sys
import tempfile
import unittest
from pathlib import Path

from openregie import einstellungen
from openregie.obs.motor import MotorZustand, ObsMotor
from openregie.obs.verbindung import ObsVerbindung, Sendung

from .falsches_obs import FalschesObs
from .hilfen import app, obs_einstellungen, warte, warte_bis, zugang

PROGRAMM = Path(__file__).with_name("falsches_obs_programm.py")


class MotorTest(unittest.TestCase):
    def setUp(self):
        app()
        self.ordner = tempfile.TemporaryDirectory()
        self.datei = Path(self.ordner.name) / "argumente.json"
        os.environ["OPENREGIE_TEST_DATEI"] = str(self.datei)
        os.environ.pop("OPENREGIE_TEST_ABSTURZ", None)
        self.obs = FalschesObs(passwort="geheim")
        self.laeuft = False
        self.E = einstellungen.lade()

    def tearDown(self):
        for m in getattr(self, "_motoren", []):
            m.beenden(2000)
        for v in getattr(self, "_verbindungen", []):
            v.beenden()
        self.obs.beenden()
        self.ordner.cleanup()
        os.environ.pop("OPENREGIE_TEST_ABSTURZ", None)
        warte(20)

    def motor(self, **obs_werte):
        werte = dict(startbefehl=f"{shlex.quote(sys.executable)} {shlex.quote(str(PROGRAMM))}",
                     start_zeitlimit_sekunden=3)
        werte.update(obs_werte)
        oe, _ = obs_einstellungen(**werte)
        v = ObsVerbindung(oe, self.E.texte, zugang_finden=zugang(self.obs.port), obs_laeuft=lambda: self.laeuft)
        m = ObsMotor(oe, self.E.texte, v, obs_laeuft=lambda: self.laeuft)
        self._motoren = getattr(self, "_motoren", []) + [m]
        self._verbindungen = getattr(self, "_verbindungen", []) + [v]
        return m, v

    def argumente(self):
        self.assertTrue(warte_bis(self.datei.exists, 3000))
        warte_bis(lambda: self.datei.read_text().strip(), 1000)
        return json.loads(self.datei.read_text())

    def test_startet_unsichtbar_mit_sammlung(self):
        m, v = self.motor(szenensammlung="Meine Show")
        m.starten()
        self.assertIs(m.zustand, MotorZustand.STARTET)
        self.assertTrue(m.selbst_gestartet)
        args = self.argumente()
        self.assertIn("--minimize-to-tray", args)
        self.assertIn("--disable-shutdown-check", args)
        self.assertEqual(args[args.index("--collection") + 1], "Meine Show")
        self.assertTrue(warte_bis(lambda: v.verbunden, 3000))
        self.assertIs(m.zustand, MotorZustand.LAEUFT)

    def test_sichtbar_wenn_gewuenscht(self):
        m, _ = self.motor(unsichtbar=False, szenensammlung="")
        m.starten()
        args = self.argumente()
        self.assertNotIn("--minimize-to-tray", args)
        self.assertNotIn("--collection", args)

    def test_kein_zweites_obs(self):
        self.laeuft = True
        m, v = self.motor()
        m.starten()
        self.assertFalse(m.selbst_gestartet)
        self.assertIs(m.zustand, MotorZustand.LAEUFT)
        warte(300)
        self.assertFalse(self.datei.exists())  # nichts gestartet
        self.assertTrue(warte_bis(lambda: v.verbunden, 3000))  # aber verbunden

    def test_sauber_beenden(self):
        m, v = self.motor()
        m.starten()
        self.argumente()
        m.beenden()
        self.assertEqual(Path(str(self.datei) + ".ende").read_text(), "sauber")
        self.assertIs(m.zustand, MotorZustand.AUS)

    def test_fremdes_obs_wird_nicht_beendet(self):
        self.laeuft = True
        m, _ = self.motor()
        m.starten()
        m.beenden()  # darf nichts tun
        self.assertIs(m.zustand, MotorZustand.LAEUFT)

    def test_nicht_beenden_wenn_abgeschaltet(self):
        m, _ = self.motor(beim_beenden_schliessen=False)
        m.starten()
        self.argumente()
        m.beenden()
        warte(300)
        self.assertFalse(Path(str(self.datei) + ".ende").exists())
        m._prozess.kill()
        m._prozess.waitForFinished(2000)

    def test_programm_fehlt(self):
        m, _ = self.motor(startbefehl="/gibt/es/nicht/obs")
        meldungen = []
        m.zustand_geaendert.connect(lambda z, t: meldungen.append((z, t)))
        m.starten()
        self.assertTrue(warte_bis(lambda: m.zustand is MotorZustand.FEHLER, 3000))
        self.assertEqual(m.meldung, self.E.texte.meldung_obs_start_fehler)
        self.assertFalse(m.selbst_gestartet)

    def test_absturz(self):
        os.environ["OPENREGIE_TEST_ABSTURZ"] = "1"
        m, _ = self.motor()
        m.starten()
        self.assertTrue(warte_bis(lambda: m.zustand is MotorZustand.FEHLER, 3000))
        self.assertEqual(m.meldung, self.E.texte.meldung_obs_abgestuerzt)
        # „OBS starten“ startet es wieder
        os.environ.pop("OPENREGIE_TEST_ABSTURZ")
        self.datei.unlink()
        m.starten()
        self.argumente()
        self.assertIs(m.zustand, MotorZustand.STARTET)

    def test_meldet_sich_nicht(self):
        m, v = self.motor(start_zeitlimit_sekunden=0.5)
        v._zugang_finden = zugang(1)  # niemand antwortet
        m.starten()
        self.assertTrue(warte_bis(lambda: m.zustand is MotorZustand.FEHLER, 3000))
        self.assertEqual(m.meldung, self.E.texte.meldung_obs_start_zu_langsam)

    def test_nachfrage_nur_wenn_live(self):
        m, v = self.motor()
        m.starten()
        self.assertTrue(warte_bis(lambda: v.verbunden, 3000))
        self.assertFalse(m.braucht_nachfrage_beim_beenden)
        self.obs.stream_starten()
        self.assertTrue(warte_bis(lambda: v.sendung is Sendung.AN, 3000))
        self.assertTrue(m.braucht_nachfrage_beim_beenden)


class SammlungTest(unittest.TestCase):
    """Richtige Szenensammlung laden, wenn OBS schon lief (dann greift --collection nicht)."""

    def setUp(self):
        app()
        self.obs = FalschesObs(passwort="geheim")
        self.E = einstellungen.lade()

    def tearDown(self):
        self.v.beenden()
        self.obs.beenden()
        warte(20)

    def los(self, gewuenscht):
        oe, _ = obs_einstellungen(szenensammlung=gewuenscht)
        self.v = ObsVerbindung(oe, self.E.texte, zugang_finden=zugang(self.obs.port), obs_laeuft=lambda: True)
        self.m = ObsMotor(oe, self.E.texte, self.v, obs_laeuft=lambda: True)
        self.meldungen = []
        self.m.sammlung_meldung.connect(self.meldungen.append)
        self.m.starten()
        self.assertTrue(warte_bis(lambda: self.v.verbunden, 3000))

    def test_wechselt(self):
        self.los("Show")
        self.assertTrue(warte_bis(lambda: self.obs.sammlung == "Show", 3000))
        self.assertTrue(warte_bis(lambda: self.meldungen == [""], 3000))

    def test_schon_richtig(self):
        self.los("Unbenannt")
        self.assertTrue(warte_bis(lambda: self.meldungen, 3000))
        self.assertNotIn("SetCurrentSceneCollection", [a for a, _ in self.obs.anfragen])

    def test_gibts_nicht(self):
        self.los("Gibts nicht")
        self.assertTrue(warte_bis(lambda: self.meldungen, 3000))
        self.assertIn("Gibts nicht", self.meldungen[0])
        self.assertEqual(self.obs.sammlung, "Unbenannt")

    def test_leer_heisst_nichts_tun(self):
        self.los("")
        warte(300)
        self.assertNotIn("GetSceneCollectionList", [a for a, _ in self.obs.anfragen])


if __name__ == "__main__":
    unittest.main()
