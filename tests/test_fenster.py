"""Prüft das Fenster so, wie es bedient wird: durch Anklicken der Knöpfe."""

import unittest

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from rolliregie import einstellungen
from rolliregie.obs.verbindung import ObsVerbindung, Sendung, Status
from rolliregie.obs.vorschau import Vorschau
from rolliregie.oberflaeche.countdown_bereich import schritt_text
from rolliregie.oberflaeche.hauptfenster import Hauptfenster
from rolliregie.titel.countdown import Countdown, Zustand
from rolliregie.web.server import LokaleWebseite

from .falsches_obs import FalschesObs
from .hilfen import app, obs_einstellungen, warte, warte_bis, zugang


def klick(k):
    assert k.isVisible() and k.isEnabled(), k.text()
    QTest.mouseClick(k, Qt.MouseButton.LeftButton)


class FensterTest(unittest.TestCase):
    def setUp(self):
        app()
        self.E = einstellungen.lade()
        self.obs = FalschesObs(passwort="geheim")
        oe, _ = obs_einstellungen()
        self.v = ObsVerbindung(oe, self.E.texte, zugang_finden=zugang(self.obs.port), obs_laeuft=lambda: True)
        self.vs = Vorschau(self.v, self.E.vorschau)
        self.cd = Countdown("Countdown", 120, 5999)
        self.web = LokaleWebseite(0, self.cd, self.E.countdown)
        self.web.starten()
        self.f = Hauptfenster(self.E, self.v, self.vs, self.cd, self.web.countdown_adresse)
        self.f.resize(1600, 900)
        self.f.show()
        self.b = self.f.countdown_bereich

    def tearDown(self):
        self.vs.anhalten()
        self.v.beenden()
        self.obs.beenden()
        self.web.beenden()
        self.f.close()
        self.f.deleteLater()
        warte(20)

    def test_build_anzeige(self):
        self.assertEqual(self.f.build.text(), "Rolliregie Build " + einstellungen.build_nummer())
        self.assertTrue(self.f.build.isVisible())

    def test_titelliste(self):
        self.assertEqual(list(self.f.titelliste.knoepfe), ["countdown"])
        k = self.f.titelliste.knoepfe["countdown"]
        self.assertTrue(k.isChecked())
        klick(k)
        self.assertTrue(k.isChecked())  # zweiter Klick wählt nicht ab
        self.assertIs(self.f.bedienfelder.currentWidget(), self.b)

    def test_countdown_bedienen(self):
        t = self.E.texte
        self.assertEqual(self.b.anzeige.text(), "02:00")
        self.assertFalse(self.b.pause.isEnabled())
        self.assertFalse(self.b.stopp.isEnabled())
        klick(self.b.plus_gross)
        self.assertEqual(self.b.anzeige.text(), "03:00")
        klick(self.b.minus_klein)
        self.assertEqual(self.b.anzeige.text(), "02:50")
        klick(self.b.start)
        self.assertEqual(self.cd.zustand, Zustand.LAEUFT)
        self.assertFalse(self.b.start.isEnabled())
        self.assertEqual(self.b.zustand_text.text(), t.countdown_zustand_laeuft)
        warte(1200)
        self.assertEqual(self.b.anzeige.text(), "02:49")
        klick(self.b.pause)
        self.assertEqual(self.b.start.text(), t.knopf_weiter)
        self.assertEqual(self.b.zustand_text.text(), t.countdown_zustand_pausiert)
        klick(self.b.start)
        self.assertEqual(self.b.start.text(), t.knopf_start)
        klick(self.b.stopp)
        self.assertEqual(self.b.anzeige.text(), "02:50")
        self.assertEqual(self.cd.zustand, Zustand.BEREIT)

    def test_minus_bis_null(self):
        for _ in range(2):
            klick(self.b.minus_gross)
        self.assertEqual(self.b.anzeige.text(), "00:00")
        self.assertFalse(self.b.minus_gross.isEnabled())
        self.assertFalse(self.b.minus_klein.isEnabled())
        self.assertFalse(self.b.start.isEnabled())  # bei 0 nichts zu starten
        klick(self.b.plus_klein)
        self.assertTrue(self.b.start.isEnabled())

    def test_ablauf_im_fenster(self):
        self.cd.stopp()
        for _ in range(2):
            klick(self.b.minus_gross)
        klick(self.b.plus_klein)  # 10 Sekunden
        self.cd._uhr = lambda: 0.0
        klick(self.b.start)
        self.cd._uhr = lambda: 11.0
        warte(250)
        self.assertEqual(self.b.zustand_text.text(), self.E.texte.countdown_zustand_abgelaufen)
        self.assertEqual(self.b.anzeige.text(), "00:00")
        self.assertTrue(self.b.start.isEnabled())
        self.assertTrue(self.b.stopp.isEnabled())
        self.assertFalse(self.b.pause.isEnabled())

    def test_schritt_text(self):
        self.assertEqual(schritt_text(60, True), "+1 Min")
        self.assertEqual(schritt_text(10, False), "−10 Sek")
        self.assertEqual(schritt_text(90, True), "+90 Sek")

    def test_verbindung_und_on_air(self):
        self.assertTrue(self.f.meldungsleiste.isHidden() or not self.v.meldung)
        self.v.starten()
        self.assertTrue(warte_bis(lambda: self.v.verbunden))
        self.assertEqual(self.f.verbindungsanzeige.text.text(), self.E.texte.status_verbunden)
        self.assertTrue(self.f.meldungsleiste.isHidden())
        self.assertEqual(self.f.on_air.text(), self.E.texte.on_air_aus)
        self.obs.stream_starten()
        self.assertTrue(warte_bis(lambda: self.f.on_air.text() == self.E.texte.on_air_an))
        self.assertIn(self.E.farben.on_air_an, self.f.on_air.styleSheet())
        self.obs.stream_stoppen()
        self.assertTrue(warte_bis(lambda: self.f.on_air.text() == self.E.texte.on_air_aus))

    def test_vorschau_im_fenster(self):
        self.v.starten()
        self.assertTrue(warte_bis(lambda: self.f.vorschaubild.hat_bild(), 3000))
        self.assertTrue(warte_bis(lambda: self.f.szenenname.text() == "Szene 1"))
        self.obs.alle_trennen()
        self.assertTrue(warte_bis(lambda: not self.f.vorschaubild.hat_bild()))
        self.assertTrue(warte_bis(lambda: self.f.meldungsleiste.isVisible()))
        self.assertEqual(self.f.meldungstext.text(), self.E.texte.meldung_verbindung_weg)
        self.assertTrue(warte_bis(lambda: self.f.vorschaubild.hat_bild(), 3000))  # kommt von selbst wieder

    def test_on_air_aus_bei_abbruch(self):
        self.v.starten()
        self.assertTrue(warte_bis(lambda: self.v.verbunden))
        self.obs.stream_starten()
        self.assertTrue(warte_bis(lambda: self.f.on_air.sendung is Sendung.AN))
        self.obs.beenden()
        self.assertTrue(warte_bis(lambda: self.f.on_air.sendung is Sendung.AUS))
        self.assertEqual(self.f.verbindungsanzeige.text.text(), self.E.texte.status_getrennt)

    def test_einrichten_knopf(self):
        self.v.starten()
        self.assertTrue(warte_bis(lambda: self.v.verbunden and self.v.szene))
        klick(self.b.einrichten)
        self.assertFalse(self.b.einrichten.isEnabled())  # kein Doppelklick während es läuft
        self.assertTrue(warte_bis(lambda: self.b.einrichten.isEnabled()))
        self.assertIn("Fertig", self.b.meldung.text())
        self.assertEqual(self.obs.quellen["Rolliregie Countdown"]["settings"]["url"], self.web.countdown_adresse)

    def test_einrichten_ohne_verbindung(self):
        klick(self.b.einrichten)
        self.assertTrue(warte_bis(lambda: self.b.einrichten.isEnabled()))
        self.assertEqual(self.b.meldung.text(), self.E.texte.meldung_nicht_verbunden)

    def test_neu_verbinden_knopf(self):
        self.v._zugang_finden = zugang(1)
        self.v.starten()
        self.assertTrue(warte_bis(lambda: self.f.meldungsleiste.isVisible()))
        self.assertEqual(self.f.meldungstext.text(), self.E.texte.meldung_websocket_aus)
        self.v._zugang_finden = zugang(self.obs.port)
        klick(self.f.knopf_neu)
        self.assertTrue(warte_bis(lambda: self.v.verbunden))
        self.assertTrue(self.f.meldungsleiste.isHidden())

    def test_kein_knopf_beim_start_markiert(self):
        from PySide6.QtWidgets import QApplication, QPushButton
        self.f.activateWindow()
        warte(50)
        self.assertNotIsInstance(QApplication.focusWidget(), QPushButton)

    def test_knoepfe_gross_genug(self):
        from PySide6.QtWidgets import QPushButton
        for k in self.f.findChildren(QPushButton):
            if k.isVisible():
                self.assertGreaterEqual(k.height(), self.E.groessen.knopf_hoehe, k.text())
                self.assertGreaterEqual(k.width(), 100, k.text())

    def test_knoepfe_ueberlappen_nicht(self):
        reihe = [self.b.start, self.b.pause, self.b.stopp]
        for a, b in zip(reihe, reihe[1:]):
            self.assertLessEqual(a.geometry().right(), b.geometry().left(), (a.text(), b.text()))

    def test_port_belegt_meldung(self):
        f2 = Hauptfenster(self.E, self.v, self.vs, self.cd, None, "Port belegt")
        self.assertFalse(f2.countdown_bereich.einrichten.isEnabled())
        self.assertEqual(f2.countdown_bereich.meldung.text(), "Port belegt")
        f2.close()
        f2.deleteLater()


class ObsStartenTest(unittest.TestCase):
    def test_obs_starten_knopf(self):
        app()
        E = einstellungen.lade()
        werte = E.obs.als_dict()
        oe, _ = obs_einstellungen(startbefehl="true")  # harmloser Befehl statt OBS
        v = ObsVerbindung(oe, E.texte, zugang_finden=zugang(1), obs_laeuft=lambda: False)
        vs = Vorschau(v, E.vorschau)
        cd = Countdown("Countdown", 60, 5999)
        E2 = einstellungen.lade()
        E2._werte["obs"] = dict(werte, startbefehl="true")
        f = Hauptfenster(E2, v, vs, cd, "http://x")
        f.show()
        from rolliregie.obs import zugang as zmod
        alt = zmod.obs_laeuft
        zmod.obs_laeuft = lambda *a: False
        try:
            v.starten()
            self.assertTrue(warte_bis(lambda: f.knopf_obs_starten.isVisible()))
            klick(f.knopf_obs_starten)
            self.assertEqual(f.meldungstext.text(), E.texte.meldung_obs_startet)
            self.assertFalse(f.knopf_obs_starten.isVisible())  # nicht doppelt starten
        finally:
            zmod.obs_laeuft = alt
            vs.anhalten(); v.beenden(); f.close(); f.deleteLater()
            warte(20)


if __name__ == "__main__":
    unittest.main()
