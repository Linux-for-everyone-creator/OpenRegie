"""Prüft: Uno-Quellen werden in OBS angelegt, liegen immer ganz oben, alte Quelle wird entfernt."""

import unittest

from openregie import einstellungen
from openregie.geheimspeicher import Arbeitsspeicher
from openregie.obs.overlays_in_obs import ObsOverlays, ausgabe_kennung, ist_alter_countdown, neue_reihenfolge
from openregie.obs.verbindung import ObsVerbindung
from openregie.uno.verwaltung import UnoVerwaltung

from .falsches_internet import EINZEL_TOKEN, FalschesInternet
from .falsches_obs import FalschesObs
from .hilfen import app, groesste_pause_ms, internet_einstellungen, obs_einstellungen, warte, warte_bis, zugang

UNO = "Uno: Countdown | Circles"
AUSGABE = "https://controlapi.singular.live/output/AUSGABE123/Output?aspect=16:9"
ALT = "http://127.0.0.1:8787/countdown"


class HilfenTest(unittest.TestCase):
    def test_ausgabe_erkennen(self):
        self.assertEqual(ausgabe_kennung(AUSGABE), "AUSGABE123")
        self.assertEqual(ausgabe_kennung("https://app.overlays.uno/output/abc123"), "abc123")
        self.assertIsNone(ausgabe_kennung("https://example.com/chat"))
        self.assertIsNone(ausgabe_kennung(""))

    def test_nur_alter_countdown(self):
        self.assertTrue(ist_alter_countdown("Rolliregie Countdown", ALT))
        self.assertTrue(ist_alter_countdown("OpenRegie Countdown", "http://localhost:8787/countdown"))
        self.assertFalse(ist_alter_countdown("Rolliregie Countdown", AUSGABE))
        self.assertFalse(ist_alter_countdown("Chat", "http://127.0.0.1:8080/chat"))
        self.assertFalse(ist_alter_countdown("Mein Browser", "https://example.com/countdown"))

    def test_neue_reihenfolge(self):
        e = lambda i, n: {"sceneItemId": i, "sourceName": n, "sceneItemIndex": i}
        liste = [e(0, "A"), e(1, "Uno1"), e(2, "B"), e(3, "Uno2"), e(4, "C")]
        self.assertEqual([x["sourceName"] for x in neue_reihenfolge(liste, {"Uno1", "Uno2"})],
                         ["A", "B", "C", "Uno1", "Uno2"])


class ObsOverlaysTest(unittest.TestCase):
    def setUp(self):
        app()
        self.netz = FalschesInternet()
        self.E = internet_einstellungen(self.netz)
        self.obs = FalschesObs(passwort="geheim")
        # Kevins Szene: zweimal die alte Countdown-Quelle, darüber die Bildschirmaufnahme
        self.obs.szenen = {"Szene": [], "Pause": []}
        self.obs.quelle_anlegen("Szene", "Rolliregie Countdown", "browser_source", {"url": ALT})
        self.obs.quelle_anlegen("Szene", "Rolliregie Countdown", "browser_source", {"url": ALT})
        self.obs.quelle_anlegen("Szene", "Bildschirmaufnahme (PipeWire)", "pipewire-screen-capture-source")
        self.obs.quelle_anlegen("Pause", "Pausenbild", "image_source")
        self.speicher = Arbeitsspeicher()
        self.speicher.json_schreiben("uno", [{"name": "Countdown | Circles", "token": EINZEL_TOKEN, "einzeln": True}])

    def tearDown(self):
        self.oo._sammeln.stop()
        self.uno.beenden()
        self.v.beenden()
        self.obs.beenden()
        self.netz.beenden()
        warte(20)

    def starten(self, **obs_werte):
        oe, _ = obs_einstellungen(szenensammlung="", **obs_werte)
        self.v = ObsVerbindung(oe, self.E.texte, zugang_finden=zugang(self.obs.port), obs_laeuft=lambda: True)
        self.uno = UnoVerwaltung(self.E.uno, self.E.texte, self.speicher)
        self.oo = ObsOverlays(oe, self.v, self.uno)
        self.uno.laden()
        self.v.starten()

    def ruhig(self, ms=3000):
        """Warten, bis OpenRegie mit dem Abgleich fertig ist und nichts mehr nachkommt."""
        def fertig():
            return not self.oo._laeuft and not self.oo._sammeln.isActive() and self.oo.durchlaeufe > 0
        self.assertTrue(warte_bis(fertig, ms))
        warte(400)
        self.assertTrue(warte_bis(fertig, ms))

    def test_kevins_szene(self):
        """Der gemeldete Fall: Countdown war unter der Bildschirmaufnahme – jetzt ganz oben."""
        self.starten()
        self.assertTrue(warte_bis(lambda: UNO in self.obs.quellen, 5000))
        self.ruhig()
        self.assertNotIn("Rolliregie Countdown", self.obs.quellen)  # alte, leere Quelle weg
        self.assertEqual(self.obs.reihenfolge("Szene"), ["Bildschirmaufnahme (PipeWire)", UNO])  # oben = zuletzt
        self.assertEqual(self.obs.reihenfolge("Pause"), ["Pausenbild", UNO])  # in jeder Szene
        einst = self.obs.quellen[UNO]["settings"]
        self.assertEqual(einst["url"], AUSGABE)
        self.assertEqual((einst["width"], einst["height"]), (1280, 720))  # so groß wie das Bild

    def test_bleibt_oben_wenn_etwas_dazukommt(self):
        self.starten()
        self.assertTrue(warte_bis(lambda: UNO in self.obs.quellen, 5000))
        self.ruhig()
        self.obs.quelle_anlegen("Szene", "Kamera", "v4l2_input")  # landet in OBS ganz oben
        self.assertTrue(warte_bis(lambda: self.obs.reihenfolge("Szene")[-1] == UNO, 3000))
        self.assertEqual(self.obs.reihenfolge("Szene"), ["Bildschirmaufnahme (PipeWire)", "Kamera", UNO])

    def test_bleibt_oben_wenn_von_hand_verschoben(self):
        self.starten()
        self.assertTrue(warte_bis(lambda: UNO in self.obs.quellen, 5000))
        self.ruhig()
        liste = self.obs.szenen["Szene"]
        liste.insert(len(liste), liste.pop(0))  # Bildschirmaufnahme in OBS nach oben gezogen
        self.obs.ereignis("SceneItemListReindexed", {"sceneName": "Szene"})
        self.assertTrue(warte_bis(lambda: self.obs.reihenfolge("Szene")[-1] == UNO, 3000))

    def test_neue_szene_bekommt_uno(self):
        self.starten()
        self.assertTrue(warte_bis(lambda: UNO in self.obs.quellen, 5000))
        self.ruhig()
        self.obs.szene_anlegen("Interview")
        self.assertTrue(warte_bis(lambda: self.obs.reihenfolge("Interview") == [UNO], 3000))

    def test_kein_doppel_bei_neuverbinden(self):
        self.starten()
        self.assertTrue(warte_bis(lambda: UNO in self.obs.quellen, 5000))
        self.ruhig()
        self.v.jetzt_neu_verbinden()
        self.assertTrue(warte_bis(lambda: self.v.verbunden, 3000))
        warte(500)
        self.ruhig()
        self.assertEqual([n for n in self.obs.quellen if n.startswith("Uno")], [UNO])
        self.assertEqual(self.obs.reihenfolge("Szene").count(UNO), 1)
        self.assertEqual(self.obs.reihenfolge("Pause").count(UNO), 1)

    def test_keine_endlosschleife(self):
        self.starten()
        self.assertTrue(warte_bis(lambda: UNO in self.obs.quellen, 5000))
        self.ruhig()
        vorher_l, vorher_u = self.oo.durchlaeufe, self.obs.umsortiert
        warte(1500)
        self.assertEqual(self.oo.durchlaeufe, vorher_l)  # kommt zur Ruhe
        self.assertEqual(self.obs.umsortiert, vorher_u)

    def test_von_hand_angelegte_uno_quelle_wird_erkannt(self):
        self.obs.quelle_anlegen("Szene", "Mein Countdown", "browser_source",
                                {"url": "https://controlapi.singular.live/output/AUSGABE123/Output"})
        self.obs.quelle_anlegen("Szene", "Spielszene", "game_capture")
        self.starten()
        self.ruhig(5000)
        warte(500)
        self.ruhig()
        self.assertNotIn(UNO, self.obs.quellen)  # nicht doppelt anlegen
        self.assertEqual(self.obs.reihenfolge("Szene")[-1], "Mein Countdown")
        self.assertEqual(self.obs.reihenfolge("Pause"), ["Pausenbild", "Mein Countdown"])

    def test_andere_quellen_bleiben(self):
        self.obs.quelle_anlegen("Szene", "Chat", "browser_source", {"url": "http://127.0.0.1:8080/chat"})
        self.starten()
        self.assertTrue(warte_bis(lambda: UNO in self.obs.quellen, 5000))
        self.ruhig()
        self.assertIn("Chat", self.obs.quellen)
        self.assertIn("Bildschirmaufnahme (PipeWire)", self.obs.quellen)
        self.assertEqual(self.obs.reihenfolge("Szene"), ["Bildschirmaufnahme (PipeWire)", "Chat", UNO])

    def test_abschaltbar(self):
        self.starten(uno_in_jede_szene=False, overlays_immer_oben=False)
        self.assertTrue(warte_bis(lambda: self.uno.ausgaben(), 5000))
        self.ruhig()
        self.assertNotIn(UNO, self.obs.quellen)
        self.assertEqual(self.obs.umsortiert, 0)

    def test_oberflaeche_bleibt_fluessig(self):
        self.starten()
        pause = groesste_pause_ms(2500, lambda: UNO in self.obs.quellen)
        self.assertLess(pause, 250, f"Oberfläche hing {pause:.0f} ms")


if __name__ == "__main__":
    unittest.main()
