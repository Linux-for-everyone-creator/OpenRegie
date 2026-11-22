"""Prüft das Fenster so, wie es bedient wird: durch Anklicken der Knöpfe."""

import unittest

import re
from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QHelpEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton, QToolTip

from openregie import einstellungen
from openregie.geheimspeicher import Arbeitsspeicher
from openregie.obs.motor import MotorZustand, ObsMotor
from openregie.obs.verbindung import ObsVerbindung, Sendung
from openregie.obs.vorschau import Vorschau
from openregie.oberflaeche.hauptfenster import Hauptfenster
from openregie.twitch.konto import Anmeldung, TwitchKonto
from openregie.uno.verwaltung import UnoVerwaltung

from openregie.oberflaeche import overlay_bereich
from openregie.oberflaeche.bausteine import gesperrt_text
from openregie.oberflaeche.overlay_bereich import AUS, BEREIT, LIVE

from .falsches_internet import (CONTENT, EINZEL_ADRESSE_TEXT, EINZEL_TOKEN, UNO_ADRESSE_TEXT, UNO_TOKEN,
                                FalschesInternet)
from .falsches_obs import FalschesObs
from .hilfen import app, groesste_pause_ms, internet_einstellungen, obs_einstellungen, warte, warte_bis, zugang


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

    # --- Countdown-Zeit direkt eintippen --------------------------------------
    def tippen(self, text, taste=Qt.Key.Key_Return):
        """Klick auf die große Zeit, Text eintippen, Enter (bzw. andere Taste)."""
        QTest.mouseClick(self.b.zeit, Qt.MouseButton.LeftButton)
        self.assertTrue(self.b.zeit_eingabe.isVisible())
        self.assertFalse(self.b.zeit.isVisible())
        self.assertEqual(self.b.zeit_eingabe.selectedText(), self.b.zeit.text())  # alles markiert
        QTest.keyClicks(self.b.zeit_eingabe, text)
        if taste is not None:
            QTest.keyClick(self.b.zeit_eingabe, taste)

    def uno_patches(self):
        return [b["PATCH"] for b in self.netz.einzel_befehle if "PATCH" in b]

    def test_zeit_eintippen_kommt_bei_uno_an(self):
        self.tippen("12:30")
        self.assertFalse(self.b.zeit_eingabe.isVisible())
        self.assertTrue(self.b.zeit.isVisible())
        self.assertEqual(self.b.zeit.text(), "12:30")  # sofort sichtbar
        self.assertTrue(warte_bis(lambda: self.e.werte[CONTENT]["BeginTime"] == 750, 3000))
        self.assertEqual(self.uno_patches()[-1], [{"subCompositionId": CONTENT, "payload": {"BeginTime": 750}}])
        self.assertTrue(warte_bis(lambda: self.kachel("Countdown | Circles").zeit_text() == "12:30", 3000))
        self.assertEqual(self.e.restzeit_s(), 750)  # das Uno-Overlay zeigt genau diese Zeit
        self.assertFalse(self.b.meldung_zeit.isVisible())
        # Stunden und nur Minuten gehen auch
        self.tippen("1:05:00")
        self.assertTrue(warte_bis(lambda: self.e.werte[CONTENT]["BeginTime"] == 3900, 3000))
        self.assertEqual(self.b.zeit.text(), "1:05:00")
        self.tippen("5")
        self.assertTrue(warte_bis(lambda: self.e.werte[CONTENT]["BeginTime"] == 300, 3000))
        self.assertEqual(self.b.zeit.text(), "05:00")

    def test_zeit_und_minuten_knoepfe_zeigen_dasselbe(self):
        self.tippen("12:30")
        self.assertTrue(warte_bis(lambda: self.e.werte[CONTENT]["BeginTime"] == 750, 3000))
        klick(self.b.dauer_knoepfe[60])  # +1 Min rechnet mit der eingetippten Zeit weiter
        self.assertEqual(self.b.zeit.text(), "13:30")
        self.assertTrue(warte_bis(lambda: self.e.werte[CONTENT]["BeginTime"] == 810, 3000))
        self.assertEqual(self.b.overlay.dauer, 810)
        self.tippen("2:00")  # und umgekehrt: Eintippen nach den Knöpfen
        self.assertTrue(warte_bis(lambda: self.e.werte[CONTENT]["BeginTime"] == 120, 3000))
        klick(self.b.dauer_knoepfe[-60])
        self.assertTrue(warte_bis(lambda: self.e.werte[CONTENT]["BeginTime"] == 60, 3000))
        self.assertTrue(warte_bis(lambda: self.b.zeit.text() == "01:00", 3000))

    def test_escape_bricht_ab(self):
        self.tippen("9:99", taste=Qt.Key.Key_Escape)
        self.assertFalse(self.b.zeit_eingabe.isVisible())
        self.assertEqual(self.b.zeit.text(), "05:00")
        warte(300)
        self.assertEqual(self.uno_patches(), [])  # nichts an Uno geschickt
        self.assertEqual(self.e.werte[CONTENT]["BeginTime"], 300)

    def test_falsche_eingaben_mit_hinweis(self):
        t = self.E.texte
        for text, hinweis in [("abc", t.meldung_countdown_format), ("5:75", t.meldung_countdown_ueber_59),
                              ("0:00", t.meldung_countdown_null), ("10:00:00",
                               t.meldung_countdown_zu_lang.format(hoechstens="9:59:59")),
                              ("5:3", t.meldung_countdown_format), ("", t.meldung_countdown_leer)]:
            if not self.b.zeit_eingabe.isVisible():
                QTest.mouseClick(self.b.zeit, Qt.MouseButton.LeftButton)
            self.b.zeit_eingabe.selectAll()
            QTest.keyClick(self.b.zeit_eingabe, Qt.Key.Key_Backspace)
            QTest.keyClicks(self.b.zeit_eingabe, text)
            QTest.keyClick(self.b.zeit_eingabe, Qt.Key.Key_Return)
            self.assertTrue(self.b.zeit_eingabe.isVisible(), text)  # bleibt offen zum Verbessern
            self.assertTrue(self.b.meldung_zeit.isVisible(), text)
            self.assertEqual(self.b.meldung_zeit.text(), hinweis, text)
            self.assertEqual(self.b.meldung_zeit.objectName(), "fehler")
        # Verbessern: richtig eintippen, Hinweis verschwindet
        self.b.zeit_eingabe.selectAll()
        QTest.keyClicks(self.b.zeit_eingabe, "7:00")
        QTest.keyClick(self.b.zeit_eingabe, Qt.Key.Key_Return)
        self.assertFalse(self.b.meldung_zeit.isVisible())
        self.assertTrue(warte_bis(lambda: self.e.werte[CONTENT]["BeginTime"] == 420, 3000))
        # nur die richtige Zeit kam bei Uno an
        self.assertEqual(self.uno_patches(), [[{"subCompositionId": CONTENT, "payload": {"BeginTime": 420}}]])

    def test_gesperrt_wenn_live(self):
        t = self.E.texte
        klick(self.b.einblenden)
        self.assertTrue(warte_bis(lambda: self.b.overlay.sichtbar is True, 3000))
        QTest.mouseClick(self.b.zeit, Qt.MouseButton.LeftButton)
        self.assertFalse(self.b.zeit_eingabe.isVisible())  # kein Eingabefeld
        self.assertTrue(self.b.meldung_zeit.isVisible())
        self.assertEqual(self.b.meldung_zeit.text(), t.meldung_countdown_live)
        QTest.mouseClick(self.b.zeit, Qt.MouseButton.LeftButton)  # auch Doppelklick nicht
        QTest.mouseDClick(self.b.zeit, Qt.MouseButton.LeftButton)
        self.assertFalse(self.b.zeit_eingabe.isVisible())
        self.assertEqual(self.b.zeit.toolTip(), t.meldung_countdown_live)
        warte(50)
        # der (zweizeilige) Hinweis liegt UNTER der Zeit, nichts wird überdeckt oder gequetscht
        self.assertGreater(self.b.meldung_zeit.geometry().top(), self.b.zeit.geometry().bottom())
        self.assertGreaterEqual(self.b.meldung_zeit.height(),
                                self.b.meldung_zeit.heightForWidth(self.b.meldung_zeit.width()))
        self.assertLess(self.b.meldung_zeit.geometry().bottom(), self.b.start.geometry().top())
        self.assertFalse(self.b.countdown_zustand.isVisible())  # der Hinweis steht an seiner Stelle
        # Hinweis verschwindet von selbst, die Zustandszeile kommt zurück
        self.assertTrue(warte_bis(lambda: not self.b.meldung_zeit.isVisible(), self.b.HINWEIS_MS + 1500))
        self.assertTrue(self.b.countdown_zustand.isVisible())
        n = len(self.uno_patches())
        warte(200)
        self.assertEqual(len(self.uno_patches()), n)
        self.assertEqual(self.e.werte[CONTENT]["BeginTime"], 300)
        # nach dem Ausblenden geht es wieder
        klick(self.b.ausblenden)
        self.assertTrue(warte_bis(lambda: self.b.overlay.sichtbar is False, 3000))
        warte(300)
        self.assertEqual(self.b.zeit.toolTip(), t.countdown_zeit_tippen)
        self.tippen("3:00")
        self.assertTrue(warte_bis(lambda: self.e.werte[CONTENT]["BeginTime"] == 180, 3000))

    def test_waehrend_des_tippens_live_geschaltet(self):
        """Jemand blendet ein, während getippt wird: Eingabe zu, nichts übernommen."""
        self.tippen("8:00", taste=None)
        self.e.werte[CONTENT]["ShowOverlay"] = True
        self.e.zustand.update({k: "In" for k in self.e.zustand})
        self.e.werte["-Haupt1"]["Active"] = True
        self.uno.felder_laden(self.b.overlay)  # Uno meldet: jetzt im Stream
        self.assertTrue(warte_bis(lambda: not self.b.zeit_eingabe.isVisible(), 3000))
        self.assertEqual(self.b.meldung_zeit.text(), self.E.texte.meldung_countdown_live)
        QTest.keyClick(self.b.zeit_eingabe, Qt.Key.Key_Return)  # Enter kommt zu spät: nichts passiert
        warte(300)
        self.assertEqual(self.uno_patches(), [])
        self.assertEqual(self.e.werte[CONTENT]["BeginTime"], 300)

    def test_angehaltener_countdown_steht_danach_auf_der_neuen_zeit(self):
        t = self.E.texte
        klick(self.b.start)
        self.assertTrue(warte_bis(lambda: self.b.countdown_zustand.text() == t.countdown_laeuft, 3000))
        warte(1200)
        klick(self.b.pause)
        self.assertTrue(warte_bis(lambda: self.b.countdown_zustand.text() == t.countdown_pausiert, 3000))
        self.assertIn(self.b.zeit.text(), ("04:59", "04:58", "04:57"))  # angehalten, schon gezählt
        self.tippen("10:00")
        self.assertEqual(self.b.zeit.text(), "10:00")  # nicht 9:59
        self.assertTrue(warte_bis(lambda: self.e.werte[CONTENT]["BeginTime"] == 600, 3000))
        # ein einziger Befehl: neue Dauer + zurück auf Anfang
        self.assertEqual(self.uno_patches()[-1], [{"subCompositionId": CONTENT,
                                                   "payload": {"BeginTime": 600, "Timer": {"command": "reset"}}}])
        self.assertEqual(self.e.restzeit_s(), 600)  # Uno zeigt genau 10:00
        self.assertTrue(warte_bis(lambda: self.b.countdown_zustand.text() == t.countdown_bereit, 3000))
        warte(600)
        self.assertEqual(self.b.zeit.text(), "10:00")  # läuft nicht von selbst los
        klick(self.b.start)  # und startet von der neuen Zeit
        self.assertTrue(warte_bis(lambda: self.b.zeit.text() == "09:59", 3000))

    def test_uno_lehnt_ab_alte_zeit_kommt_zurueck(self):
        self.netz.uno_kaputt = True
        self.tippen("12:30")
        self.assertTrue(warte_bis(lambda: self.b.meldung_zeit.isVisible(), 3000))
        self.assertEqual(self.b.meldung_zeit.text(), self.E.texte.meldung_uno_fehler)
        self.assertEqual(self.b.zeit.text(), "05:00")  # nichts vorgegaukelt
        self.assertEqual(self.b.overlay.dauer, 300)
        self.netz.uno_kaputt = False
        self.tippen("12:30")
        self.assertTrue(warte_bis(lambda: self.e.werte[CONTENT]["BeginTime"] == 750, 3000))
        self.assertFalse(self.b.meldung_zeit.isVisible())

    def test_doppelklick_oeffnet_und_ersetzt_die_zeit(self):
        # echter Doppelklick: Drücken, Loslassen (öffnet), Doppelklick + Loslassen landen im neuen Feld
        QTest.mousePress(self.b.zeit, Qt.MouseButton.LeftButton)
        QTest.mouseRelease(self.b.zeit, Qt.MouseButton.LeftButton)
        self.assertTrue(self.b.zeit_eingabe.isVisible())
        QTest.mouseDClick(self.b.zeit_eingabe, Qt.MouseButton.LeftButton)
        QTest.mouseRelease(self.b.zeit_eingabe, Qt.MouseButton.LeftButton)
        self.assertTrue(self.b.zeit_eingabe.isVisible())
        self.assertEqual(self.b.zeit_eingabe.selectedText(), "05:00")  # weiterhin alles markiert
        QTest.keyClicks(self.b.zeit_eingabe, "4:00")
        self.assertEqual(self.b.zeit_eingabe.text(), "4:00")
        QTest.keyClick(self.b.zeit_eingabe, Qt.Key.Key_Enter)  # Enter auf dem Ziffernblock
        self.assertTrue(warte_bis(lambda: self.e.werte[CONTENT]["BeginTime"] == 240, 3000))

    def test_wegklicken_und_knoepfe_brechen_ab(self):
        self.tippen("8:00", taste=None)
        klick(self.b.dauer_knoepfe[60])  # anderer Knopf: Eingabe zu, Knopf gilt
        self.assertFalse(self.b.zeit_eingabe.isVisible())
        self.assertTrue(warte_bis(lambda: self.e.werte[CONTENT]["BeginTime"] == 360, 3000))
        self.tippen("8:00", taste=None)
        self.b.eingabe("Message").setFocus(Qt.FocusReason.MouseFocusReason)  # ins Textfeld geklickt
        self.assertTrue(warte_bis(lambda: not self.b.zeit_eingabe.isVisible(), 1000))
        warte(300)
        self.assertEqual(self.e.werte[CONTENT]["BeginTime"], 360)

    # --- Knöpfe ✓ (Übernehmen) und ✕ (Abbrechen) neben dem Feld – ohne Enter/Esc ---
    def echter_klick(self, k):
        """Drücken und Loslassen wie mit der Maus – inklusive Fokuswechsel, den Qt beim Drücken macht."""
        self.assertTrue(k.isVisible() and k.isEnabled(), k.accessibleName())
        QTest.mousePress(k, Qt.MouseButton.LeftButton)
        # Beim Drücken darf das Feld nicht zugehen (kein „Wegklicken“)
        self.assertTrue(self.b.zeit_eingabe.isVisible(), "Feld beim Drücken zugegangen")
        self.assertTrue(self.b.zeit_eingabe.hasFocus(), "Knopf hat den Fokus genommen")
        QTest.mouseRelease(k, Qt.MouseButton.LeftButton)

    def test_knoepfe_nur_beim_tippen_und_gross_genug(self):
        self.assertFalse(self.b.zeit_ok.isVisible())
        self.assertFalse(self.b.zeit_weg.isVisible())
        self.tippen("8:00", taste=None)
        warte(50)
        rechts = self.b.width()
        feld = self.b.zeit_eingabe.geometry()
        for k in (self.b.zeit_ok, self.b.zeit_weg):
            self.assertTrue(k.isVisible())
            self.assertGreaterEqual(k.width(), self.E.groessen.knopf_hoehe)
            self.assertGreaterEqual(k.height(), self.E.groessen.knopf_hoehe)
            self.assertEqual(k.height(), self.b.zeit_eingabe.height())
            self.assertLessEqual(k.mapTo(self.b, k.rect().topRight()).x(), rechts)  # passt in die Spalte
            self.assertGreater(k.geometry().left(), feld.right())  # neben dem Feld, nichts überdeckt
            self.assertEqual(k.focusPolicy(), Qt.FocusPolicy.NoFocus)
        self.assertEqual(self.b.zeit_ok.accessibleName(), "Übernehmen")
        self.assertEqual(self.b.zeit_weg.accessibleName(), "Abbrechen")
        # „1:05:00“ passt noch ganz ins Feld
        self.b.zeit_eingabe.setText("1:05:00")
        breite = self.b.zeit_eingabe.fontMetrics().horizontalAdvance("1:05:00")
        self.assertLess(breite, self.b.zeit_eingabe.width() - 24)

    def test_haekchen_uebernimmt(self):
        self.tippen("12:30", taste=None)
        self.echter_klick(self.b.zeit_ok)
        self.assertFalse(self.b.zeit_eingabe.isVisible())
        self.assertFalse(self.b.zeit_ok.isVisible())
        self.assertTrue(self.b.zeit.isVisible())
        self.assertEqual(self.b.zeit.text(), "12:30")
        self.assertTrue(warte_bis(lambda: self.e.werte[CONTENT]["BeginTime"] == 750, 3000))
        self.assertEqual(self.uno_patches(), [[{"subCompositionId": CONTENT, "payload": {"BeginTime": 750}}]])
        self.assertEqual(self.e.restzeit_s(), 750)

    def test_kreuz_bricht_ab(self):
        self.tippen("9:99", taste=None)
        self.echter_klick(self.b.zeit_weg)
        self.assertFalse(self.b.zeit_eingabe.isVisible())
        self.assertTrue(self.b.zeit.isVisible())
        self.assertEqual(self.b.zeit.text(), "05:00")
        warte(300)
        self.assertEqual(self.uno_patches(), [])
        self.assertEqual(self.e.werte[CONTENT]["BeginTime"], 300)
        # danach geht es ganz normal wieder auf
        self.tippen("4:00", taste=None)
        self.echter_klick(self.b.zeit_ok)
        self.assertTrue(warte_bis(lambda: self.e.werte[CONTENT]["BeginTime"] == 240, 3000))

    def test_haekchen_faengt_falsche_eingaben_ab_wie_enter(self):
        t = self.E.texte
        QTest.mouseClick(self.b.zeit, Qt.MouseButton.LeftButton)
        for text, hinweis in [("abc", t.meldung_countdown_format), ("5:75", t.meldung_countdown_ueber_59),
                              ("0:00", t.meldung_countdown_null), ("10:00:00",
                               t.meldung_countdown_zu_lang.format(hoechstens="9:59:59")),
                              ("5:3", t.meldung_countdown_format), ("", t.meldung_countdown_leer)]:
            self.b.zeit_eingabe.selectAll()
            QTest.keyClick(self.b.zeit_eingabe, Qt.Key.Key_Backspace)
            QTest.keyClicks(self.b.zeit_eingabe, text)
            self.echter_klick(self.b.zeit_ok)
            self.assertTrue(self.b.zeit_eingabe.isVisible(), text)  # bleibt offen zum Verbessern
            self.assertTrue(self.b.zeit_eingabe.hasFocus(), text)  # gleich weitertippen
            self.assertEqual(self.b.zeit_eingabe.selectedText(), text, text)
            self.assertEqual(self.b.meldung_zeit.text(), hinweis, text)
            self.assertEqual(self.b.meldung_zeit.objectName(), "fehler")
        QTest.keyClicks(self.b.zeit_eingabe, "7:00")  # tippt direkt über die markierte falsche Eingabe
        self.echter_klick(self.b.zeit_ok)
        self.assertFalse(self.b.meldung_zeit.isVisible())
        self.assertTrue(warte_bis(lambda: self.e.werte[CONTENT]["BeginTime"] == 420, 3000))
        self.assertEqual(self.uno_patches(), [[{"subCompositionId": CONTENT, "payload": {"BeginTime": 420}}]])

    def test_kreuz_nach_falscher_eingabe_raeumt_hinweis_weg(self):
        self.tippen("abc", taste=None)
        self.echter_klick(self.b.zeit_ok)
        self.assertTrue(self.b.meldung_zeit.isVisible())
        self.echter_klick(self.b.zeit_weg)
        self.assertFalse(self.b.zeit_eingabe.isVisible())
        self.assertFalse(self.b.meldung_zeit.isVisible())
        self.assertEqual(self.b.zeit.text(), "05:00")

    def test_haekchen_nachdem_live_geschaltet(self):
        """Eingeblendet, während getippt wird, und Uno meldet es erst beim Klick: nichts übernehmen."""
        self.tippen("8:00", taste=None)
        self.b.overlay.sichtbar = True  # Zustand schon da, Fenster noch nicht neu gezeichnet
        self.echter_klick(self.b.zeit_ok)
        self.assertFalse(self.b.zeit_eingabe.isVisible())
        self.assertEqual(self.b.meldung_zeit.text(), self.E.texte.meldung_countdown_live)
        warte(300)
        self.assertEqual(self.uno_patches(), [])
        self.assertEqual(self.e.werte[CONTENT]["BeginTime"], 300)

    def test_doppelt_auf_haekchen_schickt_nur_einmal(self):
        self.tippen("3:00", taste=None)
        # versehentlicher Doppelklick: zweimal Drücken+Loslassen sofort hintereinander
        for _ in range(2):
            QTest.mousePress(self.b.zeit_ok, Qt.MouseButton.LeftButton)
            QTest.mouseRelease(self.b.zeit_ok, Qt.MouseButton.LeftButton)
        self.assertTrue(warte_bis(lambda: self.e.werte[CONTENT]["BeginTime"] == 180, 3000))
        warte(300)
        self.assertEqual(len(self.uno_patches()), 1)
        self.assertFalse(self.b.zeit_eingabe.isVisible())

    def test_tastatur_ohne_maus(self):
        self.b.zeit.setFocus(Qt.FocusReason.TabFocusReason)
        QTest.keyClick(self.b.zeit, Qt.Key.Key_Space)
        self.assertTrue(self.b.zeit_eingabe.isVisible())
        QTest.keyClicks(self.b.zeit_eingabe, "6:15")
        QTest.keyClick(self.b.zeit_eingabe, Qt.Key.Key_Return)
        self.assertTrue(warte_bis(lambda: self.e.werte[CONTENT]["BeginTime"] == 375, 3000))

    def test_veraltete_uno_antwort_dreht_die_zeit_nicht_zurueck(self):
        o = self.b.overlay
        alt_stand, alte_antwort = o.countdown_stand, self.e.control()  # Abfrage, bevor getippt wurde
        self.tippen("12:30")
        self.assertTrue(warte_bis(lambda: self.e.werte[CONTENT]["BeginTime"] == 750, 3000))
        self.uno._zustand_uebernehmen(o, alte_antwort, alt_stand)  # kommt erst jetzt an
        self.assertEqual(o.dauer, 750)
        self.assertEqual(self.b.zeit.text(), "12:30")
        self.uno._zustand_uebernehmen(o, self.e.control(), o.countdown_stand)  # aktuelle Antwort gilt
        self.assertEqual(o.dauer, 750)

    def test_spaete_antwort_einer_frueheren_aenderung_gilt_nicht(self):
        """Unter Last gefunden: „+1 Min“, dann schnell „2:00“ getippt. Die Antwort zu „+1 Min“ kam spät,
        ihr Nachlesen zeigte kurz wieder die alte Zeit – und „−1 Min“ rechnete dann falsch."""
        o = self.b.overlay
        echt = self.uno._singular
        gehalten = []

        def singular(projekt, methode, pfad, daten, rueckruf):
            if methode == "PATCH" and daten == [{"subCompositionId": CONTENT, "payload": {"BeginTime": 360}}]:
                rueckruf_spaet = lambda *a: gehalten.append(lambda: rueckruf(*a))  # Antwort festhalten
                return echt(projekt, methode, pfad, daten, rueckruf_spaet)
            return echt(projekt, methode, pfad, daten, rueckruf)

        self.uno._singular = singular
        klick(self.b.dauer_knoepfe[60])  # 5:00 → 6:00, Antwort von Uno hängt
        self.assertTrue(warte_bis(lambda: gehalten, 3000))
        self.tippen("2:00")  # inzwischen getippt
        self.assertTrue(warte_bis(lambda: self.e.werte[CONTENT]["BeginTime"] == 120, 3000))
        self.assertTrue(warte_bis(lambda: o.dauer == 120, 3000))
        self.uno._abfrage.stop()  # nur die späte Antwort prüfen, nicht die regelmäßige Abfrage
        warte(100)
        # Die späte Antwort kommt an; ihr Nachlesen sieht bei Uno noch den Stand von „+1 Min“
        self.e.werte[CONTENT]["BeginTime"] = 360
        anfragen = len(self.netz.anfragen)
        gehalten.pop()()
        self.assertTrue(warte_bis(lambda: len(self.netz.anfragen) > anfragen, 3000))  # Nachlesen ist raus
        warte(200)
        self.assertEqual(o.dauer, 120)  # nicht zurückgedreht
        self.assertEqual(self.b.zeit.text(), "02:00")
        self.e.werte[CONTENT]["BeginTime"] = 120
        klick(self.b.dauer_knoepfe[-60])  # rechnet mit 2:00 weiter
        self.assertTrue(warte_bis(lambda: self.e.werte[CONTENT]["BeginTime"] == 60, 3000))

    def test_anderes_overlay_gewaehlt_schliesst_eingabe(self):
        self.tippen("8:00", taste=None)
        self.b.zeigen(self.b.overlay)
        self.assertFalse(self.b.zeit_eingabe.isVisible())
        self.assertTrue(self.b.zeit.isVisible())

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

    def test_niedriger_bildschirm_nichts_ueberlappt(self):
        """Kevins Bildschirm: Fenster 1903 × 971, OBS-Meldung mit „OBS starten“/„Neu verbinden“ sichtbar.
        Früher brauchte das Fenster über 1100 Pixel – Qt quetschte dann den grünen Start-Knopf über die
        Countdown-Zeit. Jetzt muss alles ohne Rollen passen, auch mit einem Hinweis unter der Zeit."""
        f = self.f
        f.meldungstext.setText("OBS wurde unerwartet beendet. Klicke auf „OBS starten“.")
        for w in (f.meldungsleiste, f.knopf_obs_starten, f.knopf_neu):
            w.show()
        warte(50)
        self.assertLessEqual(f.minimumSizeHint().height(), 900)
        f.resize(1903, 971)
        warte(200)
        b = self.b
        # Die OBS-Meldung steht in der Mitte, nimmt der rechten Spalte also keine Höhe weg
        self.assertGreater(f.meldungsleiste.mapTo(f, f.meldungsleiste.rect().topLeft()).x(),
                           f.bibliothek.mapTo(f, f.bibliothek.rect().topRight()).x())

        def passt_ohne_rollen():
            return not b.mitte_flaeche.verticalScrollBar().isVisible() and b.mitte.height() <= \
                b.mitte_flaeche.viewport().height()

        self.assertTrue(passt_ohne_rollen())
        b._hinweis_zeit(self.E.texte.meldung_countdown_live, False)  # Hinweis unter der Zeit
        warte(100)
        self.assertTrue(passt_ohne_rollen())
        b._hinweis_zeit("")
        warte(100)

        def unten(w):
            return w.mapTo(b, w.rect().bottomLeft()).y()

        def oben(w):
            return w.mapTo(b, w.rect().topLeft()).y()

        reihenfolge = [b.zeit, b.countdown_zustand, b.start, b.dauer_knoepfe[60], b.knopf_uebernehmen]
        for vorher, nachher in zip(reihenfolge, reihenfolge[1:]):
            self.assertLess(unten(vorher), oben(nachher), (vorher, nachher))
        self.assertEqual(b.zeit.height(), b.zeit.minimumHeight())  # die große Zeit wird nicht gequetscht
        # Einblenden/Ausblenden immer ganz zu sehen, ohne Rollen
        self.assertLessEqual(unten(b.ausblenden), b.height())
        self.assertGreaterEqual(oben(b.einblenden), b.mitte_flaeche.geometry().bottom())


class NeustartTest(Grundlage):
    """Fehler aus Build 1.1: Neustart mit schon eingefügtem Einzel-Uno.
    „Ausgewählt“ hing an einem leeren Platzhalter, zeigte „nicht erreichbar“ und reagierte nicht."""
    mit_uno = False

    def setUp(self):
        app()
        self.netz = FalschesInternet()
        self.E = internet_einstellungen(self.netz)
        self.speicher = Arbeitsspeicher()
        # wie nach dem ersten Einfügen gespeichert
        self.speicher.json_schreiben("uno", [{"name": "Countdown | Circles", "token": EINZEL_TOKEN, "einzeln": True}])
        self.obs = FalschesObs(passwort="geheim")
        oe, _ = obs_einstellungen(szenensammlung="")
        self.v = ObsVerbindung(oe, self.E.texte, zugang_finden=zugang(self.obs.port), obs_laeuft=lambda: True)
        self.m = ObsMotor(oe, self.E.texte, self.v, obs_laeuft=lambda: True)
        self.vs = Vorschau(self.v, self.E.vorschau)
        self.uno = UnoVerwaltung(self.E.uno, self.E.texte, self.speicher)
        self.twitch = TwitchKonto(self.E.twitch, self.E.texte, self.speicher)
        self.f = Hauptfenster(self.E, self.v, self.vs, self.m, self.uno, self.twitch)
        self.geoeffnet = []
        self.f.twitch_bereich._browser_oeffnen = self.geoeffnet.append
        self.f.resize(1600, 900)
        self.f.show()
        self.b = self.f.overlay_bedienfeld
        self.rote = []
        self.uno.meldung.connect(lambda t, fehler: self.rote.append(t) if fehler else None)

    def starten(self):
        # gleiche Reihenfolge wie im Programm (app.py): erst Fenster, dann laden
        self.uno.laden()
        self.twitch.laden()

    def test_neustart_alles_bedienbar(self):
        self.netz.verzoegerung = 0.3  # Uno antwortet etwas langsam, wie im echten Internet
        self.starten()
        self.assertTrue(warte_bis(lambda: self.b.overlay is not None, 3000))
        # während Uno gelesen wird: „Wird geladen …“, Knöpfe still aus, KEINE rote Meldung
        self.assertEqual(self.b.tally_text.text(), self.E.texte.overlay_texte_laden)
        self.assertFalse(self.b.einblenden.isEnabled())
        self.assertTrue(warte_bis(lambda: self.b.overlay.bereit, 5000))
        self.assertIs(self.b.overlay, self.uno.overlays[f"{EINZEL_TOKEN}/"])  # nicht am Platzhalter hängen
        self.assertEqual(self.b.tally_text.text(), self.E.texte.overlay_ausgeblendet)
        self.assertTrue(warte_bis(lambda: list(self.b.eingaben) == [(CONTENT, "Message")], 3000))
        self.assertTrue(self.b.countdown.isVisible())
        self.assertEqual(self.rote, [])
        self.assertFalse(self.b.meldung_schalter.isVisible())
        self.assertFalse(self.b.meldung_texte.isVisible())
        # alles bedienbar
        self.netz.verzoegerung = 0
        klick(self.b.einblenden)
        self.assertTrue(warte_bis(lambda: self.netz.einzel.komplett_sichtbar(), 3000))
        # erst klicken, wenn die Antwort von Uno auch im Fenster angekommen ist (sonst ist der Knopf noch aus)
        self.assertTrue(warte_bis(lambda: self.b.ausblenden.isEnabled(), 3000))
        klick(self.b.ausblenden)
        self.assertTrue(warte_bis(lambda: self.netz.einzel.ganz_aus(), 3000))
        klick(self.b.knopf_texte_neu)
        self.b.eingabe("Message").setText("Gleich!")
        klick(self.b.knopf_uebernehmen)
        self.assertTrue(warte_bis(lambda: self.netz.einzel.werte[CONTENT]["Message"] == "Gleich!", 3000))
        klick(self.b.start)
        self.assertTrue(warte_bis(lambda: self.netz.einzel.werte[CONTENT]["Timer"]["isRunning"], 3000))

    def test_uno_antwortet_gar_nicht_oberflaeche_bleibt_fluessig(self):
        self.netz.verzoegerung = 10  # Uno hängt
        self.starten()
        pause = groesste_pause_ms(3000)
        self.assertLess(pause, 250, f"Oberfläche hing {pause:.0f} ms")
        # Twitch-Bereich und Bibliothek reagieren währenddessen
        klick(self.f.bibliothek.knopf_einrichten)
        self.assertIs(self.f.bedienfelder.currentWidget(), self.f.uno_einrichtung)
        klick(self.f.uno_einrichtung.zurueck)
        # nach dem Zeitlimit: EINE Meldung „nicht erreichbar“, „Ausgewählt“ still ausgegraut
        self.assertTrue(warte_bis(lambda: self.rote, 4000))
        self.assertEqual(self.rote, [self.E.texte.meldung_uno_kein_internet])
        self.assertEqual(self.f.bibliothek.meldung.text(), self.E.texte.meldung_uno_kein_internet)
        self.assertFalse(self.b.meldung_schalter.isVisible())
        self.assertFalse(self.b.einblenden.isEnabled())
        # Uno ist wieder da → von selbst bereit, Meldung weg
        self.netz.verzoegerung = 0
        self.assertTrue(warte_bis(lambda: self.b.overlay is not None and self.b.overlay.bereit, 6000))
        self.assertTrue(warte_bis(lambda: not self.f.bibliothek.meldung.isVisible(), 3000))
        self.assertTrue(self.b.einblenden.isEnabled())

    def test_klick_waehrend_uno_haengt(self):
        self.starten()
        self.assertTrue(warte_bis(lambda: self.b.overlay is not None and self.b.overlay.bereit, 3000))
        self.netz.verzoegerung = 10
        klick(self.b.einblenden)
        self.assertFalse(self.b.einblenden.isEnabled())  # kein Doppelklick, solange es läuft
        pause = groesste_pause_ms(2500, lambda: self.b.einblenden.isEnabled())
        self.assertLess(pause, 250, f"Oberfläche hing {pause:.0f} ms")
        self.assertTrue(warte_bis(lambda: self.b.einblenden.isEnabled(), 2000))  # nach Zeitlimit wieder frei
        self.assertEqual(self.rote, [self.E.texte.meldung_uno_kein_internet])
        self.assertFalse(self.b.meldung_schalter.isVisible())  # nicht doppelt
        self.netz.verzoegerung = 0

    def test_passwortspeicher_haengt(self):
        """Der Passwortspeicher fragt nach dem Passwort (dauert): das Fenster bleibt flüssig."""
        self.speicher.verzoegerung = 2
        self.starten()
        pause = groesste_pause_ms(1500)
        self.assertLess(pause, 250, f"Oberfläche hing {pause:.0f} ms")
        self.assertTrue(warte_bis(lambda: self.b.overlay is not None and self.b.overlay.bereit, 6000))

    def test_einzel_uno_kann_befehl_nicht(self):
        """400 „Invalid command“ beim Lesen: still, keine rote Meldung, Rest bedienbar."""
        self.speicher.json_schreiben("uno", [{"name": "Uno-Projekt 1", "token": UNO_TOKEN}])
        self.netz.unbekannte_befehle.add("GetOverlayContent")
        self.starten()
        self.assertTrue(warte_bis(lambda: self.b.overlay is not None, 3000))
        self.assertTrue(warte_bis(lambda: self.b.texte.isHidden(), 3000))  # Texte still ausgegraut
        self.assertEqual(self.rote, [])
        self.assertFalse(self.b.meldung_texte.isVisible())
        klick(self.b.einblenden)
        self.assertTrue(warte_bis(lambda: self.netz.overlays[0]["visible"], 3000))


class GesperrteKnoepfeTest(Grundlage):
    """Ausgegraute Knöpfe sagen, warum: beim Drüberfahren (Hinweis) und beim Anklicken (kurze Meldung)."""
    mit_uno = False

    def setUp(self):
        super().setUp()
        self.e = self.netz.einzel
        e = self.f.uno_einrichtung
        e._zwischenablage = lambda: EINZEL_ADRESSE_TEXT
        klick(e.einfuegen)
        self.assertTrue(warte_bis(lambda: e.meldung.text() == self.E.texte.meldung_uno_einzel_ok, 3000))
        klick(e.zurueck)
        self.b = self.f.overlay_bedienfeld
        self.assertTrue(warte_bis(lambda: self.b.overlay is not None and self.b.countdown.isVisible()
                                  and self.b.eingaben and self.b.knopf_texte_neu.isEnabled(), 3000))
        QToolTip.hideText()

    def tearDown(self):
        QToolTip.hideText()
        super().tearDown()

    def hinweis_beim_drueberfahren(self, k):
        """Was Qt beim Drüberfahren anzeigt (das Hinweis-Ereignis, das Qt nach kurzem Stillhalten schickt)."""
        QToolTip.hideText()
        self.assertTrue(warte_bis(lambda: not QToolTip.isVisible(), 2000))  # Qt schließt mit kurzer Verzögerung
        punkt = k.rect().center()
        QApplication.sendEvent(k, QHelpEvent(QEvent.Type.ToolTip, punkt, k.mapToGlobal(punkt)))
        return QToolTip.text() if QToolTip.isVisible() else ""

    def alle_gesperrten_sagen_warum(self, zustand):
        """Kein sichtbarer ausgegrauter Knopf im ganzen Fenster bleibt stumm."""
        gefunden = 0
        for k in self.f.findChildren(QPushButton):
            if k.isVisible() and not k.isEnabled():
                gefunden += 1
                text = gesperrt_text(k)
                self.assertTrue(text, f"{zustand}: „{k.text()}“ ist ausgegraut und sagt nicht, warum")
                self.assertNotEqual(text, self.E.texte.gesperrt_moment, f"{zustand}: „{k.text()}“ zu allgemein")
                self.assertEqual(self.hinweis_beim_drueberfahren(k), text, f"{zustand}: {k.text()}")
                self.assertEqual(k.cursor().shape(), Qt.CursorShape.ForbiddenCursor, k.text())
        return gefunden

    # --- Kein Knopf vergessen ----------------------------------------------------
    def test_jeder_knopf_der_ausgegraut_werden_kann_hat_einen_hinweis(self):
        """Liest den Programmtext: Jeder Knopf, der irgendwo gesperrt wird, muss einen Hinweis haben."""
        ordner = Path(overlay_bereich.__file__).parent
        besitzer = [self.b, self.f.uno_einrichtung, self.f.twitch_bereich, self.f.bibliothek, self.f,
                    self.f.shot_bedienfeld, self.f.shot_neu, self.f.shot_leiste, self.f.wenn_dann]
        namen, gruppen = set(), set()
        for datei in sorted(ordner.glob("*.py")):
            text = datei.read_text()
            namen |= set(re.findall(r"self\.(\w+)\.set(?:Enabled|Disabled)\(", text))
            for liste, rumpf in re.findall(r"for \w+ in ([^\n]+):\n((?:[ ]{12,}.*\n){1,3})", text):
                if "setEnabled" in rumpf or "setDisabled" in rumpf:
                    namen |= set(re.findall(r"self\.(\w+)", liste))
        self.assertGreaterEqual(len(namen), 9, namen)  # alle Stellen gefunden (Stand Build 1.1: 9)
        for name in sorted(namen):
            ziel = next((getattr(o, name) for o in besitzer if hasattr(o, name)), None)
            self.assertIsNotNone(ziel, name)
            knoepfe = list(ziel.values()) if isinstance(ziel, dict) else [ziel]
            for k in knoepfe:
                self.assertTrue(hasattr(k, "_gesperrt_hinweis"), f"{name} („{k.text()}“) hat keinen Hinweis")

    def test_in_jedem_zustand_sagen_alle_gesperrten_warum(self):
        t = self.E.texte
        n = self.alle_gesperrten_sagen_warum("ausgeblendet, bereit")
        self.assertEqual(n, 2)  # Pause und Ausblenden
        klick(self.b.start)
        self.assertTrue(warte_bis(lambda: self.b.pause.isEnabled(), 3000))
        self.alle_gesperrten_sagen_warum("Countdown läuft")
        klick(self.b.einblenden)
        self.assertTrue(warte_bis(lambda: self.b.overlay.sichtbar is True and self.b.ausblenden.isEnabled(), 3000))
        self.alle_gesperrten_sagen_warum("im Stream")
        self.b.overlay.beschaeftigt = True
        self.b._zustand_zeigen()
        self.alle_gesperrten_sagen_warum("schaltet gerade")
        self.b.overlay.beschaeftigt = False
        self.b._zustand_zeigen()
        self.b.texte_laden()
        self.alle_gesperrten_sagen_warum("Texte werden geladen")
        self.assertTrue(warte_bis(lambda: self.b.knopf_texte_neu.isEnabled(), 3000))
        self.b.eingabe("Message").setText("Neu")
        self.netz.verzoegerung = 3.0  # Uno antwortet langsam: Knopf bleibt solange gesperrt
        klick(self.b.knopf_uebernehmen)
        self.assertEqual(gesperrt_text(self.b.knopf_uebernehmen), t.gesperrt_texte_senden)
        self.assertGreaterEqual(self.alle_gesperrten_sagen_warum("Texte werden übernommen"), 1)
        self.netz.verzoegerung = 0.0
        self.assertTrue(warte_bis(lambda: self.b.knopf_uebernehmen.isEnabled(), 6000))

    # --- Die einzelnen Gründe ----------------------------------------------------
    def test_ausblenden_wenn_schon_ausgeblendet(self):
        t = self.E.texte
        k = self.b.ausblenden
        self.assertFalse(k.isEnabled())
        self.assertEqual(self.hinweis_beim_drueberfahren(k), t.gesperrt_schon_aus)
        self.assertEqual(k.cursor().shape(), Qt.CursorShape.ForbiddenCursor)
        vorher = len(self.netz.einzel_befehle)
        QTest.mouseClick(k, Qt.MouseButton.LeftButton)
        self.assertTrue(self.b.meldung_schalter.isVisible())
        self.assertEqual(self.b.meldung_schalter.text(), t.gesperrt_schon_aus)
        self.assertEqual(self.b.meldung_schalter.objectName(), "meldung")  # Hinweis, kein roter Fehler
        warte(300)
        self.assertEqual(len(self.netz.einzel_befehle), vorher)  # nichts an Uno geschickt
        self.assertFalse(self.b.overlay.sichtbar)
        # verschwindet von selbst
        self.assertTrue(warte_bis(lambda: not self.b.meldung_schalter.isVisible(), overlay_bereich.HINWEIS_MS + 1500))
        # Einblenden: jetzt ist Einblenden gesperrt, Ausblenden frei – und ohne Sperr-Hinweis
        klick(self.b.einblenden)
        self.assertTrue(warte_bis(lambda: self.b.ausblenden.isEnabled(), 3000))
        self.assertEqual(self.hinweis_beim_drueberfahren(self.b.einblenden), t.gesperrt_schon_ein)
        self.assertEqual(self.hinweis_beim_drueberfahren(self.b.ausblenden), "")
        self.assertEqual(self.b.ausblenden.cursor().shape(), Qt.CursorShape.PointingHandCursor)
        klick(self.b.ausblenden)  # freier Knopf wirkt ganz normal
        self.assertTrue(warte_bis(lambda: self.b.overlay.sichtbar is False, 3000))

    def test_waehrend_umgeschaltet_wird(self):
        self.b.overlay.beschaeftigt = True
        self.b._zustand_zeigen()
        for k in (self.b.einblenden, self.b.ausblenden):
            self.assertFalse(k.isEnabled())
            self.assertEqual(gesperrt_text(k), self.E.texte.gesperrt_schaltet)

    def test_pause_und_start(self):
        t = self.E.texte
        self.assertEqual(self.hinweis_beim_drueberfahren(self.b.pause), t.gesperrt_pause)
        QTest.mouseClick(self.b.pause, Qt.MouseButton.LeftButton)
        self.assertEqual(self.b.meldung_zeit.text(), t.gesperrt_pause)
        self.assertEqual(self.b.meldung_zeit.objectName(), "meldung")
        self.assertTrue(self.b.meldung_zeit.isVisible())
        self.assertFalse(self.e.werte[CONTENT]["Timer"].get("isRunning"))
        klick(self.b.start)
        self.assertTrue(warte_bis(lambda: self.b.countdown_zustand.text() == t.countdown_laeuft, 3000))
        self.assertEqual(self.hinweis_beim_drueberfahren(self.b.start), t.gesperrt_start_laeuft)
        QTest.mouseClick(self.b.start, Qt.MouseButton.LeftButton)
        self.assertEqual(self.b.meldung_zeit.text(), t.gesperrt_start_laeuft)
        self.assertEqual(self.hinweis_beim_drueberfahren(self.b.pause), "")  # frei
        self.assertTrue(warte_bis(lambda: not self.b.meldung_zeit.isVisible(), overlay_bereich.HINWEIS_MS + 1500))

    def test_start_wenn_abgelaufen(self):
        t = self.E.texte
        QTest.mouseClick(self.b.zeit, Qt.MouseButton.LeftButton)
        QTest.keyClicks(self.b.zeit_eingabe, "0:01")
        QTest.keyClick(self.b.zeit_eingabe, Qt.Key.Key_Return)
        self.assertTrue(warte_bis(lambda: self.e.werte[CONTENT]["BeginTime"] == 1, 3000))
        klick(self.b.start)
        self.assertTrue(warte_bis(lambda: self.b.countdown_zustand.text() == t.countdown_abgelaufen, 4000))
        self.assertFalse(self.b.start.isEnabled())
        self.assertEqual(self.hinweis_beim_drueberfahren(self.b.start), t.gesperrt_start_abgelaufen)
        QTest.mouseClick(self.b.start, Qt.MouseButton.LeftButton)
        self.assertEqual(self.b.meldung_zeit.text(), t.gesperrt_start_abgelaufen)
        self.alle_gesperrten_sagen_warum("abgelaufen")

    def test_dauer_knoepfe_ohne_dauer(self):
        self.b.overlay.bauplan.dauer = ""
        self.b._zustand_zeigen()
        for k in self.b.dauer_knoepfe.values():
            self.assertFalse(k.isEnabled())
            self.assertEqual(self.hinweis_beim_drueberfahren(k), self.E.texte.gesperrt_keine_dauer)

    def test_texte_knoepfe(self):
        t = self.E.texte
        self.b.texte_laden()
        self.assertFalse(self.b.knopf_texte_neu.isEnabled())
        self.assertEqual(self.hinweis_beim_drueberfahren(self.b.knopf_texte_neu), t.gesperrt_texte_laden)
        QTest.mouseClick(self.b.knopf_texte_neu, Qt.MouseButton.LeftButton)
        self.assertEqual(self.b.meldung_texte.text(), t.gesperrt_texte_laden)
        self.assertTrue(warte_bis(lambda: self.b.knopf_texte_neu.isEnabled(), 3000))
        # Overlay ganz ohne Texte
        self.b._felder_aufbauen([], t.overlay_keine_texte)
        self.assertEqual(self.hinweis_beim_drueberfahren(self.b.knopf_uebernehmen), t.gesperrt_keine_texte)

    def test_uno_noch_nicht_gelesen(self):
        o = self.b.overlay
        o.bauplan, alt = None, o.bauplan
        self.b._zustand_zeigen()
        for k in (self.b.einblenden, self.b.ausblenden, self.b.knopf_uebernehmen, self.b.knopf_texte_neu):
            self.assertFalse(k.isEnabled())
            self.assertEqual(gesperrt_text(k), self.E.texte.gesperrt_uno_laedt, k.text())
        self.alle_gesperrten_sagen_warum("Uno wird gelesen")
        o.bauplan = alt

    def test_uno_einfuegen_waehrend_eingefuegt_wird(self):
        t = self.E.texte
        e = self.f.uno_einrichtung
        self.f.bibliothek.knopf_einrichten.click()
        self.assertTrue(warte_bis(lambda: e.isVisible(), 2000))
        e.einfuegen.setEnabled(False)  # wie während des Einfügens
        e.meldung.zeigen("…")
        self.assertEqual(self.hinweis_beim_drueberfahren(e.einfuegen), t.gesperrt_einfuegen)
        QTest.mouseClick(e.einfuegen, Qt.MouseButton.LeftButton)
        self.assertEqual(e.meldung.text(), t.gesperrt_einfuegen)
        self.alle_gesperrten_sagen_warum("Uno wird eingefügt")
        # danach steht wieder da, was vorher da stand
        self.assertTrue(warte_bis(lambda: e.meldung.text() == "…", overlay_bereich.HINWEIS_MS + 1500))
        e.einfuegen.setEnabled(True)

    def test_echtes_drueberfahren_mit_der_maus(self):
        k = self.b.ausblenden
        QTest.mouseMove(self.f, self.f.mapFromGlobal(k.mapToGlobal(QPoint(5, 5))))
        QTest.mouseMove(k, k.rect().center())
        self.assertTrue(warte_bis(lambda: QToolTip.isVisible(), 3000), "kein Hinweis beim Drüberfahren")
        self.assertEqual(QToolTip.text(), self.E.texte.gesperrt_schon_aus)

    # --- Die kurze Meldung ---------------------------------------------------------
    def test_kurze_meldung_verdeckt_keine_echte_meldung(self):
        m = self.b.meldung_schalter
        m.zeigen("Uno antwortet nicht.", False)
        m.kurz_zeigen("Ist schon ausgeblendet.", 200)
        self.assertEqual(m.objectName(), "meldung")
        m.kurz_zeigen("Ist schon ausgeblendet.", 200)  # zweimal geklickt: merkt sich trotzdem das Original
        self.assertTrue(warte_bis(lambda: m.text() == "Uno antwortet nicht.", 2000))
        self.assertEqual(m.objectName(), "fehler")  # wieder rot wie vorher
        # Kommt währenddessen eine echte Rückmeldung, bleibt die stehen
        m.zeigen("")
        m.kurz_zeigen("Ist schon ausgeblendet.", 200)
        m.zeigen("Eingeblendet.", True)
        warte(400)
        self.assertEqual(m.text(), "Eingeblendet.")
        self.assertEqual(m.objectName(), "gut")


class TwitchFensterTest(Grundlage):
    mit_uno = False

    def test_titel_knopf_gesperrt_sagt_warum(self):
        tb = self.f.twitch_bereich
        tb.uebernehmen.setEnabled(False)  # wie während der Titel geändert wird
        punkt = tb.uebernehmen.rect().center()
        QApplication.sendEvent(tb.uebernehmen, QHelpEvent(QEvent.Type.ToolTip, punkt, tb.uebernehmen.mapToGlobal(punkt)))
        self.assertEqual(gesperrt_text(tb.uebernehmen), self.E.texte.gesperrt_titel)
        QTest.mouseClick(tb.uebernehmen, Qt.MouseButton.LeftButton)
        self.assertEqual(tb.meldung.text(), self.E.texte.gesperrt_titel)
        QToolTip.hideText()

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

    def test_ohne_client_id_knopf_ausgegraut_und_sagt_warum(self):
        tb = self.f.twitch_bereich
        self.twitch.client_id = ""  # wie mit leerer client_id in einstellungen.toml
        self.twitch.zustand = Anmeldung.NICHT_EINGERICHTET
        tb._zustand(self.twitch.zustand)
        self.assertTrue(tb.anmelden.isVisible())
        self.assertFalse(tb.anmelden.isEnabled())
        self.assertEqual(gesperrt_text(tb.anmelden), self.E.texte.gesperrt_twitch_client_id)
        QTest.mouseClick(tb.anmelden, Qt.MouseButton.LeftButton)
        self.assertEqual(tb.meldung.text(), self.E.texte.gesperrt_twitch_client_id)
        self.assertIs(self.twitch.zustand, Anmeldung.NICHT_EINGERICHTET)  # Klick löst nichts aus

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
