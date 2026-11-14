import json
import socket
import unittest
import urllib.error
import urllib.request

from openregie import einstellungen
from openregie.titel.countdown import Countdown
from openregie.web.server import LokaleWebseite, countdown_seite


def holen(url):
    with urllib.request.urlopen(url, timeout=3) as antwort:
        return antwort.status, antwort.headers.get("Content-Type"), antwort.read().decode("utf-8")


class WebseiteTest(unittest.TestCase):
    def setUp(self):
        self.E = einstellungen.lade()
        self.cd = Countdown("Countdown", 125, 5999)
        self.web = LokaleWebseite(0, self.cd, self.E.countdown)  # Port 0 = freier Port
        self.web.starten()
        self.basis = f"http://127.0.0.1:{self.web.port}"

    def tearDown(self):
        self.web.beenden()

    def test_seite(self):
        status, art, inhalt = holen(self.basis + "/countdown")
        self.assertEqual(status, 200)
        self.assertIn("text/html", art)
        self.assertNotIn("{{", inhalt)  # alle Platzhalter ersetzt
        self.assertIn("/countdown/zustand", inhalt)
        self.assertIn(json.dumps(self.E.countdown.endtext), inhalt)

    def test_seite_mit_schraegstrich_und_parameter(self):
        self.assertEqual(holen(self.basis + "/countdown/?x=1")[0], 200)

    def test_zustand(self):
        status, art, inhalt = holen(self.basis + "/countdown/zustand")
        self.assertEqual(status, 200)
        self.assertEqual(art, "application/json")
        daten = json.loads(inhalt)
        self.assertEqual(daten["text"], "02:05")
        self.assertEqual(daten["zustand"], "bereit")
        self.cd.start()
        self.assertEqual(json.loads(holen(self.basis + "/countdown/zustand")[2])["zustand"], "laeuft")

    def test_unbekannt(self):
        with self.assertRaises(urllib.error.HTTPError) as f:
            holen(self.basis + "/gibtsnicht")
        self.assertEqual(f.exception.code, 404)

    def test_viele_abfragen(self):
        for _ in range(200):
            self.assertEqual(holen(self.basis + "/countdown/zustand")[0], 200)

    def test_nur_lokal_erreichbar(self):
        self.assertEqual(self.web._server.server_address[0], "127.0.0.1")

    def test_port_belegt(self):
        zweite = LokaleWebseite(self.web.port, self.cd, self.E.countdown)
        with self.assertRaises(OSError):
            zweite.starten()

    def test_adresse(self):
        self.assertEqual(self.web.countdown_adresse, f"http://127.0.0.1:{self.web.port}/countdown")

    def test_beenden_gibt_port_frei(self):
        port = self.web.port
        self.web.beenden()
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", port))
        s.close()
        self.web.beenden()  # zweimal beenden darf nicht abstürzen


class PositionTest(unittest.TestCase):
    def test_alle_positionen(self):
        E = einstellungen.lade()
        werte = E.countdown.als_dict()
        for pos, erwartet in [("unten rechts", ("flex-end", "flex-end")), ("oben links", ("flex-start", "flex-start")),
                              ("Mitte", ("center", "center")), ("quatsch", ("center", "center"))]:
            werte["position"] = pos
            seite = countdown_seite(einstellungen.Bereich("countdown", werte))
            self.assertIn(f"justify-content: {erwartet[0]}", seite)
            self.assertIn(f"align-items: {erwartet[1]}", seite)

    def test_endtext_mit_sonderzeichen(self):
        E = einstellungen.lade()
        werte = E.countdown.als_dict()
        werte["endtext"] = 'Gleich "geht\'s" los </script><b>'
        seite = countdown_seite(einstellungen.Bereich("countdown", werte))
        skript = seite.split("<script>", 1)[1]
        self.assertEqual(skript.count("</script>"), 1)  # nur das echte Ende
        self.assertIn("\\u003c/script>", skript)


class EinstellungenTest(unittest.TestCase):
    def test_alles_vorhanden(self):
        E = einstellungen.lade()
        self.assertTrue(E.farben.hintergrund.startswith("#"))
        self.assertEqual(einstellungen.build_anzeige(E), "OpenRegie · Vorabversion · Build " + einstellungen.build_nummer())

    def test_fehlender_eintrag(self):
        E = einstellungen.lade()
        with self.assertRaises(einstellungen.EinstellungsFehler) as f:
            E.farben.gibtsnicht
        self.assertIn("[farben]", str(f.exception))

    def test_kaputte_datei(self):
        import tempfile, pathlib
        with tempfile.TemporaryDirectory() as ordner:
            p = pathlib.Path(ordner) / "einstellungen.toml"
            p.write_text('[farben]\nhintergrund = "#123\n', encoding="utf-8")
            with self.assertRaises(einstellungen.EinstellungsFehler) as f:
                einstellungen.lade(p)
            self.assertIn("Zeile 2", str(f.exception))

    def test_alle_farben_gueltig(self):
        import re
        E = einstellungen.lade()
        for name, wert in E.farben.als_dict().items():
            self.assertRegex(wert, r"^#[0-9A-Fa-f]{6}$", name)
        for name in ("textfarbe", "hintergrundfarbe"):
            self.assertRegex(getattr(E.countdown, name), r"^#[0-9A-Fa-f]{6}$")


if __name__ == "__main__":
    unittest.main()
