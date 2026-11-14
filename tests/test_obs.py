import socket
import unittest

from PySide6.QtNetwork import QHostAddress

from openregie.obs import verbindung as vmod
from openregie.obs.verbindung import EREIGNISSE_AUSGABEN, ObsVerbindung, Sendung, Status, ZEITLIMIT_TEXT
from openregie.obs.vorschau import Vorschau, bild_aus_daten
from openregie.obs import zugang as zmod

from .falsches_obs import FalschesObs, testbild_daten
from .hilfen import app, obs_einstellungen, warte, warte_bis, zugang


def freier_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class Grundlage(unittest.TestCase):
    passwort_obs = "geheim"
    passwort_rolli = "geheim"

    def setUp(self):
        app()
        self.obs = FalschesObs(passwort=self.passwort_obs)
        self.einst, self.E = obs_einstellungen()
        self.laeuft = True
        self.v = ObsVerbindung(self.einst, self.E.texte, zugang_finden=zugang(self.obs.port, self.passwort_rolli),
                               obs_laeuft=lambda: self.laeuft)
        self.stati = []
        self.sendungen = []
        self.v.status_geaendert.connect(lambda s, m: self.stati.append((s, m)))
        self.v.sendung_geaendert.connect(self.sendungen.append)

    def tearDown(self):
        self.v.beenden()
        self.obs.beenden()
        warte(20)

    def verbinden(self):
        self.v.starten()
        self.assertTrue(warte_bis(lambda: self.v.verbunden), self.v.meldung)
        self.assertTrue(warte_bis(lambda: self.v.szene != ""))


class VerbindungTest(Grundlage):
    def test_verbindet_mit_passwort(self):
        self.verbinden()
        self.assertEqual(self.v.meldung, self.E.texte.status_verbunden)
        self.assertEqual(self.stati[0][0], Status.VERBINDE)
        self.assertTrue(self.obs.identify_daten["eventSubscriptions"] & EREIGNISSE_AUSGABEN)
        self.assertEqual(self.v.szene, "Szene 1")

    def test_on_air(self):
        self.verbinden()
        self.assertEqual(self.v.sendung, Sendung.AUS)
        self.obs.stream_starten()
        self.assertTrue(warte_bis(lambda: self.v.sendung is Sendung.AN))
        self.assertEqual(self.sendungen, [Sendung.STARTET, Sendung.AN])
        self.obs.stream_stoppen()
        self.assertTrue(warte_bis(lambda: self.v.sendung is Sendung.AUS))
        self.assertEqual(self.sendungen[-2:], [Sendung.STOPPT, Sendung.AUS])

    def test_schon_live_beim_verbinden(self):
        self.obs.stream_aktiv = True
        self.verbinden()
        self.assertTrue(warte_bis(lambda: self.v.sendung is Sendung.AN))

    def test_stream_abfrage_als_sicherheitsnetz(self):
        """Falls ein Ereignis verloren geht, merkt die regelmäßige Abfrage es trotzdem."""
        alt = vmod.STREAM_ABFRAGE_MS
        vmod.STREAM_ABFRAGE_MS = 100
        try:
            self.v._stream_timer.setInterval(100)
            self.verbinden()
            self.obs.stream_aktiv = True  # ohne Ereignis
            self.assertTrue(warte_bis(lambda: self.v.sendung is Sendung.AN, 1500))
            self.obs.stream_aktiv = False
            self.assertTrue(warte_bis(lambda: self.v.sendung is Sendung.AUS, 1500))
        finally:
            vmod.STREAM_ABFRAGE_MS = alt

    def test_szenenwechsel(self):
        self.verbinden()
        szenen = []
        self.v.szene_geaendert.connect(szenen.append)
        self.obs.szene_wechseln("Pause")
        self.assertTrue(warte_bis(lambda: self.v.szene == "Pause"))
        self.assertEqual(szenen, ["Pause"])

    def test_abbruch_und_automatisch_neu(self):
        self.verbinden()
        self.obs.stream_starten()
        self.assertTrue(warte_bis(lambda: self.v.sendung is Sendung.AN))
        self.obs.alle_trennen()
        self.assertTrue(warte_bis(lambda: self.v.status is Status.GETRENNT))
        self.assertEqual(self.v.meldung, self.E.texte.meldung_verbindung_weg)
        self.assertEqual(self.v.sendung, Sendung.AUS)  # ohne Verbindung kein „On Air“
        self.assertEqual(self.v.szene, "")
        self.assertTrue(warte_bis(lambda: self.v.verbunden, 3000))
        self.assertTrue(warte_bis(lambda: self.v.sendung is Sendung.AN))  # wieder erkannt

    def test_obs_weg_und_wieder_da(self):
        self.verbinden()
        port = self.obs.port
        self.obs.beenden()
        self.laeuft = False
        self.assertTrue(warte_bis(lambda: self.v.status is Status.GETRENNT))
        warte(600)  # einige Fehlversuche
        self.assertFalse(self.v.verbunden)
        self.assertEqual(self.v.meldung, self.E.texte.meldung_obs_nicht_offen)
        self.obs = FalschesObs(passwort="geheim")
        self.obs.server.close()
        self.assertTrue(self.obs.server.listen(QHostAddress.SpecialAddress.LocalHost, port))
        self.obs.port = port
        self.laeuft = True
        self.assertTrue(warte_bis(lambda: self.v.verbunden, 3000))

    def test_anfrage_zeitlimit(self):
        alt = vmod.ANFRAGE_ZEITLIMIT_MS
        vmod.ANFRAGE_ZEITLIMIT_MS = 200
        try:
            self.verbinden()
            self.obs.antworte = False
            ergebnis = []
            self.v.anfrage("GetStreamStatus", None, lambda *a: ergebnis.append(a))
            self.assertTrue(warte_bis(lambda: ergebnis, 2000))
            self.assertEqual(ergebnis[0], (False, {}, ZEITLIMIT_TEXT))
            warte(100)
            self.assertEqual(len(ergebnis), 1)  # genau einmal
        finally:
            vmod.ANFRAGE_ZEITLIMIT_MS = alt

    def test_offene_anfragen_bei_abbruch(self):
        self.verbinden()
        self.obs.antworte = False
        ergebnis = []
        self.v.anfrage("GetStreamStatus", None, lambda *a: ergebnis.append(a))
        warte(50)
        self.obs.alle_trennen()
        self.assertTrue(warte_bis(lambda: ergebnis))
        self.assertFalse(ergebnis[0][0])
        self.assertEqual(len(ergebnis), 1)

    def test_anfrage_ohne_verbindung(self):
        ergebnis = []
        self.v.anfrage("GetStreamStatus", None, lambda *a: ergebnis.append(a))
        self.assertTrue(warte_bis(lambda: ergebnis))
        self.assertEqual(ergebnis[0], (False, {}, self.E.texte.meldung_nicht_verbunden))

    def test_fehlerantwort(self):
        self.verbinden()
        ergebnis = []
        self.v.anfrage("GibtEsNicht", None, lambda *a: ergebnis.append(a))
        self.assertTrue(warte_bis(lambda: ergebnis))
        self.assertFalse(ergebnis[0][0])
        self.assertIn("Unknown", ergebnis[0][2])

    def test_rueckruf_mit_fehler_stoert_nicht(self):
        self.verbinden()
        def kaputt(*_):
            raise ValueError("absichtlich")
        self.v.anfrage("GetStreamStatus", None, kaputt)
        warte(100)
        self.assertTrue(self.v.verbunden)

    def test_unsinnige_nachricht(self):
        self.verbinden()
        for c in self.obs.clients:
            c.sendTextMessage("kein json {")
            c.sendTextMessage('{"op": 5}')
            c.sendTextMessage('[]')
        warte(100)
        self.assertTrue(self.v.verbunden)

    def test_neu_verbinden_knopf(self):
        self.verbinden()
        self.v.jetzt_neu_verbinden()
        self.assertTrue(warte_bis(lambda: self.v.verbunden))
        warte(100)
        self.assertEqual(len(self.obs.clients), 1)  # keine doppelte Verbindung

    def test_viele_neu_verbinden_klicks(self):
        self.v.starten()
        for _ in range(20):
            self.v.jetzt_neu_verbinden()
        self.assertTrue(warte_bis(lambda: self.v.verbunden))
        warte(200)
        self.assertEqual(len(self.obs.clients), 1)

    def test_beenden_stoppt_neuversuche(self):
        self.verbinden()
        self.v.beenden()
        warte(600)
        self.assertEqual(self.v.status, Status.GETRENNT)
        self.assertEqual(self.obs.clients, [])

    def test_anmeldung_haengt(self):
        alt = vmod.ANMELDE_ZEITLIMIT_MS
        vmod.ANMELDE_ZEITLIMIT_MS = 300
        try:
            self.obs.ohne_begruessung = True
            self.v.starten()
            self.assertTrue(warte_bis(lambda: self.v.status is Status.GETRENNT and self.v.meldung, 2000))
            self.assertEqual(self.v.meldung, self.E.texte.meldung_websocket_aus)
            self.obs.ohne_begruessung = False
            self.assertTrue(warte_bis(lambda: self.v.verbunden, 3000))
        finally:
            vmod.ANMELDE_ZEITLIMIT_MS = alt


class FalschesPasswortTest(Grundlage):
    passwort_rolli = "falsch"

    def test_falsches_passwort(self):
        self.v.starten()
        self.assertTrue(warte_bis(lambda: self.v.meldung == self.E.texte.meldung_passwort_falsch))
        self.assertFalse(self.v.verbunden)


class OhnePasswortTest(Grundlage):
    passwort_obs = None
    passwort_rolli = ""

    def test_ohne_passwort(self):
        self.verbinden()
        self.assertNotIn("authentication", self.obs.identify_daten)


class KeinObsTest(unittest.TestCase):
    def setUp(self):
        app()
        self.einst, self.E = obs_einstellungen()

    def pruefe(self, laeuft, erwartet):
        v = ObsVerbindung(self.einst, self.E.texte, zugang_finden=zugang(freier_port()), obs_laeuft=lambda: laeuft)
        v.starten()
        try:
            self.assertTrue(warte_bis(lambda: v.status is Status.GETRENNT and v.meldung))
            self.assertEqual(v.meldung, erwartet)
        finally:
            v.beenden()

    def test_obs_nicht_offen(self):
        self.pruefe(False, self.E.texte.meldung_obs_nicht_offen)

    def test_fernsteuerung_aus(self):
        self.pruefe(True, self.E.texte.meldung_websocket_aus)

    def test_kein_flackern_bei_neuversuchen(self):
        v = ObsVerbindung(self.einst, self.E.texte, zugang_finden=zugang(freier_port()), obs_laeuft=lambda: False)
        stati = []
        v.status_geaendert.connect(lambda s, m: stati.append(s))
        v.starten()
        try:
            self.assertTrue(warte_bis(lambda: v.status is Status.GETRENNT and v.meldung))
            warte(1000)  # ca. 4 Neuversuche
            self.assertEqual(stati, [Status.VERBINDE, Status.GETRENNT])
            v.jetzt_neu_verbinden()  # Knopf: zeigt wieder „Verbinde …“
            self.assertEqual(stati[-1], Status.VERBINDE)
        finally:
            v.beenden()


class AlteVersionTest(Grundlage):
    def setUp(self):
        super().setUp()
        self.obs.rpc_version = 2

    def test_zu_alt(self):
        self.v.starten()
        self.assertTrue(warte_bis(lambda: self.v.meldung == self.E.texte.meldung_obs_zu_alt))


class VorschauTest(Grundlage):
    def neue_vorschau(self):
        einst = self.E.vorschau.als_dict()
        einst["bilder_pro_sekunde"] = 20
        from openregie.einstellungen import Bereich
        return Vorschau(self.v, Bereich("vorschau", einst))

    def test_bilder_kommen(self):
        vorschau = self.neue_vorschau()
        bilder = []
        vorschau.neues_bild.connect(bilder.append)
        self.verbinden()
        self.assertTrue(warte_bis(lambda: len(bilder) >= 5, 3000))
        self.assertEqual(bilder[0].width(), 320)
        anfrage = [d for t, d in self.obs.anfragen if t == "GetSourceScreenshot"][0]
        self.assertEqual(anfrage["sourceName"], "Szene 1")
        self.assertEqual(anfrage["imageWidth"], self.E.vorschau.bildbreite)
        vorschau.anhalten()

    def test_folgt_szenenwechsel(self):
        vorschau = self.neue_vorschau()
        self.verbinden()
        self.obs.szene_wechseln("Pause")
        warte(300)
        letzte = [d for t, d in self.obs.anfragen if t == "GetSourceScreenshot"][-1]
        self.assertEqual(letzte["sourceName"], "Pause")
        vorschau.anhalten()

    def test_kein_stau_wenn_obs_langsam(self):
        vorschau = self.neue_vorschau()
        self.verbinden()
        warte(100)
        self.obs.antworte = False
        vorher = sum(1 for t, _ in self.obs.anfragen if t == "GetSourceScreenshot")
        warte(500)
        nachher = sum(1 for t, _ in self.obs.anfragen if t == "GetSourceScreenshot")
        self.assertLessEqual(nachher - vorher, 1)
        vorschau.anhalten()

    def test_ohne_verbindung_keine_anfragen(self):
        vorschau = self.neue_vorschau()
        warte(200)
        self.assertEqual(self.obs.anfragen, [])
        vorschau.anhalten()

    def test_szene_umbenannt(self):
        vorschau = self.neue_vorschau()
        self.verbinden()
        # Szene in OBS umbenannt, ohne dass ein Ereignis ankam
        self.obs.szenen["Neu"] = self.obs.szenen.pop("Szene 1")
        self.obs.szene = "Neu"
        self.assertTrue(warte_bis(lambda: self.v.szene == "Neu", 3000))
        vorschau.anhalten()

    def test_bild_aus_daten(self):
        self.assertIsNotNone(bild_aus_daten(testbild_daten()))
        self.assertIsNone(bild_aus_daten(""))
        self.assertIsNone(bild_aus_daten("data:image/jpg;base64,kaputt!!"))


class ZugangTest(unittest.TestCase):
    def test_aus_datei(self):
        import json, tempfile, pathlib
        with tempfile.TemporaryDirectory() as o:
            p = pathlib.Path(o) / "config.json"
            p.write_text(json.dumps({"server_port": 4460, "server_password": "abc", "auth_required": True,
                                     "server_enabled": False}))
            z = zmod.aus_obs_lesen([pathlib.Path(o) / "fehlt.json", p])
            self.assertEqual((z.port, z.passwort, z.passwort_noetig, z.server_an), (4460, "abc", True, False))

    def test_kaputte_oder_fehlende_datei(self):
        import tempfile, pathlib
        with tempfile.TemporaryDirectory() as o:
            p = pathlib.Path(o) / "config.json"
            p.write_text("{kaputt")
            z = zmod.aus_obs_lesen([p])
            self.assertEqual((z.port, z.passwort, z.server_an), (4455, "", None))

    def test_obs_laeuft(self):
        import tempfile, pathlib
        with tempfile.TemporaryDirectory() as o:
            proc = pathlib.Path(o)
            (proc / "12").mkdir(); (proc / "12" / "comm").write_text("bash\n")
            (proc / "self").mkdir()
            self.assertFalse(zmod.obs_laeuft(proc))
            (proc / "99").mkdir(); (proc / "99" / "comm").write_text("obs\n")
            self.assertTrue(zmod.obs_laeuft(proc))
        self.assertFalse(zmod.obs_laeuft(pathlib.Path("/gibt/es/nicht")))

    def test_vorrang_einstellungen(self):
        from openregie.einstellungen import Bereich
        z = zmod.ermitteln(Bereich("obs", {"port": 5000, "passwort": "eigen"}))
        self.assertEqual((z.port, z.passwort), (5000, "eigen"))

    def test_echte_obs_datei_lesbar(self):
        z = zmod.aus_obs_lesen()
        self.assertGreater(z.port, 0)


class AnmeldeschluesselTest(unittest.TestCase):
    def test_bekannter_wert(self):
        # Unabhängig nachgerechnet nach der OBS-WebSocket-Beschreibung
        import base64, hashlib
        pw, salz, aufgabe = "supersicher", "lM1GncleQOaCu9lT1yeUZhFYnqhsLLP1G5lAGo3ixaI=", "+IxH4CnCiqpX1rM9scsNynZzbOe4KhDeYcTNS3PDaeY="
        geheim = base64.b64encode(hashlib.sha256((pw + salz).encode()).digest()).decode()
        erwartet = base64.b64encode(hashlib.sha256((geheim + aufgabe).encode()).digest()).decode()
        self.assertEqual(vmod.anmeldeschluessel(pw, salz, aufgabe), erwartet)


if __name__ == "__main__":
    unittest.main()
