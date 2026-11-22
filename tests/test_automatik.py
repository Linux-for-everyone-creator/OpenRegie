"""Build 1.2, Teil B: Wenn-dann-Regeln, Register, Zeitplan – und dass ohne aktive Regel nichts läuft."""

import json
import stat
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QStandardItemModel

from openregie import einstellungen
from openregie.automatik import register
from openregie.automatik.motor import Automatik, Regel
from openregie.automatik.zeitplan import Termin, naechster
from openregie.obs.quellen import ObsQuellen
from openregie.obs.verbindung import ObsVerbindung, Sendung

from .falsches_obs import FalschesObs
from .hilfen import app, obs_einstellungen, warte, warte_bis, zugang


class _Overlay:
    def __init__(self, name):
        self.name = name
        self.sichtbar = False


class UnoAttrappe(QObject):
    liste_geaendert = Signal()

    def __init__(self):
        super().__init__()
        self.overlays = {"p1/o1": _Overlay("Bauchbinde"), "p1/o2": _Overlay("Countdown")}
        self.befehle = []

    def sichtbar_setzen(self, overlay, sichtbar, fertig=None):
        overlay.sichtbar = sichtbar
        self.befehle.append((overlay.name, sichtbar))


class AutomatikGrundlage(unittest.TestCase):
    def setUp(self):
        app()
        self.E = einstellungen.lade()
        self.ordner = tempfile.TemporaryDirectory()
        self.datei = Path(self.ordner.name) / "automatik.json"
        self.obs = FalschesObs(passwort="geheim")
        self.obs.quelle_anlegen("Szene 1", "Mikrofon", "pulse_input_capture")
        self.obs.quelle_anlegen("Szene 1", "Kamerabild", "v4l2_input")
        oe, _ = obs_einstellungen(szenensammlung="")
        self.v = ObsVerbindung(oe, self.E.texte, zugang_finden=zugang(self.obs.port), obs_laeuft=lambda: True)
        self.q = ObsQuellen(self.v, self.E.texte, self.E.quellen)
        self.uno = UnoAttrappe()
        self.a = Automatik(self.E.texte, self.v, self.q, self.uno, datei=self.datei)
        self.v.starten()
        self.assertTrue(warte_bis(lambda: self.v.verbunden and self.v.szene, 3000))
        self.a.laden()
        self.assertTrue(warte_bis(lambda: self.a.geladen, 2000))

    def tearDown(self):
        self.a.beenden()  # wartet, bis alles gespeichert ist
        self.v.beenden()
        self.obs.beenden()
        self.ordner.cleanup()
        warte(20)

    def wecker(self):
        return [t for t in self.a.findChildren(QTimer) if t.isActive()]

    def gespeichert(self):
        warte_bis(lambda: self.datei.exists() and self.a._hintergrund.offen == 0, 2000)
        return json.loads(self.datei.read_text())


class LeerlaufTest(AutomatikGrundlage):
    def test_ohne_regel_laeuft_nichts(self):
        self.assertFalse(self.a.laeuft)
        self.assertEqual(self.a.eingerichtet, {})
        self.assertEqual(self.wecker(), [])
        vorher = len(self.obs.anfragen)
        self.obs.stream_starten()
        self.obs.szene_wechseln("Pause")
        warte(500)
        neu = [a for a, _ in self.obs.anfragen[vorher:]]
        # Nur die Grundabfrage der Verbindung (On-Air alle 5 s) – nichts von der Automatik
        self.assertTrue(set(neu) <= {"GetStreamStatus"}, neu)
        self.assertEqual(self.a.ausloesungen, 0)

    def test_nur_ausgeschaltete_regeln_laufen_nicht(self):
        self.a.regel_speichern(Regel("stream_startet", "shot_live", dann_wert="Pause", aktiv=False))
        self.a.regel_speichern(Regel("zeitplan_start", "overlay_ein", dann_wert="p1/o1", aktiv=False))
        self.a.zeitplan_setzen([Termin(0, 19, 0)])
        self.assertFalse(self.a.laeuft)
        self.assertEqual(self.wecker(), [])
        self.obs.stream_starten()
        warte(400)
        self.assertEqual(self.obs.szene, "Szene 1")

    def test_unvollstaendige_regel_laeuft_nicht(self):
        self.a.regel_speichern(Regel("stream_startet", "shot_live", dann_wert=None))
        self.assertFalse(self.a.laeuft)

    def test_nach_dem_ausschalten_wieder_still(self):
        r = Regel("zeitplan_start", "overlay_ein", dann_wert="p1/o1")
        self.a.zeitplan_setzen([Termin(0, 19, 0)])
        self.a.regel_speichern(r)
        self.assertTrue(self.a.laeuft)
        self.assertEqual(len(self.wecker()), 1)  # genau ein Wecker, kein Takt
        self.a.regel_aktiv(r.kennung, False)
        warte(50)
        self.assertFalse(self.a.laeuft)
        self.assertEqual(self.wecker(), [])


class RegelTest(AutomatikGrundlage):
    def test_stream_startet_dann_shot(self):
        self.a.regel_speichern(Regel("stream_startet", "shot_live", dann_wert="Pause"))
        self.assertTrue(self.a.laeuft)
        self.obs.stream_starten()
        self.assertTrue(warte_bis(lambda: self.obs.szene == "Pause", 3000))

    def test_stream_endet_dann_overlay_aus(self):
        self.uno.overlays["p1/o1"].sichtbar = True
        self.a.regel_speichern(Regel("stream_endet", "overlay_aus", dann_wert="p1/o1"))
        self.obs.stream_starten()
        warte(200)
        self.assertEqual(self.uno.befehle, [])
        self.obs.stream_stoppen()
        self.assertTrue(warte_bis(lambda: self.uno.befehle == [("Bauchbinde", False)], 3000))

    def test_shot_live_dann_ton_stumm(self):
        self.a.regel_speichern(Regel("shot_live", "ton_aus", wenn_wert="Pause", dann_wert="Mikrofon"))
        self.obs.szene_wechseln("Szene 1")
        warte(200)
        self.assertNotIn("SetInputMute", [a for a, _ in self.obs.anfragen])
        self.obs.szene_wechseln("Pause")
        self.assertTrue(warte_bis(lambda: ("SetInputMute", {"inputName": "Mikrofon", "inputMuted": True})
                                  in self.obs.anfragen, 3000))

    def test_ausgeschaltet_reagiert_nicht(self):
        r = Regel("stream_startet", "shot_live", dann_wert="Pause")
        self.a.regel_speichern(r)
        self.a.regel_aktiv(r.kennung, False)
        self.obs.stream_starten()
        warte(400)
        self.assertEqual(self.obs.szene, "Szene 1")

    def test_kein_ping_pong(self):
        """Zwei Regeln schalten sich gegenseitig um – das darf nicht endlos laufen."""
        self.a.regel_speichern(Regel("shot_live", "shot_live", wenn_wert="Pause", dann_wert="Szene 1"))
        self.a.regel_speichern(Regel("shot_live", "shot_live", wenn_wert="Szene 1", dann_wert="Pause"))
        self.obs.szene_wechseln("Pause")
        warte(1200)
        self.assertLessEqual(self.a.ausloesungen, 3)

    def test_overlay_gibt_es_nicht_mehr(self):
        self.a.regel_speichern(Regel("stream_startet", "overlay_ein", dann_wert="weg/weg"))
        self.obs.stream_starten()
        warte(300)
        self.assertEqual(self.uno.befehle, [])  # kein Absturz, nur ein Eintrag im Protokoll

    def test_zeitplan_wecker_klingelt(self):
        bald = datetime.now() + timedelta(milliseconds=400)
        self.a.naechster_termin = lambda jetzt=None: bald if datetime.now() < bald else bald + timedelta(days=7)
        self.a.regel_speichern(Regel("zeitplan_start", "overlay_ein", dann_wert="p1/o2"))
        self.assertTrue(warte_bis(lambda: self.uno.befehle == [("Countdown", True)], 3000))
        self.assertEqual(len(self.wecker()), 1)  # neu gestellt auf nächste Woche


class SpeichernTest(AutomatikGrundlage):
    def test_speichern_und_wieder_laden(self):
        r = Regel("shot_live", "overlay_ein", wenn_wert="Pause", dann_wert="p1/o1")
        self.a.regel_speichern(r)
        self.a.zeitplan_setzen([Termin(4, 19, 0), Termin(1, 18, 30)])
        daten = self.gespeichert()
        self.assertEqual(daten["regeln"][0]["wenn"], {"art": "shot_live", "wert": "Pause"})
        self.assertEqual(daten["zeitplan"], [{"tag": 1, "zeit": "18:30"}, {"tag": 4, "zeit": "19:00"}])
        self.assertEqual(stat.S_IMODE(self.datei.stat().st_mode), 0o600)  # nur für den eigenen Benutzer
        b = Automatik(self.E.texte, self.v, self.q, self.uno, datei=self.datei)
        b.laden()
        self.assertTrue(warte_bis(lambda: b.geladen, 2000))
        self.assertEqual([x.als_dict() for x in b.regeln], [r.als_dict()])
        self.assertEqual(b.zeitplan, [Termin(1, 18, 30), Termin(4, 19, 0)])
        self.assertTrue(b.laeuft)
        b.beenden()

    def test_bearbeiten_ersetzt(self):
        r = Regel("stream_startet", "shot_live", dann_wert="Pause")
        self.a.regel_speichern(r)
        self.a.regel_speichern(Regel("stream_startet", "shot_live", dann_wert="Szene 1", kennung=r.kennung))
        self.assertEqual(len(self.a.regeln), 1)
        self.assertEqual(self.a.regeln[0].dann_wert, "Szene 1")
        self.a.regel_loeschen(r.kennung)
        self.assertEqual(self.gespeichert()["regeln"], [])

    def test_kaputte_datei(self):
        self.datei.write_text("{ kaputt")
        b = Automatik(self.E.texte, self.v, self.q, self.uno, datei=self.datei)
        meldungen = []
        b.meldung.connect(lambda t, f: meldungen.append((t, f)))
        b.laden()
        self.assertTrue(warte_bis(lambda: b.geladen, 2000))
        self.assertEqual(b.regeln, [])
        self.assertEqual(meldungen, [(self.E.texte.meldung_automatik_lesen, True)])
        b.beenden()


class ZeitplanTest(unittest.TestCase):
    def test_naechster(self):
        mittwoch = datetime(2026, 11, 25, 12, 0)  # Mittwoch
        termine = [Termin(4, 19, 0), Termin(1, 18, 0)]  # Fr 19:00, Di 18:00
        self.assertEqual(naechster(termine, mittwoch), datetime(2026, 11, 27, 19, 0))
        self.assertEqual(naechster([Termin(2, 11, 0)], mittwoch), datetime(2026, 12, 2, 11, 0))  # heute vorbei
        self.assertEqual(naechster([Termin(2, 12, 0)], mittwoch), datetime(2026, 12, 2, 12, 0))  # genau jetzt
        self.assertEqual(naechster([Termin(2, 12, 1)], mittwoch), datetime(2026, 11, 25, 12, 1))
        self.assertIsNone(naechster([], mittwoch))

    def test_termin_lesen(self):
        self.assertEqual(Termin.aus_dict({"tag": 4, "zeit": "19:05"}), Termin(4, 19, 5))
        for falsch in ({"tag": 7, "zeit": "19:00"}, {"tag": 1, "zeit": "25:00"}, {"tag": 1}, {"zeit": "x"}):
            self.assertIsNone(Termin.aus_dict(falsch))
        self.assertEqual(Termin(4, 9, 5).text(), "Fr 09:05")


class RegisterTest(AutomatikGrundlage):
    """Neue Auslöser/Aktionen (z. B. in Build 1.3) lassen sich einfach eintragen."""

    def setUp(self):
        super().setUp()
        self.eingerichtet, self.abgebaut, self.ausgefuehrt = [], [], []
        self.ausloesen = None

        def einrichten(_u, wert, ausloesen):
            self.eingerichtet.append(wert)
            self.ausloesen = ausloesen
            return lambda: self.abgebaut.append(wert)

        register.ausloeser_eintragen(register.Ausloeser("test_pegel", "test", register.KEINE, einrichten))
        register.aktion_eintragen(register.Aktion("test_aktion", "test", register.KEINE,
                                                  lambda u, w: self.ausgefuehrt.append(w)))

    def tearDown(self):
        register.AUSLOESER.pop("test_pegel", None)
        register.AKTIONEN.pop("test_aktion", None)
        register.GRUPPEN.remove("test")
        super().tearDown()

    def test_eigener_ausloeser_nur_mit_aktiver_regel(self):
        r = Regel("test_pegel", "test_aktion", aktiv=False)
        self.a.regel_speichern(r)
        self.assertEqual(self.eingerichtet, [])  # nichts eingerichtet, solange aus
        self.a.regel_aktiv(r.kennung, True)
        self.assertEqual(self.eingerichtet, [None])
        self.ausloesen()
        self.assertEqual(self.ausgefuehrt, [None])
        self.a.regel_aktiv(r.kennung, False)
        self.assertEqual(self.abgebaut, [None])  # sauber abgebaut
        self.assertIn(("test", [register.AUSLOESER["test_pegel"]]), register.nach_gruppen(register.AUSLOESER))


# ---------------------------------------------------------------------------
#  Im Fenster
# ---------------------------------------------------------------------------
from .test_fenster import Grundlage, klick  # noqa: E402


class WennDannFensterTest(Grundlage):
    mit_uno = False

    def setUp(self):
        super().setUp()
        self.ordner = tempfile.TemporaryDirectory()
        self.datei = Path(self.ordner.name) / "automatik.json"
        # eigene Automatik mit Wegwerf-Datei
        self.a = Automatik(self.E.texte, self.v, self.f.quellen, self.uno, datei=self.datei)
        from openregie.oberflaeche.wenn_dann import WennDannFenster
        self.f.automatik = self.a
        self.f.wenn_dann = WennDannFenster(self.E, self.a, self.f)
        self.a.geaendert.connect(self.f._automatik_zeigen)
        self.a.laden()
        self.assertTrue(warte_bis(lambda: self.a.geladen, 2000))
        self.m.starten()
        self.assertTrue(warte_bis(lambda: self.v.verbunden, 3000))
        self.w = self.f.wenn_dann

    def tearDown(self):
        self.w.close()
        self.a.beenden()
        super().tearDown()
        self.ordner.cleanup()

    def waehle(self, liste, wert):
        self.assertTrue(warte_bis(lambda: wert in liste.werte(), 3000), (wert, liste.werte()))
        liste.setCurrentIndex(next(i for i in range(liste.count()) if liste.itemData(i) == wert))

    def test_fenster_oeffnen_und_regel_anlegen(self):
        t = self.E.texte
        klick(self.f.knopf_wenn_dann)
        self.assertTrue(self.w.isVisible())
        self.assertEqual(self.w.zustand.text(), t.automatik_ruht)
        klick(self.w.neue_regel)
        self.assertIs(self.w.seiten.currentWidget(), self.w.seite_editor)
        self.assertFalse(self.w.speichern.isEnabled())
        from openregie.oberflaeche.bausteine import gesperrt_text
        self.assertEqual(gesperrt_text(self.w.speichern), t.gesperrt_regel_wenn)
        self.waehle(self.w.wenn_liste, "stream_startet")
        self.assertFalse(self.w.wenn_wahl.isVisible())  # braucht keine zweite Auswahl
        self.assertEqual(gesperrt_text(self.w.speichern), t.gesperrt_regel_dann)
        self.waehle(self.w.dann_liste, "shot_live")
        self.assertTrue(self.w.dann_wahl.isVisible())
        self.assertEqual(gesperrt_text(self.w.speichern), t.gesperrt_regel_wahl)
        self.waehle(self.w.dann_wahl, "Pause")
        self.assertTrue(self.w.speichern.isEnabled())
        self.assertIn("Pause", self.w.vorschau.text())
        klick(self.w.speichern)
        self.assertIs(self.w.seiten.currentWidget(), self.w.seite_regeln)
        self.assertEqual(len(self.a.regeln), 1)
        self.assertEqual(len(self.w._zeilen), 1)
        self.assertEqual(self.w.zustand.text(), t.automatik_laeuft.format(anzahl=1))
        self.assertEqual(self.f.knopf_wenn_dann.text(), t.knopf_wenn_dann_aktiv.format(anzahl=1))
        self.assertTrue(warte_bis(lambda: self.datei.exists(), 2000))
        # und sie wirkt
        self.obs.stream_starten()
        self.assertTrue(warte_bis(lambda: self.obs.szene == "Pause", 3000))

    def test_gruppen_in_der_liste(self):
        klick(self.f.knopf_wenn_dann)
        klick(self.w.neue_regel)
        liste = self.w.dann_liste
        modell: QStandardItemModel = liste.model()
        texte = [modell.item(i).text().strip() for i in range(modell.rowCount())]
        for gruppe in ("SZENEN", "OVERLAYS", "TON"):
            self.assertIn(gruppe, texte)
            zeile = texte.index(gruppe)
            self.assertFalse(modell.item(zeile).isEnabled())  # Überschrift nicht wählbar
        self.assertGreaterEqual(liste.maxVisibleItems(), 10)  # große Scrollfläche
        self.assertGreaterEqual(liste.height(), self.E.groessen.knopf_hoehe - 8)

    def test_bearbeiten_an_aus_loeschen(self):
        t = self.E.texte
        r = Regel("stream_startet", "shot_live", dann_wert="Pause")
        self.a.regel_speichern(r)
        klick(self.f.knopf_wenn_dann)
        z = self.w._zeilen[0]
        klick(z.schalter)
        self.assertFalse(self.a.regeln[0].aktiv)
        self.assertFalse(self.a.laeuft)
        self.assertEqual(self.w._zeilen[0].schalter.text(), t.regel_aus)
        klick(self.w._zeilen[0].schalter)
        self.assertTrue(self.a.laeuft)
        klick(self.w._zeilen[0].bearbeiten)
        self.assertEqual(self.w.wenn_liste.wert(), "stream_startet")
        self.assertTrue(warte_bis(lambda: self.w.dann_wahl.wert() == "Pause", 3000))
        self.waehle(self.w.dann_liste, "overlay_ein")
        self.assertFalse(self.w.speichern.isEnabled())  # Overlay fehlt (kein Uno-Projekt)
        self.waehle(self.w.dann_liste, "ton_aus")
        self.obs.quelle_anlegen("Szene 1", "Mikrofon", "pulse_input_capture")
        self.waehle(self.w.dann_liste, "shot_live")
        self.waehle(self.w.dann_wahl, "Szene 1")
        klick(self.w.speichern)
        self.assertEqual(len(self.a.regeln), 1)
        self.assertEqual((self.a.regeln[0].kennung, self.a.regeln[0].dann_wert), (r.kennung, "Szene 1"))
        z = self.w._zeilen[0]
        klick(z.loeschen)
        self.assertEqual(z.loeschen.text(), t.knopf_wirklich_loeschen)
        self.assertEqual(len(self.a.regeln), 1)
        klick(z.loeschen)
        self.assertEqual(self.a.regeln, [])
        self.assertTrue(self.w.leer.isVisible())

    def test_ton_liste_kommt_von_obs(self):
        self.obs.quelle_anlegen("Szene 1", "Mikrofon", "pulse_input_capture")
        self.obs.quelle_anlegen("Szene 1", "Desktop-Ton", "pulse_output_capture")
        klick(self.f.knopf_wenn_dann)
        klick(self.w.neue_regel)
        self.waehle(self.w.dann_liste, "ton_aus")
        self.assertTrue(warte_bis(lambda: set(self.w.dann_wahl.werte()) == {"Mikrofon", "Desktop-Ton"}, 3000))

    def test_zeitplan_ohne_tippen(self):
        t = self.E.texte
        klick(self.f.knopf_wenn_dann)
        klick(self.w.reiter_zeitplan)
        self.assertEqual(self.w.naechster.text(), t.zeitplan_kein_termin)
        self.assertFalse(self.w.termin_eintragen.isEnabled())
        klick(self.w.tag_knoepfe[4])  # Freitag
        klick(self.w.zeit_knoepfe[60])  # 20:00
        klick(self.w.zeit_knoepfe[-15])  # 19:45
        self.assertEqual(self.w.zeit_anzeige.text(), "19:45")
        klick(self.w.termin_eintragen)
        self.assertEqual(self.a.zeitplan, [Termin(4, 19, 45)])
        self.assertEqual(self.w.naechster.text(), t.zeitplan_naechster.format(tag="Fr", zeit="19:45"))
        self.assertEqual(self.f.naechster_stream.text(), t.zeitplan_naechster.format(tag="Fr", zeit="19:45"))
        self.assertFalse(self.w.termin_eintragen.isEnabled())  # gibt es schon
        from openregie.oberflaeche.bausteine import gesperrt_text
        self.assertEqual(gesperrt_text(self.w.termin_eintragen), t.gesperrt_termin_da)
        klick(self.w.termin_zeilen[0][1])
        self.assertEqual(self.a.zeitplan, [])
        self.assertEqual(self.f.naechster_stream.text(), "")
        self.assertFalse(self.a.laeuft)  # Zeitplan allein startet keine Automatik

    def test_geschlossen_belastet_nichts(self):
        klick(self.f.knopf_wenn_dann)
        klick(self.w.schliessen)
        self.assertFalse(self.w.isVisible())
        self.assertEqual([t for t in self.w.findChildren(QTimer) if t.isActive()], [])
        self.a.regel_speichern(Regel("stream_endet", "shot_live", dann_wert="Pause", aktiv=False))
        warte(300)
        self.assertFalse(self.a.laeuft)
        self.assertEqual([t for t in self.a.findChildren(QTimer) if t.isActive()], [])
        # Zu: das Fenster baut sich bei Änderungen nicht einmal neu auf
        self.assertEqual(len(self.w._zeilen), 0)

    def test_knoepfe_gross(self):
        klick(self.f.knopf_wenn_dann)
        self.a.regel_speichern(Regel("stream_startet", "shot_live", dann_wert="Pause"))
        from PySide6.QtWidgets import QPushButton
        for seite in (self.w.reiter_regeln, self.w.reiter_zeitplan):
            klick(seite)
            warte(50)
            for k in self.w.findChildren(QPushButton):
                if k.isVisible():
                    self.assertGreaterEqual(k.height(), self.E.groessen.knopf_hoehe, k.text())
        self.assertGreaterEqual(self.f.knopf_wenn_dann.height(), self.E.groessen.knopf_hoehe)


if __name__ == "__main__":
    unittest.main()
