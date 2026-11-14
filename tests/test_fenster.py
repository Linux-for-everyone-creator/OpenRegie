"""Prüft das Fenster so, wie es bedient wird: durch Anklicken der Knöpfe."""

import unittest

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton

from openregie import einstellungen
from openregie.geheimspeicher import Arbeitsspeicher
from openregie.obs.motor import MotorZustand, ObsMotor
from openregie.obs.verbindung import ObsVerbindung, Sendung
from openregie.obs.vorschau import Vorschau
from openregie.oberflaeche.hauptfenster import Hauptfenster
from openregie.twitch.konto import Anmeldung, TwitchKonto
from openregie.uno.verwaltung import UnoVerwaltung

from openregie.oberflaeche.overlay_bereich import AUS, BEREIT, LIVE

from .falsches_internet import (CONTENT, EINZEL_ADRESSE_TEXT, EINZEL_TOKEN, UNO_ADRESSE_TEXT, UNO_TOKEN,
                                FalschesInternet)
from .falsches_obs import FalschesObs
from .hilfen import app, internet_einstellungen, obs_einstellungen, warte, warte_bis, zugang


def klick(k):
    assert k.isVisible() and k.isEnabled(), k.text()
    QTest.mouseClick(k, Qt.MouseButton.LeftButton)


class Grundlage(unittest.TestCase):
    mit_uno = True

    def setUp(self):
        app()
        self.netz = FalschesInternet()
        self.E = internet_einstellungen(self.netz)
        self.speicher = Arbeitsspeicher()
        if self.mit_uno:
            self.speicher.json_schreiben("uno", [{"name": "Uno-Projekt 1", "token": UNO_TOKEN}])
        self.obs = FalschesObs(passwort="geheim")
        self.obs_laeuft = True
        oe, _ = obs_einstellungen(szenensammlung="")
        self.v = ObsVerbindung(oe, self.E.texte, zugang_finden=zugang(self.obs.port),
                               obs_laeuft=lambda: self.obs_laeuft)
        self.m = ObsMotor(oe, self.E.texte, self.v, obs_laeuft=lambda: self.obs_laeuft)
        self.vs = Vorschau(self.v, self.E.vorschau)
        self.uno = UnoVerwaltung(self.E.uno, self.E.texte, self.speicher)
        self.twitch = TwitchKonto(self.E.twitch, self.E.texte, self.speicher)
        self.f = Hauptfenster(self.E, self.v, self.vs, self.m, self.uno, self.twitch)
        self.geoeffnet = []
        self.f.twitch_bereich._browser_oeffnen = self.geoeffnet.append
        self.f.resize(1600, 900)
        self.f.show()
        self.uno.laden()
        self.twitch.laden()
        if self.mit_uno:
            self.assertTrue(warte_bis(lambda: len(self.f.bibliothek.kacheln) == 3, 3000))

    def tearDown(self):
        self.vs.anhalten()
        self.uno.beenden()
        self.twitch.beenden()
        self.v.beenden()
        self.obs.beenden()
        self.netz.beenden()
        self.f._schliessen_erlaubt = True
        self.f.close()
        self.f.deleteLater()
        warte(20)

    def kachel(self, name):
        return next(k for k in self.f.bibliothek.kacheln.values() if k.overlay.name == name)


class FensterTest(Grundlage):
    def test_name_uhr_und_build_wasserzeichen(self):
        self.assertIn("OpenRegie", self.f.windowTitle())
        self.assertIn("Profi-Regie für alle. Einfach live.", self.f.windowTitle())
        self.assertEqual(self.f.build.text(), "OpenRegie · Vorabversion · Build " + einstellungen.build_nummer())
        self.assertTrue(self.f.build.isVisible())
        mitte = self.f.centralWidget()
        self.assertLess(self.f.build.x(), 60)  # unten links
        self.assertGreater(self.f.build.y(), mitte.height() - 60)
        self.assertLess(self.f.build.graphicsEffect().opacity(), 1)
        self.assertRegex(self.f.uhr.text(), r"^\d\d:\d\d:\d\d$")

    def test_bibliothek_mit_lampen(self):
        self.assertEqual([k.overlay.name for k in self.f.bibliothek.kacheln.values()],
                         ["Bauchbinde", "News-Ticker", "Countdown"])
        self.assertEqual(self.kachel("News-Ticker").zustand, LIVE)  # roter Rahmen
        self.assertEqual(self.kachel("Bauchbinde").zustand, BEREIT)  # grüner Rahmen
        self.assertIn("Live", self.kachel("News-Ticker").accessibleName())
        # erstes Overlay ist gleich ausgewählt
        self.assertTrue(self.kachel("Bauchbinde").isChecked())
        self.assertIs(self.f.bedienfelder.currentWidget(), self.f.overlay_bedienfeld)

    def test_einblenden_ausblenden(self):
        b = self.f.overlay_bedienfeld
        klick(self.kachel("Bauchbinde"))
        self.assertEqual(b.name.text(), "Bauchbinde")
        self.assertFalse(b.ausblenden.isEnabled())  # ist schon aus
        klick(b.einblenden)
        self.assertTrue(warte_bis(lambda: self.netz.overlays[0]["visible"], 3000))
        self.assertTrue(warte_bis(lambda: self.kachel("Bauchbinde").zustand == LIVE, 3000))
        self.assertEqual(b.tally_text.text(), self.E.texte.overlay_im_stream)
        self.assertFalse(b.einblenden.isEnabled())
        klick(b.ausblenden)
        self.assertTrue(warte_bis(lambda: not self.netz.overlays[0]["visible"], 3000))
        self.assertTrue(warte_bis(lambda: self.kachel("Bauchbinde").zustand == BEREIT, 3000))

    def test_texte_aendern(self):
        b = self.f.overlay_bedienfeld
        klick(self.kachel("Bauchbinde"))
        self.assertTrue(warte_bis(lambda: len(b.eingaben) == 2, 3000))
        self.assertFalse(b.countdown.isVisible())  # kein Countdown bei der Bauchbinde
        b.eingabe("Titel").setText("Heute: Neues Spiel!")
        klick(b.knopf_uebernehmen)
        self.assertTrue(warte_bis(lambda: b.meldung_texte.text() == self.E.texte.meldung_texte_ok, 3000))
        self.assertEqual(self.netz.inhalte["ov-1"]["Titel"], "Heute: Neues Spiel!")
        self.assertEqual(self.netz.inhalte["ov-1"]["Name"], "Kevin")
        self.assertEqual(self.netz.anzahl("SetOverlayContentField"), 1)  # nur das geänderte Feld
        klick(b.knopf_uebernehmen)
        self.assertEqual(b.meldung_texte.text(), self.E.texte.meldung_texte_nichts)

    def test_overlay_ohne_texte(self):
        b = self.f.overlay_bedienfeld
        klick(self.kachel("Countdown"))
        self.assertTrue(warte_bis(lambda: b.knopf_texte_neu.isEnabled(), 3000))
        self.assertEqual(b.eingaben, {})
        self.assertFalse(b.knopf_uebernehmen.isEnabled())

    def test_neues_overlay_liste_neu_laden(self):
        self.netz.overlays.append({"id": "ov-4", "name": "Uhr", "visible": False})
        klick(self.f.bibliothek.knopf_neu)
        self.assertTrue(warte_bis(lambda: len(self.f.bibliothek.kacheln) == 4, 3000))
        self.assertEqual(list(self.f.bibliothek.kacheln.values())[-1].overlay.name, "Uhr")

    def test_uno_fehler_wird_angezeigt(self):
        b = self.f.overlay_bedienfeld
        klick(self.kachel("Bauchbinde"))
        self.netz.uno_kaputt = True
        klick(b.einblenden)
        self.assertTrue(warte_bis(lambda: b.meldung_schalter.text() == self.E.texte.meldung_uno_fehler, 3000))
        self.assertTrue(b.einblenden.isEnabled())  # gleich nochmal versuchbar

    def test_verbindung_und_on_air(self):
        self.m.starten()  # OBS „läuft schon“ → nur verbinden
        self.assertTrue(warte_bis(lambda: self.v.verbunden, 3000))
        self.assertTrue(self.f.meldungsleiste.isHidden())
        self.assertEqual(self.f.on_air.text.text(), self.E.texte.on_air_aus)
        self.obs.stream_starten()
        self.assertTrue(warte_bis(lambda: self.f.on_air.text.text() == self.E.texte.on_air_an))
        self.assertIn(self.E.farben.on_air_an, self.f.on_air.styleSheet())
        self.assertTrue(self.f.vorschaubild.live)  # roter Rahmen um das Live-Bild
        self.obs.stream_stoppen()
        self.assertTrue(warte_bis(lambda: self.f.on_air.text.text() == self.E.texte.on_air_aus))
        self.assertFalse(self.f.vorschaubild.live)

    def test_vorschau_im_fenster(self):
        self.m.starten()
        self.assertTrue(warte_bis(lambda: self.f.vorschaubild.hat_bild(), 3000))
        self.assertTrue(warte_bis(lambda: self.f.szenenname.text() == "Szene 1"))
        self.obs.alle_trennen()
        self.assertTrue(warte_bis(lambda: not self.f.vorschaubild.hat_bild()))
        self.assertTrue(warte_bis(lambda: self.f.meldungsleiste.isVisible()))
        self.assertEqual(self.f.meldungstext.text(), self.E.texte.meldung_verbindung_weg)
        self.assertTrue(warte_bis(lambda: self.f.vorschaubild.hat_bild(), 3000))

    def test_meldung_obs_startet_und_fehler(self):
        self.m._zustand_setzen(MotorZustand.STARTET, self.E.texte.meldung_obs_startet)
        self.assertTrue(self.f.meldungsleiste.isVisible())
        self.assertEqual(self.f.meldungstext.text(), self.E.texte.meldung_obs_startet)
        self.assertTrue(self.f.knopf_obs_starten.isHidden())
        self.obs_laeuft = False
        self.m._zustand_setzen(MotorZustand.FEHLER, self.E.texte.meldung_obs_abgestuerzt)
        self.assertEqual(self.f.meldungstext.text(), self.E.texte.meldung_obs_abgestuerzt)
        self.assertTrue(self.f.knopf_obs_starten.isVisible())
        self.assertTrue(self.f.knopf_neu.isVisible())

    def test_beenden_wenn_live_fragt_nach(self):
        self.m.selbst_gestartet = True  # so tun, als hätte OpenRegie OBS gestartet
        self.v.starten()
        self.assertTrue(warte_bis(lambda: self.v.verbunden, 3000))
        self.obs.stream_starten()
        self.assertTrue(warte_bis(lambda: self.v.sendung is Sendung.AN, 3000))
        fragen = []
        self.f.frage_beenden = lambda: fragen.append(1) or False  # „Weiter streamen“
        self.f.close()
        self.assertEqual(fragen, [1])
        self.assertTrue(self.f.isVisible())
        self.assertTrue(self.obs.stream_aktiv)
        self.f.frage_beenden = lambda: True  # „Stream beenden und schließen“
        self.f.close()
        self.assertTrue(warte_bis(lambda: not self.f.isVisible(), 3000))
        self.assertFalse(self.obs.stream_aktiv)

    def test_beenden_ohne_stream_ohne_frage(self):
        self.m.selbst_gestartet = True
        self.f.frage_beenden = lambda: self.fail("keine Frage erwartet")
        self.f.close()
        self.assertFalse(self.f.isVisible())

    def test_kein_knopf_beim_start_markiert(self):
        self.f.activateWindow()
        warte(50)
        self.assertNotIsInstance(QApplication.focusWidget(), QPushButton)

    def test_knoepfe_gross_genug_und_ohne_ueberlappung(self):
        klick(self.kachel("Bauchbinde"))
        warte_bis(lambda: self.f.overlay_bedienfeld.eingaben, 3000)
        sichtbar = [k for k in self.f.findChildren(QPushButton) if k.isVisible()]
        for k in sichtbar:
            self.assertGreaterEqual(k.height(), self.E.groessen.knopf_hoehe, k.text())
            self.assertGreaterEqual(k.width(), 70, k.text())
        for k in self.f.bibliothek.kacheln.values():
            self.assertGreaterEqual(k.height(), 100)
            self.assertGreaterEqual(k.width(), 150)
        b = self.f.overlay_bedienfeld
        self.assertLessEqual(b.einblenden.geometry().right(), b.ausblenden.geometry().left())


class EinzelUnoFensterTest(Grundlage):
    """Kevins „Countdown | Circles“ im Fenster: Ein/Aus, Countdown, Dauer, Texte."""
    mit_uno = False

    def setUp(self):
        super().setUp()
        self.e = self.netz.einzel
        e = self.f.uno_einrichtung
        e._zwischenablage = lambda: EINZEL_ADRESSE_TEXT
        klick(e.einfuegen)
        self.assertTrue(warte_bis(lambda: e.meldung.text() == self.E.texte.meldung_uno_einzel_ok, 3000))
        self.assertEqual(e.meldung.objectName(), "gut")  # grün, nicht rot
        klick(e.zurueck)
        self.b = self.f.overlay_bedienfeld
        self.assertTrue(warte_bis(lambda: self.b.overlay is not None and self.b.countdown.isVisible()
                                  and self.b.eingaben, 3000))

    def test_kachel_und_bedienfeld(self):
        k = self.kachel("Countdown | Circles")
        self.assertTrue(k.isChecked())
        self.assertEqual(k.zustand, BEREIT)
        self.assertEqual(k.zeit_text(), "05:00")
        self.assertTrue(warte_bis(lambda: k.bild is not None, 3000))  # Vorschaubild von Uno geladen
        self.assertEqual(self.b.zeit.text(), "05:00")
        self.assertEqual(self.b.countdown_zustand.text(), self.E.texte.countdown_bereit)
        self.assertEqual(list(self.b.eingaben), [(CONTENT, "Message")])

    def test_einblenden_komplett(self):
        klick(self.b.einblenden)
        self.assertTrue(warte_bis(lambda: self.e.komplett_sichtbar(), 3000))
        self.assertTrue(warte_bis(lambda: self.kachel("Countdown | Circles").zustand == LIVE, 3000))
        klick(self.b.ausblenden)
        self.assertTrue(warte_bis(lambda: self.e.ganz_aus(), 3000))

    def test_countdown_bedienen(self):
        t = self.E.texte
        self.assertFalse(self.b.pause.isEnabled())
        klick(self.b.start)
        self.assertTrue(warte_bis(lambda: self.b.countdown_zustand.text() == t.countdown_laeuft, 3000))
        self.assertTrue(self.e.werte[CONTENT]["Timer"]["isRunning"])
        self.assertFalse(self.b.start.isEnabled())
        warte(1300)
        self.assertEqual(self.b.zeit.text(), "04:59")  # zählt sichtbar herunter
        klick(self.b.pause)
        self.assertTrue(warte_bis(lambda: self.b.countdown_zustand.text() == t.countdown_pausiert, 3000))
        klick(self.b.zurueck)
        self.assertTrue(warte_bis(lambda: self.b.zeit.text() == "05:00", 3000))
        self.assertEqual(self.b.countdown_zustand.text(), t.countdown_bereit)

    def test_dauer_einstellen(self):
        klick(self.b.dauer_knoepfe[600])
        self.assertEqual(self.b.zeit.text(), "15:00")  # sofort sichtbar
        self.assertTrue(warte_bis(lambda: self.e.werte[CONTENT]["BeginTime"] == 900, 3000))
        klick(self.b.dauer_knoepfe[-60])
        self.assertTrue(warte_bis(lambda: self.e.werte[CONTENT]["BeginTime"] == 840, 3000))
        for _ in range(3):
            klick(self.b.dauer_knoepfe[-600])
            warte(200)
        self.assertTrue(warte_bis(lambda: self.e.werte[CONTENT]["BeginTime"] == 0, 3000))  # nie negativ

    def test_endtext_aendern(self):
        self.b.eingabe("Message").setText("Gleich geht's los!")
        klick(self.b.knopf_uebernehmen)
        self.assertTrue(warte_bis(lambda: self.b.meldung_texte.text() == self.E.texte.meldung_texte_ok, 3000))
        self.assertEqual(self.e.werte[CONTENT]["Message"], "Gleich geht's los!")

    def test_knoepfe_passen_in_die_spalte(self):
        rechts = self.b.width()
        for k in [self.b.start, self.b.pause, self.b.zurueck, *self.b.dauer_knoepfe.values()]:
            self.assertTrue(k.isVisible(), k.text())
            self.assertLessEqual(k.mapTo(self.b, k.rect().topRight()).x(), rechts, k.text())
            self.assertGreaterEqual(k.height(), self.E.groessen.knopf_hoehe)


class TwitchFensterTest(Grundlage):
    mit_uno = False

    def test_anmelden_und_titel_aendern(self):
        tb = self.f.twitch_bereich
        self.assertTrue(tb.anmelden.isVisible())
        self.assertTrue(tb.titel_reihe.isHidden())
        klick(tb.anmelden)
        self.assertTrue(warte_bis(lambda: self.twitch.zustand is Anmeldung.WARTET, 3000))
        self.assertIn("ABCD-EFGH", tb.hinweis.text())
        self.assertEqual(len(self.geoeffnet), 1)  # Twitch-Seite automatisch geöffnet
        klick(tb.seite_oeffnen)
        self.assertEqual(len(self.geoeffnet), 2)
        self.netz.bestaetigt = True
        self.assertTrue(warte_bis(lambda: tb.titel_reihe.isVisible(), 4000))
        self.assertTrue(warte_bis(lambda: tb.titel.text() == "Alter Titel", 3000))
        self.assertTrue(warte_bis(lambda: "KevinTest" in tb.konto_text.text(), 3000))
        tb.titel.setText("Mein neuer Streamtitel")
        klick(tb.uebernehmen)
        self.assertTrue(warte_bis(lambda: tb.meldung.text() == self.E.texte.meldung_twitch_titel_ok, 3000))
        self.assertEqual(self.netz.titel, "Mein neuer Streamtitel")
        klick(tb.abmelden)
        self.assertTrue(tb.anmelden.isVisible())

    def test_ohne_uno_projekt_einrichtung_zeigen(self):
        self.assertIs(self.f.bedienfelder.currentWidget(), self.f.uno_einrichtung)
        self.assertTrue(self.f.bibliothek.leer.isVisible())

    def test_uno_projekt_per_zwischenablage(self):
        e = self.f.uno_einrichtung
        e._zwischenablage = lambda: "irgendein Text"
        klick(e.einfuegen)
        self.assertTrue(warte_bis(lambda: e.meldung.text() == self.E.texte.meldung_uno_adresse_falsch, 3000))
        e._zwischenablage = lambda: UNO_ADRESSE_TEXT + "\n"
        klick(e.einfuegen)
        self.assertTrue(warte_bis(lambda: len(self.f.bibliothek.kacheln) == 3, 3000))
        self.assertTrue(warte_bis(lambda: "3" in e.meldung.text(), 3000))
        self.assertIn(UNO_TOKEN, self.speicher.daten["uno"])
        klick(e.entfernen_knoepfe[UNO_TOKEN])  # Entfernen braucht zwei Klicks
        self.assertEqual(len(self.uno.projekte), 1)
        klick(e.entfernen_knoepfe[UNO_TOKEN])
        self.assertEqual(self.uno.projekte, [])
        self.assertEqual(self.f.bibliothek.kacheln, {})


if __name__ == "__main__":
    unittest.main()
