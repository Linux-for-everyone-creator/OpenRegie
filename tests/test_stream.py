"""Build 1.2.3: Stream direkt aus OpenRegie starten und beenden.

Zwei Ebenen:
  - StreamSteuerung (Zwischenschicht) mit dem nachgeahmten OBS – das sich so verhält wie das echte
    OBS 33 (ohne Stream-Key hängt es in „startet …“, Server weg = Fehlstart, 500/501, Neu-Verbinden).
  - Das Regiepult: Knopf, Nachfrage, ON AIR, Meldung – bedient durch Anklicken.
Jede Prüfung läuft mehrere Runden hintereinander (RUNDEN), damit nichts nur zufällig klappt.
"""

import unittest

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton

from openregie.automatik.motor import Automatik, Regel
from openregie.obs import stream as smod
from openregie.obs.quellen import ObsQuellen
from openregie.obs.stream import Knopf, StreamSteuerung, ziel_fehlt
from openregie.obs.verbindung import ObsVerbindung, Sendung
from openregie.oberflaeche.bausteine import gesperrt_text

from .falsches_internet import CONTENT
from .falsches_obs import FalschesObs
from .hilfen import app, groesste_pause_ms, obs_einstellungen, warte, warte_bis, zugang
from .test_automatik import UnoAttrappe
from . import test_fenster as tf  # über das Modul: sonst liefen dessen Tests hier noch einmal
from .test_fenster import klick

RUNDEN = 3


class StreamGrundlage(unittest.TestCase):
    def setUp(self):
        app()
        self.obs = FalschesObs(passwort="geheim")
        self.einst, self.E = obs_einstellungen()
        self.t = self.E.texte
        self.v = ObsVerbindung(self.einst, self.t, zugang_finden=zugang(self.obs.port), obs_laeuft=lambda: True)
        self.s = StreamSteuerung(self.v, self.t)
        self.knoepfe, self.meldungen, self.begonnen, self.beendet = [], [], [], []
        self.s.knopf_geaendert.connect(self.knoepfe.append)
        self.s.meldung_geaendert.connect(self.meldungen.append)
        self.v.live_begonnen.connect(lambda: self.begonnen.append(1))
        self.v.live_beendet.connect(lambda: self.beendet.append(1))
        self.v.starten()
        self.assertTrue(warte_bis(lambda: self.v.verbunden and self.v.szene, 3000))

    def tearDown(self):
        self.v.beenden()
        self.obs.beenden()
        warte(20)

    def anfragen(self, *typen):
        return [a for a, _ in self.obs.anfragen if a in typen]

    def starten_bis_live(self):
        self.assertIs(self.s.knopf, Knopf.STARTEN)
        self.s.starten()
        self.assertIs(self.s.knopf, Knopf.VERBINDE)  # sofort gesperrt – noch bevor OBS antwortet
        self.assertTrue(warte_bis(lambda: self.s.knopf is Knopf.BEENDEN, 3000), self.s.knopf)
        self.assertIs(self.v.sendung, Sendung.AN)

    def beenden_bis_aus(self):
        self.s.beenden()
        self.assertIs(self.s.knopf, Knopf.STOPPE)
        self.assertTrue(warte_bis(lambda: self.s.knopf is Knopf.STARTEN, 3000), self.s.knopf)
        self.assertIs(self.v.sendung, Sendung.AUS)


class StartenBeendenTest(StreamGrundlage):
    def test_starten_und_beenden(self):
        for runde in range(RUNDEN):
            with self.subTest(runde=runde):
                vorher = len(self.obs.anfragen)
                self.starten_bis_live()
                neu = [a for a, _ in self.obs.anfragen[vorher:] if a != "GetStreamStatus"]
                self.assertEqual(neu, ["GetStreamServiceSettings", "StartStream"])  # erst prüfen, dann starten
                self.assertTrue(self.obs.stream_aktiv)
                self.beenden_bis_aus()
                self.assertFalse(self.obs.stream_aktiv)
                self.assertEqual(self.s.meldung, "")
        self.assertEqual(len(self.anfragen("StartStream")), RUNDEN)
        self.assertEqual(len(self.anfragen("StopStream")), RUNDEN)
        self.assertEqual((len(self.begonnen), len(self.beendet)), (RUNDEN, RUNDEN))
        self.assertEqual(self.meldungen, [])

    def test_kein_doppelklick(self):
        for _ in range(RUNDEN):
            vorher = len(self.anfragen("StartStream"))
            for _ in range(5):
                self.s.starten()  # fünfmal schnell hintereinander
            self.assertTrue(warte_bis(lambda: self.s.knopf is Knopf.BEENDEN, 3000))
            self.s.starten()  # läuft schon: nichts
            warte(100)
            self.assertEqual(len(self.anfragen("StartStream")), vorher + 1)
            vorher = len(self.anfragen("StopStream"))
            for _ in range(5):
                self.s.beenden()
            self.assertTrue(warte_bis(lambda: self.s.knopf is Knopf.STARTEN, 3000))
            self.s.beenden()  # läuft nicht: nichts
            warte(100)
            self.assertEqual(len(self.anfragen("StopStream")), vorher + 1)

    def test_start_und_stopp_direkt_in_obs(self):
        """Der Knopf zeigt den echten Zustand – auch wenn in OBS selbst gestartet/gestoppt wird."""
        for _ in range(RUNDEN):
            self.obs.stream_starten()
            self.assertTrue(warte_bis(lambda: self.s.knopf is Knopf.BEENDEN, 3000))
            self.obs.stream_stoppen()
            self.assertTrue(warte_bis(lambda: self.s.knopf is Knopf.STARTEN, 3000))
        self.assertEqual(self.anfragen("StartStream", "StopStream"), [])
        self.assertEqual(self.meldungen, [])
        # gemischt: in OpenRegie starten, in OBS stoppen – und umgekehrt
        self.starten_bis_live()
        self.obs.stream_stoppen()
        self.assertTrue(warte_bis(lambda: self.s.knopf is Knopf.STARTEN, 3000))
        self.obs.stream_starten()
        self.assertTrue(warte_bis(lambda: self.s.knopf is Knopf.BEENDEN, 3000))
        self.beenden_bis_aus()
        self.assertEqual(self.meldungen, [])

    def test_schon_live_beim_verbinden(self):
        self.v.beenden()
        self.obs.stream_aktiv = True
        self.v.starten()
        self.assertTrue(warte_bis(lambda: self.s.knopf is Knopf.BEENDEN, 3000))

    def test_laeuft_schon_ohne_dass_wir_es_wissen(self):
        """OBS antwortet „läuft schon“ (500): kein Fehler, der Knopf holt sich den echten Zustand."""
        self.obs.stream_aktiv = True  # ohne Ereignis
        self.s.starten()
        self.assertTrue(warte_bis(lambda: self.s.knopf is Knopf.BEENDEN, 3000))
        self.assertEqual(self.s.meldung, "")

    def test_beenden_wenn_obs_schon_gestoppt_hat(self):
        """OBS antwortet „läuft nicht“ (501): kein Fehler, Knopf zeigt wieder „Stream starten“."""
        self.starten_bis_live()
        self.obs.stream_aktiv = False  # ohne Ereignis gestoppt
        self.s.beenden()
        self.assertTrue(warte_bis(lambda: self.s.knopf is Knopf.STARTEN, 3000))
        self.assertEqual(self.s.meldung, "")


class FehlerTest(StreamGrundlage):
    def test_ohne_stream_key_wird_gar_nicht_gestartet(self):
        """Echtes OBS ohne Key: hängt in „startet …“ und zeigt ein eigenes Fehlerfenster.
        Darum schickt OpenRegie dann gar kein StartStream."""
        self.obs.dienst["streamServiceSettings"]["key"] = ""
        self.obs.start_verhalten = "haengt"
        for _ in range(RUNDEN):
            self.s.starten()
            self.assertTrue(warte_bis(lambda: self.s.knopf is Knopf.STARTEN, 3000))
            self.assertEqual(self.s.meldung, self.t.stream_meldung_kein_key)
        self.assertEqual(self.anfragen("StartStream"), [])
        self.assertIs(self.v.sendung, Sendung.AUS)
        self.assertEqual(self.meldungen, [self.t.stream_meldung_kein_key])  # nie doppelt
        # Key eingetragen → klappt, Meldung verschwindet
        self.obs.dienst["streamServiceSettings"]["key"] = "live_neu"
        self.obs.start_verhalten = "ok"
        self.starten_bis_live()
        self.assertEqual(self.s.meldung, "")

    def test_eigener_server_ohne_adresse(self):
        self.obs.dienst = {"streamServiceType": "rtmp_custom", "streamServiceSettings": {"server": "", "key": ""}}
        self.s.starten()
        self.assertTrue(warte_bis(lambda: self.s.meldung == self.t.stream_meldung_kein_server, 3000))
        self.assertEqual(self.anfragen("StartStream"), [])

    def test_eigener_server_mit_key_in_der_adresse(self):
        self.obs.dienst = {"streamServiceType": "rtmp_custom",
                           "streamServiceSettings": {"server": "rtmp://server/live/geheim", "key": ""}}
        self.starten_bis_live()

    def test_ziel_fehlt(self):
        self.assertEqual(ziel_fehlt("rtmp_common", {"service": "Twitch", "key": " "}), "key")
        self.assertEqual(ziel_fehlt("rtmp_common", {"service": "Twitch", "key": "abc"}), "")
        self.assertEqual(ziel_fehlt("rtmp_custom", {"server": "", "key": "abc"}), "server")
        self.assertEqual(ziel_fehlt("rtmp_custom", {"server": "rtmp://x/y", "key": ""}), "")
        self.assertEqual(ziel_fehlt("whip_custom", {"server": ""}), "server")
        self.assertEqual(ziel_fehlt("etwas_neues", {}), "")  # unbekannt: OBS entscheidet

    def test_fehlstart_server_nicht_erreichbar(self):
        self.obs.start_verhalten = "fehlstart"
        for _ in range(RUNDEN):
            self.s.starten()
            self.assertTrue(warte_bis(lambda: self.s.knopf is Knopf.STARTEN, 3000))  # gleich nochmal versuchbar
            self.assertEqual(self.s.meldung, self.t.stream_meldung_fehlstart)
            self.assertIs(self.v.sendung, Sendung.AUS)
        self.assertEqual(self.begonnen, [])
        self.assertEqual(self.beendet, [])  # ein Fehlstart ist kein „Stream endet“
        self.obs.start_verhalten = "ok"
        self.starten_bis_live()
        self.assertEqual(self.s.meldung, "")

    def test_haengt_beim_verbinden_zeitlimit(self):
        alt = smod.START_ZEITLIMIT_MS
        smod.START_ZEITLIMIT_MS = 300
        try:
            self.obs.start_verhalten = "haengt"
            for _ in range(RUNDEN):
                self.s.starten()
                self.assertTrue(warte_bis(lambda: self.v.sendung is Sendung.STARTET, 3000))
                self.assertIs(self.s.knopf, Knopf.VERBINDE)
                self.assertTrue(warte_bis(lambda: self.s.knopf is Knopf.STARTEN, 3000))
                self.assertEqual(self.s.meldung, self.t.stream_meldung_zeitlimit)
                self.assertIs(self.v.sendung, Sendung.AUS)  # „startet …“ hängt nicht für immer
        finally:
            smod.START_ZEITLIMIT_MS = alt

    def test_start_abgelehnt(self):
        self.obs.start_verhalten = "abgelehnt"
        self.s.starten()
        self.assertTrue(warte_bis(lambda: self.s.meldung == self.t.stream_meldung_start_fehler, 3000))
        self.assertIs(self.s.knopf, Knopf.STARTEN)

    def test_ohne_verbindung_gesperrt(self):
        self.v.beenden()
        self.assertTrue(warte_bis(lambda: self.s.knopf is Knopf.GESPERRT))
        self.s.starten()
        self.s.beenden()
        warte(100)
        self.assertEqual(self.anfragen("StartStream", "StopStream"), [])

    def test_verbindung_weg_beim_verbinden(self):
        self.obs.start_verhalten = "haengt"
        for _ in range(RUNDEN):
            self.s.starten()
            self.assertTrue(warte_bis(lambda: self.v.sendung is Sendung.STARTET, 3000))
            self.obs.alle_trennen()
            self.assertTrue(warte_bis(lambda: self.s.knopf is Knopf.GESPERRT, 3000))
            # Kein „Fehlstart“ – die Meldungsleiste sagt schon „Verbindung zu OBS weg“
            self.assertEqual(self.s.meldung, "")
            self.assertTrue(warte_bis(lambda: self.s.knopf is Knopf.STARTEN, 3000))  # neu verbunden
        self.assertEqual(self.meldungen, [])

    def test_verbindung_weg_beim_pruefen(self):
        """Verbindung bricht ab, bevor OBS die Prüfung beantwortet: kein Start, kein Hängen."""
        self.obs.antworte = False
        self.s.starten()
        self.assertIs(self.s.knopf, Knopf.VERBINDE)
        self.obs.antworte = True
        self.obs.alle_trennen()
        self.assertTrue(warte_bis(lambda: self.s.knopf is Knopf.GESPERRT, 3000))
        self.assertTrue(warte_bis(lambda: self.s.knopf is Knopf.STARTEN, 3000))
        self.assertEqual(self.anfragen("StartStream"), [])

    def test_verbindung_weg_waehrend_live(self):
        for _ in range(RUNDEN):
            self.starten_bis_live()
            self.obs.alle_trennen()
            self.assertTrue(warte_bis(lambda: self.s.knopf is Knopf.GESPERRT, 3000))
            # Nach dem Neuverbinden nie kurz „Stream starten“, solange OBS noch nichts gesagt hat
            gesehen = []
            self.s.knopf_geaendert.connect(gesehen.append)
            self.assertTrue(warte_bis(lambda: self.s.knopf is Knopf.BEENDEN, 3000))  # läuft noch
            self.s.knopf_geaendert.disconnect(gesehen.append)
            self.assertNotIn(Knopf.STARTEN, gesehen)
            self.beenden_bis_aus()
        # OBS war nur kurz weg – der Stream lief durch: kein zusätzliches „begonnen/beendet“
        self.assertEqual((len(self.begonnen), len(self.beendet)), (RUNDEN, RUNDEN))
        self.assertEqual(self.meldungen, [])

    def test_stream_endet_waehrend_obs_weg_ist(self):
        self.starten_bis_live()
        self.obs.alle_trennen()
        self.obs.stream_aktiv = False  # inzwischen in OBS gestoppt
        self.assertTrue(warte_bis(lambda: self.s.knopf is Knopf.GESPERRT, 3000))
        self.assertTrue(warte_bis(lambda: self.s.knopf is Knopf.STARTEN, 3000))
        self.assertEqual(len(self.beendet), 1)  # nach dem Neuverbinden: jetzt wirklich zu Ende

    def test_verbindet_neu_zu_twitch(self):
        """Live, dann bricht die Verbindung zu Twitch ab: ON AIR nicht rot, Beenden geht weiter."""
        for _ in range(RUNDEN):
            self.starten_bis_live()
            self.obs.stream_wackeln()
            self.assertTrue(warte_bis(lambda: self.v.sendung is Sendung.WIEDER, 3000))
            self.assertIs(self.s.knopf, Knopf.BEENDEN)
            self.obs.stream_wieder_da()
            self.assertTrue(warte_bis(lambda: self.v.sendung is Sendung.AN, 3000))
            self.obs.stream_wackeln()
            self.assertTrue(warte_bis(lambda: self.v.sendung is Sendung.WIEDER, 3000))
            self.beenden_bis_aus()  # auch während „verbindet neu“ beendbar
        self.assertEqual((len(self.begonnen), len(self.beendet)), (RUNDEN, RUNDEN))

    def test_abfrage_kennt_neu_verbinden(self):
        self.starten_bis_live()
        self.obs.stream_wackelt = True  # ohne Ereignis
        self.v._letztes_stream_ereignis -= 10  # das letzte Ereignis ist lange her
        self.v.stream_status_pruefen()
        self.assertTrue(warte_bis(lambda: self.v.sendung is Sendung.WIEDER, 3000))

    def test_obs_haengt_nach_dem_stoppen_kurz_nach(self):
        """Echtes OBS 33: direkt nach „gestoppt“ sagt die Abfrage noch ~130 ms „läuft“. Fällt die
        regelmäßige Abfrage genau da hinein, darf ON AIR nicht wieder angehen und keine Regel auslösen."""
        self.obs.nachlauf_s = 1.0
        for _ in range(RUNDEN):
            self.starten_bis_live()
            self.beenden_bis_aus()
            for _ in range(5):
                self.v.stream_status_pruefen()  # Abfrage genau im Nachlauf
                warte(30)
            self.assertIs(self.v.sendung, Sendung.AUS)
            self.assertIs(self.s.knopf, Knopf.STARTEN)
            warte(1000)  # Nachlauf vorbei
        self.assertEqual((len(self.begonnen), len(self.beendet)), (RUNDEN, RUNDEN))

    def test_abfrage_bleibt_sicherheitsnetz(self):
        """Geht ein Ereignis verloren, korrigiert die Abfrage – sobald das letzte Ereignis etwas her ist."""
        self.starten_bis_live()
        self.obs.stream_aktiv = False  # ohne Ereignis aus
        self.v.stream_status_pruefen()
        warte(200)
        self.assertIs(self.v.sendung, Sendung.AN)  # eben noch „gestartet“ gemeldet: das gilt kurz
        self.v._letztes_stream_ereignis -= 10
        self.v.stream_status_pruefen()
        self.assertTrue(warte_bis(lambda: self.v.sendung is Sendung.AUS, 3000))

    def test_meldung_wegklicken(self):
        self.obs.start_verhalten = "fehlstart"
        self.s.starten()
        self.assertTrue(warte_bis(lambda: self.s.meldung != "", 3000))
        self.s.meldung_weg()
        self.assertEqual(self.s.meldung, "")


class WennDannTest(StreamGrundlage):
    """„Stream startet/endet“-Regeln lösen nur bei echten Übergängen aus."""

    def test_regeln_nur_bei_echten_uebergaengen(self):
        import tempfile
        from pathlib import Path
        ordner = tempfile.TemporaryDirectory()
        q = ObsQuellen(self.v, self.t, self.E.quellen)
        a = Automatik(self.t, self.v, q, UnoAttrappe(), datei=Path(ordner.name) / "a.json")
        try:
            a.laden()
            self.assertTrue(warte_bis(lambda: a.geladen, 2000))
            a.regel_speichern(Regel("stream_startet", "overlay_ein", dann_wert="p1/o1"))
            a.regel_speichern(Regel("stream_endet", "overlay_aus", dann_wert="p1/o1"))
            uno = a._uno
            self.obs.start_verhalten = "fehlstart"
            self.s.starten()
            self.assertTrue(warte_bis(lambda: self.s.meldung != "", 3000))
            warte(100)
            self.assertEqual(uno.befehle, [])  # Fehlstart: weder „startet“ noch „endet“
            self.obs.start_verhalten = "ok"
            self.starten_bis_live()
            self.assertTrue(warte_bis(lambda: uno.befehle == [("Bauchbinde", True)], 3000))
            self.obs.stream_wackeln()
            warte(100)
            self.obs.stream_wieder_da()
            warte(2300)  # länger als der Schutz vor Endlosschleifen (2 s)
            self.assertEqual(uno.befehle, [("Bauchbinde", True)])  # wieder da ≠ neu gestartet
            self.beenden_bis_aus()
            self.assertTrue(warte_bis(lambda: uno.befehle == [("Bauchbinde", True), ("Bauchbinde", False)], 3000))
        finally:
            a.beenden()
            ordner.cleanup()


# ---------------------------------------------------------------------------
#  Das Regiepult
# ---------------------------------------------------------------------------
class KnopfImFensterTest(tf.Grundlage):
    def setUp(self):
        super().setUp()
        self.k = self.f.knopf_stream
        self.t = self.E.texte
        self.fragen = []

    def verbinden(self):
        self.m.starten()
        self.assertTrue(warte_bis(lambda: self.v.verbunden, 3000))
        self.assertTrue(warte_bis(lambda: self.k.isEnabled(), 3000))

    def antwort(self, ja):
        self.f.stream_knopf.frage_beenden = lambda: self.fragen.append(1) or ja

    def test_ohne_verbindung_grau_mit_grund(self):
        self.assertFalse(self.k.isEnabled())
        self.assertEqual(self.k.text(), self.t.knopf_stream_starten)
        self.assertEqual(gesperrt_text(self.k), self.t.gesperrt_stream)

    def test_starten_ohne_nachfrage_beenden_mit(self):
        self.verbinden()
        for _ in range(RUNDEN):
            self.antwort(True)
            self.assertEqual(self.f.on_air.text.text(), self.t.on_air_aus)
            klick(self.k)  # ohne Nachfrage
            self.assertFalse(self.k.isEnabled())
            self.assertEqual(self.k.text(), self.t.knopf_stream_verbinde)
            self.assertEqual(gesperrt_text(self.k), self.t.gesperrt_stream_verbinde)
            self.assertTrue(warte_bis(lambda: self.f.on_air.text.text() == self.t.on_air_an, 3000))
            self.assertIn(self.E.farben.on_air_an, self.f.on_air.styleSheet())
            self.assertTrue(self.f.vorschaubild.live)
            self.assertEqual(self.k.text(), self.t.knopf_stream_beenden)
            self.assertEqual(self.k.objectName(), "stream_beenden")
            self.assertEqual(self.fragen, [])
            klick(self.k)
            self.assertEqual(self.fragen, [1])
            self.assertTrue(warte_bis(lambda: self.f.on_air.text.text() == self.t.on_air_aus, 3000))
            self.assertFalse(self.f.vorschaubild.live)
            self.assertEqual(self.k.text(), self.t.knopf_stream_starten)
            self.fragen.clear()

    def test_nachfrage_abbrechen(self):
        self.verbinden()
        klick(self.k)
        self.assertTrue(warte_bis(lambda: self.obs.stream_aktiv and self.k.isEnabled(), 3000))
        self.antwort(False)  # „Weiter streamen“
        for _ in range(RUNDEN):
            klick(self.k)
            warte(200)
            self.assertTrue(self.obs.stream_aktiv)
            self.assertEqual(self.f.on_air.text.text(), self.t.on_air_an)
            self.assertEqual(self.k.text(), self.t.knopf_stream_beenden)
        self.assertEqual(len(self.fragen), RUNDEN)
        self.assertNotIn("StopStream", [a for a, _ in self.obs.anfragen])

    def test_echte_nachfrage_weiter_streamen_ist_vorgewaehlt(self):
        """Die echte Nachfrage: zwei große Knöpfe, „Weiter streamen“ vorgewählt, Esc = weiter streamen."""
        self.verbinden()
        klick(self.k)
        self.assertTrue(warte_bis(lambda: self.obs.stream_aktiv and self.k.isEnabled(), 3000))
        gesehen = {}

        def antworten(knopf_text):
            def los():
                box = QApplication.activeModalWidget()
                if not isinstance(box, QMessageBox):
                    QTimer.singleShot(20, los)
                    return
                gesehen["text"] = box.text()
                gesehen["vorgewaehlt"] = box.defaultButton().text()
                gesehen["knoepfe"] = [(k.text(), k.height()) for k in box.findChildren(QPushButton)]
                next(k for k in box.buttons() if k.text() == knopf_text).click()
            QTimer.singleShot(20, los)

        antworten(self.t.knopf_stream_beenden_nein)
        klick(self.k)
        warte(200)
        self.assertTrue(self.obs.stream_aktiv)
        self.assertEqual(gesehen["text"], self.t.frage_stream_beenden)
        self.assertEqual(gesehen["vorgewaehlt"], self.t.knopf_stream_beenden_nein)
        for text, hoehe in gesehen["knoepfe"]:
            self.assertGreaterEqual(hoehe, self.E.groessen.knopf_hoehe, text)
        antworten(self.t.knopf_stream_beenden_ja)
        klick(self.k)
        self.assertTrue(warte_bis(lambda: not self.obs.stream_aktiv, 3000))
        self.assertTrue(warte_bis(lambda: self.k.text() == self.t.knopf_stream_starten, 3000))

    def test_waehrend_der_nachfrage_in_obs_gestoppt(self):
        """Steht die Frage noch offen und der Stream endet in OBS: „Ja“ schickt dann kein StopStream."""
        self.verbinden()
        klick(self.k)
        self.assertTrue(warte_bis(lambda: self.obs.stream_aktiv and self.k.isEnabled(), 3000))

        def frage():
            self.obs.stream_stoppen()
            warte_bis(lambda: self.v.sendung is Sendung.AUS, 3000)
            return True
        self.f.stream_knopf.frage_beenden = frage
        klick(self.k)
        warte(200)
        self.assertNotIn("StopStream", [a for a, _ in self.obs.anfragen])
        self.assertEqual(self.k.text(), self.t.knopf_stream_starten)

    def test_on_air_nur_rot_wenn_wirklich_live(self):
        self.verbinden()
        self.obs.start_verhalten = "haengt"
        klick(self.k)
        self.assertTrue(warte_bis(lambda: self.f.on_air.text.text() == self.t.on_air_startet, 3000))
        self.assertNotIn(self.E.farben.on_air_an, self.f.on_air.styleSheet())
        self.assertFalse(self.f.vorschaubild.live)
        self.assertFalse(self.k.isEnabled())
        self.obs.stream_starten()  # jetzt wirklich live
        self.assertTrue(warte_bis(lambda: self.f.on_air.text.text() == self.t.on_air_an, 3000))
        self.obs.stream_wackeln()  # Verbindung zu Twitch weg
        self.assertTrue(warte_bis(lambda: self.f.on_air.text.text() == self.t.on_air_wieder, 3000))
        self.assertNotIn(self.E.farben.on_air_an, self.f.on_air.styleSheet())
        self.assertFalse(self.f.vorschaubild.live)
        self.assertTrue(self.k.isEnabled())  # beenden geht trotzdem
        self.obs.stream_wieder_da()
        self.assertTrue(warte_bis(lambda: self.f.on_air.text.text() == self.t.on_air_an, 3000))

    def test_kein_stream_key_meldung_und_verstanden(self):
        self.verbinden()
        self.obs.dienst["streamServiceSettings"]["key"] = ""
        for _ in range(RUNDEN):
            klick(self.k)
            self.assertTrue(warte_bis(lambda: self.f.meldungsleiste.isVisible(), 3000))
            self.assertEqual(self.f.meldungstext.text(), self.t.stream_meldung_kein_key)
            self.assertTrue(self.f.knopf_verstanden.isVisible())
            self.assertTrue(self.f.knopf_obs_starten.isHidden())
            self.assertTrue(self.k.isEnabled())
            klick(self.f.knopf_verstanden)
            self.assertTrue(self.f.meldungsleiste.isHidden())
        self.assertNotIn("StartStream", [a for a, _ in self.obs.anfragen])

    def test_obs_weg_zeigt_verbindungsmeldung_statt_stream_meldung(self):
        self.verbinden()
        self.obs.dienst["streamServiceSettings"]["key"] = ""
        klick(self.k)
        self.assertTrue(warte_bis(lambda: self.f.knopf_verstanden.isVisible(), 3000))
        self.obs.alle_trennen()
        self.assertTrue(warte_bis(lambda: self.f.meldungstext.text() == self.t.meldung_verbindung_weg, 3000))
        self.assertTrue(self.f.knopf_verstanden.isHidden())
        self.assertFalse(self.k.isEnabled())
        self.assertEqual(gesperrt_text(self.k), self.t.gesperrt_stream)

    def test_knopf_bleibt_gleich_breit_und_kopfleiste_verrutscht_nicht(self):
        """Mit dem Joystick darf nichts unter dem Zeiger wegrutschen – bei 1600 und 1920 Pixeln."""
        self.verbinden()
        for breite, hoehe in ((1600, 900), (1920, 1080)):
            self.f.resize(breite, hoehe)
            warte(400)  # bis alles fertig angeordnet ist
            orte = set()
            for sendung in (Sendung.AUS, Sendung.STARTET, Sendung.AN, Sendung.WIEDER, Sendung.STOPPT, Sendung.AUS):
                self.v._sendung_setzen(sendung)
                warte(30)
                orte.add((self.k.geometry().getRect(), self.f.on_air.geometry().getRect(),
                          self.f.uhr.geometry().getRect()))
            self.assertEqual(len(orte), 1, orte)
            (kx, _, kb, kh), (ox, _, ob, _), (ux, _, ub, _) = orte.pop()
            self.assertGreaterEqual(kh, self.E.groessen.knopf_hoehe)
            self.assertLessEqual(kx + kb, ox)  # Knopf und ON AIR überlappen nicht
            self.assertLessEqual(ox + ob, ux)
            self.assertLessEqual(ux + ub, self.f.width())  # Uhr ganz zu sehen
            self.assertGreaterEqual(self.f.knopf_wenn_dann.width(),
                                    self.f.knopf_wenn_dann.sizeHint().width())  # nichts abgeschnitten

    def test_flussig_beim_starten_und_beenden(self):
        """Ein Regiepult friert nie ein – auch nicht beim Starten und Beenden."""
        self.verbinden()
        self.antwort(True)
        klick(self.k)
        self.assertLess(groesste_pause_ms(300), 150)
        self.assertTrue(warte_bis(lambda: self.k.text() == self.t.knopf_stream_beenden, 3000))
        klick(self.k)
        self.assertLess(groesste_pause_ms(300), 150)
        self.assertTrue(warte_bis(lambda: self.k.text() == self.t.knopf_stream_starten, 3000))

    def test_schliessen_waehrend_verbindet_neu_fragt_nach(self):
        self.verbinden()
        self.m.selbst_gestartet = True  # so tun, als hätte OpenRegie OBS gestartet
        klick(self.k)
        self.assertTrue(warte_bis(lambda: self.obs.stream_aktiv and self.k.isEnabled(), 3000))
        self.obs.stream_wackeln()
        self.assertTrue(warte_bis(lambda: self.v.sendung is Sendung.WIEDER, 3000))
        fragen = []
        self.f.frage_beenden = lambda: fragen.append(1) or False
        self.f.close()
        self.assertEqual(fragen, [1])
        self.assertTrue(self.f.isVisible())


class CountdownMitStreamTest(tf.EinzelUnoFensterTest):
    """Countdown und Uno-Overlays dürfen durch den Stream-Knopf nicht kaputtgehen."""

    def setUp(self):
        super().setUp()
        self.m.starten()
        self.assertTrue(warte_bis(lambda: self.v.verbunden and self.f.knopf_stream.isEnabled(), 3000))

    def test_countdown_und_overlay_waehrend_stream(self):
        t, k = self.E.texte, self.f.knopf_stream
        self.f.stream_knopf.frage_beenden = lambda: True
        for _ in range(2):
            klick(self.b.start)
            self.assertTrue(warte_bis(lambda: self.b.countdown_zustand.text() == t.countdown_laeuft, 3000))
            klick(k)  # Stream starten, während der Countdown läuft
            self.assertTrue(warte_bis(lambda: k.text() == t.knopf_stream_beenden, 3000))
            self.assertTrue(self.e.werte[CONTENT]["Timer"]["isRunning"])  # läuft weiter
            klick(self.b.einblenden)
            self.assertTrue(warte_bis(lambda: self.e.komplett_sichtbar(), 3000))
            vorher = self.b.zeit.text()
            warte(1300)
            self.assertNotEqual(self.b.zeit.text(), vorher)  # zählt sichtbar weiter
            klick(k)  # Stream beenden
            self.assertTrue(warte_bis(lambda: k.text() == t.knopf_stream_starten, 3000))
            self.assertTrue(self.e.werte[CONTENT]["Timer"]["isRunning"])  # Countdown unberührt
            self.assertTrue(self.e.komplett_sichtbar())  # Overlay unberührt
            klick(self.b.ausblenden)
            self.assertTrue(warte_bis(lambda: self.e.ganz_aus(), 3000))
            klick(self.b.pause)
            self.assertTrue(warte_bis(lambda: self.b.countdown_zustand.text() == t.countdown_pausiert, 3000))
            klick(self.b.zurueck)
            self.assertTrue(warte_bis(lambda: self.b.zeit.text() == "05:00", 3000))

    def test_fehlermeldung_stoert_den_countdown_nicht(self):
        t = self.E.texte
        self.obs.dienst["streamServiceSettings"]["key"] = ""
        klick(self.f.knopf_stream)
        self.assertTrue(warte_bis(lambda: self.f.knopf_verstanden.isVisible(), 3000))
        klick(self.b.start)
        self.assertTrue(warte_bis(lambda: self.b.countdown_zustand.text() == t.countdown_laeuft, 3000))
        self.assertTrue(self.b.start.isVisible() and self.b.pause.isEnabled())
        klick(self.b.pause)
        self.assertTrue(warte_bis(lambda: self.b.countdown_zustand.text() == t.countdown_pausiert, 3000))


# Die Countdown-Prüfungen aus test_fenster sollen hier nicht noch einmal laufen – nur die neuen
for _name in [n for n in vars(tf.EinzelUnoFensterTest) if n.startswith("test_")]:
    setattr(CountdownMitStreamTest, _name, None)


if __name__ == "__main__":
    unittest.main()
