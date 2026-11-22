"""Build 1.2, Teil A: Shots und Quellen (Motor-Schicht und Fenster), mit nachgeahmtem OBS."""

import re
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication

from openregie import einstellungen
from openregie.obs import vorlagen
from openregie.obs.quellen import ObsQuellen
from openregie.obs.verbindung import ObsVerbindung

from .falsches_obs import FalschesObs
from .hilfen import app, groesste_pause_ms, obs_einstellungen, warte, warte_bis, zugang


def schnelle_einstellungen():
    E = einstellungen.lade()
    E._werte["quellen"] = dict(E.quellen.als_dict(), vorschau_sekunden=0.2)
    return E


class MotorGrundlage(unittest.TestCase):
    def setUp(self):
        app()
        self.E = schnelle_einstellungen()
        self.obs = FalschesObs(passwort="geheim")
        self.obs.quelle_anlegen("Szene 1", "Bildschirmaufnahme", "pipewire-screen-capture-source")
        self.obs.quelle_anlegen("Szene 1", "Uno: Countdown", "browser_source",
                                {"url": "https://app.singular.live/output/abc/Output"})
        oe, _ = obs_einstellungen(szenensammlung="")
        self.v = ObsVerbindung(oe, self.E.texte, zugang_finden=zugang(self.obs.port), obs_laeuft=lambda: True)
        self.q = ObsQuellen(self.v, self.E.texte, self.E.quellen, uno_namen=lambda: {"Uno: Countdown"})
        self.v.starten()
        self.assertTrue(warte_bis(lambda: self.v.verbunden, 3000))
        self.assertTrue(warte_bis(lambda: self.v.szene, 3000))

    def tearDown(self):
        self.v.beenden()
        self.obs.beenden()
        warte(20)

    def anfragen(self, typ=None):
        return [a for a, _ in self.obs.anfragen if typ is None or a == typ]

    def lesen(self):
        self.q.beobachten(self)
        self.assertTrue(warte_bis(lambda: self.q.gelesen and not self.q._liest, 3000))

    def ausfuehren(self, aufruf, *args, **kw):
        ergebnis = []
        aufruf(*args, lambda ok, text: ergebnis.append((ok, text)), **kw)
        self.assertTrue(warte_bis(lambda: ergebnis, 5000))
        warte_bis(lambda: not self.q._liest and not self.q._sammeln.isActive(), 2000)
        return ergebnis[0]


class ShotMotorTest(MotorGrundlage):
    def test_ohne_zuschauer_keine_anfragen(self):
        """Schaut niemand hin, fragt ObsQuellen OBS nichts – auch nicht nach Änderungen in OBS."""
        vorher = len(self.obs.anfragen)
        self.obs.szene_anlegen("Neu")
        self.obs.quelle_anlegen("Pause", "Bild", "image_source")
        warte(600)
        neu = [a for a, _ in self.obs.anfragen[vorher:]]
        self.assertNotIn("GetSceneList", neu)
        self.assertNotIn("GetSceneItemList", neu)
        self.assertEqual(self.q.lesungen, 0)

    def test_liest_shots_in_obs_reihenfolge(self):
        self.lesen()
        self.assertEqual([s.name for s in self.q.shots], ["Pause", "Szene 1"])  # oben in OBS = zuerst
        szene = self.q.shot("Szene 1")
        self.assertEqual([q.name for q in szene.quellen], ["Uno: Countdown", "Bildschirmaufnahme"])
        self.assertEqual([q.name for q in szene.eigene_quellen()], ["Bildschirmaufnahme"])  # ohne Uno

    def test_liest_nach_ereignis_nur_solange_beobachtet(self):
        self.lesen()
        n = self.q.lesungen
        self.obs.szene_anlegen("Neu")
        self.assertTrue(warte_bis(lambda: self.q.shot("Neu") is not None, 3000))
        self.assertEqual(self.q.lesungen, n + 1)
        self.q.loslassen(self)
        self.obs.szene_anlegen("Noch eine")
        warte(600)
        self.assertEqual(self.q.lesungen, n + 1)
        self.q.beobachten(self)  # beim nächsten Hinschauen einmal nachholen
        self.assertTrue(warte_bis(lambda: self.q.shot("Noch eine") is not None, 3000))

    def test_live_schalten(self):
        self.lesen()
        ok, _ = self.ausfuehren(self.q.live_schalten, "Pause")
        self.assertTrue(ok)
        self.assertEqual(self.obs.szene, "Pause")
        self.assertTrue(warte_bis(lambda: self.q.live == "Pause", 2000))

    def test_umbenennen(self):
        self.lesen()
        ok, neu = self.ausfuehren(self.q.shot_umbenennen, "Pause", "  Gleich geht's los  ")
        self.assertTrue(ok)
        self.assertEqual(neu, "Gleich geht's los")
        self.assertIn("Gleich geht's los", self.obs.szenen)
        self.assertTrue(warte_bis(lambda: self.q.shot("Gleich geht's los") is not None, 2000))
        ok, neu = self.ausfuehren(self.q.quelle_umbenennen, "Bildschirmaufnahme", "Mein Bildschirm")
        self.assertTrue(ok)
        self.assertIn("Mein Bildschirm", self.obs.quellen)
        self.assertEqual(self.obs.reihenfolge("Szene 1")[0], "Mein Bildschirm")

    def test_umbenennen_falsch(self):
        self.lesen()
        t = self.E.texte
        self.assertEqual(self.ausfuehren(self.q.shot_umbenennen, "Pause", "   "), (False, t.meldung_name_leer))
        self.assertEqual(self.ausfuehren(self.q.shot_umbenennen, "Pause", "Szene 1"), (False, t.meldung_name_vergeben))
        self.assertEqual(self.ausfuehren(self.q.quelle_umbenennen, "Bildschirmaufnahme", "Pause"),
                         (False, t.meldung_name_vergeben))
        self.assertNotIn("SetSceneName", self.anfragen())
        # gleicher Name: nichts zu tun, aber kein Fehler
        self.assertEqual(self.ausfuehren(self.q.shot_umbenennen, "Pause", "Pause"), (True, "Pause"))

    def test_reactions_mit_layout(self):
        self.lesen()
        ok, name = self.ausfuehren(self.q.shot_anlegen, "reactions", "kamera_rechts_unten")
        self.assertTrue(ok, name)
        self.assertEqual(name, "Reactions")
        self.assertEqual(self.obs.reihenfolge("Reactions"), ["Reactions-Video", "Kamerabild"])  # Kamera oben
        # OBS 33 unter Wayland hat keine eigene Fensteraufnahme → Bildschirmaufnahme (dort ist Fenster wählbar)
        self.assertEqual(self.obs.quellen["Reactions-Video"]["kind"], "pipewire-screen-capture-source")
        self.assertEqual(self.obs.quellen["Kamerabild"]["kind"], "v4l2_input")
        self.assertEqual(self.obs.quellen["Kamerabild"]["settings"]["device_id"], "/dev/video0")  # nicht die IR-Kamera
        ids = {n: k for k, n, _ in self.obs.szenen["Reactions"]}
        video, kamera = self.obs.transform[ids["Reactions-Video"]], self.obs.transform[ids["Kamerabild"]]
        # Bildfläche des falschen OBS: 1280 × 720. Video füllt alles, Kamera klein rechts unten
        self.assertEqual((video["positionX"], video["positionY"], video["boundsWidth"], video["boundsHeight"]),
                         (0, 0, 1280, 720))
        self.assertAlmostEqual(kamera["boundsWidth"], 1280 * 0.28, delta=1)
        self.assertGreater(kamera["positionX"], 1280 / 2)
        self.assertGreater(kamera["positionY"], 720 / 2)
        self.assertLessEqual(kamera["positionX"] + kamera["boundsWidth"], 1280)
        self.assertLessEqual(kamera["positionY"] + kamera["boundsHeight"], 720)
        self.assertEqual(kamera["boundsType"], "OBS_BOUNDS_SCALE_INNER")

    def test_kamera_nur_ein_geraet(self):
        self.obs.geraete = [{"itemName": "Webcam", "itemValue": "/dev/video5", "itemEnabled": True}]
        self.lesen()
        self.ausfuehren(self.q.shot_anlegen, "kamera", "voll")
        self.assertEqual(self.obs.quellen["Kamerabild"]["settings"]["device_id"], "/dev/video5")

    def test_jeder_zweck_und_jedes_layout(self):
        self.lesen()
        for zweck, z in vorlagen.ZWECKE.items():
            for layout in z.layouts:
                ok, name = self.ausfuehren(self.q.shot_anlegen, zweck, layout, datei="/tmp/bild.png")
                self.assertTrue(ok, (zweck, layout, name))
                self.assertIn(name, self.obs.szenen)
                quellen = self.obs.reihenfolge(name)
                mit_kamera = z.mit_kamera and vorlagen.KAMERA in vorlagen.layout_rollen(layout)
                self.assertEqual(len(quellen), 2 if mit_kamera else 1, (zweck, layout, quellen))
        # Nur EINE Kamera-Quelle für alle Shots (eine Kamera lässt sich nur einmal öffnen)
        self.assertEqual([n for n, q in self.obs.quellen.items() if q["kind"] == "v4l2_input"], ["Kamerabild"])
        self.assertEqual(self.obs.quellen["Bilddatei"]["settings"]["file"], "/tmp/bild.png")

    def test_art_fehlt_nichts_bleibt_uebrig(self):
        self.obs.arten = ["browser_source", "image_source", "v4l2_input"]  # keine Bildschirmaufnahme
        self.lesen()
        szenen, quellen = set(self.obs.szenen), set(self.obs.quellen)
        ok, text = self.ausfuehren(self.q.shot_anlegen, "spiel", "kamera_rechts_unten")
        self.assertFalse(ok)
        self.assertEqual(text, self.E.texte.meldung_art_fehlt.format(art="Spiel"))
        self.assertEqual((set(self.obs.szenen), set(self.obs.quellen)), (szenen, quellen))

    def test_schiefgegangen_wird_aufgeraeumt(self):
        """OBS lehnt die Quelle ab → der halb angelegte Shot verschwindet wieder (kostet nichts)."""
        self.lesen()
        alt = self.obs._bearbeiten

        def ablehnen(typ, d):
            if typ == "CreateInput":
                return (False, 500, "Kaputt", None)
            return alt(typ, d)
        self.obs._bearbeiten = ablehnen
        szenen = set(self.obs.szenen)
        ok, _ = self.ausfuehren(self.q.shot_anlegen, "reactions", "kamera_rechts_unten")
        self.assertFalse(ok)
        self.assertEqual(set(self.obs.szenen), szenen)

    def test_loeschen_gibt_frei(self):
        self.lesen()
        self.ausfuehren(self.q.shot_anlegen, "reactions", "kamera_rechts_unten")
        self.ausfuehren(self.q.shot_anlegen, "kamera", "voll")
        self.assertTrue(warte_bis(lambda: self.q.shot("Kamera") is not None, 2000))
        ok, _ = self.ausfuehren(self.q.shot_loeschen, "Reactions")
        self.assertTrue(ok)
        self.assertNotIn("Reactions", self.obs.szenen)
        self.assertNotIn("Reactions-Video", self.obs.quellen)  # in keinem Shot mehr → ganz weg
        self.assertIn("Kamerabild", self.obs.quellen)  # noch im Shot „Kamera“ → bleibt
        self.assertIn("Uno: Countdown", self.obs.quellen)
        ok, _ = self.ausfuehren(self.q.shot_loeschen, "Kamera")
        self.assertNotIn("Kamerabild", self.obs.quellen)  # jetzt ist die Kamera frei

    def test_letzter_shot_bleibt(self):
        del self.obs.szenen["Pause"]
        self.lesen()
        self.assertEqual(self.ausfuehren(self.q.shot_loeschen, "Szene 1"), (False, self.E.texte.meldung_letzter_shot))
        self.assertIn("Szene 1", self.obs.szenen)

    def test_quelle_entfernen_und_hinzufuegen(self):
        self.lesen()
        ok, _ = self.ausfuehren(self.q.quelle_hinzufuegen, "Pause", "bild", datei="/tmp/pause.png")
        self.assertTrue(ok)
        self.assertEqual(self.obs.reihenfolge("Pause"), ["Bilddatei"])
        ok, _ = self.ausfuehren(self.q.quelle_hinzufuegen, "Pause", "kamera")
        self.assertEqual(self.obs.reihenfolge("Pause"), ["Bilddatei", "Kamerabild"])
        ok, _ = self.ausfuehren(self.q.quelle_hinzufuegen, "Pause", "bildschirm")
        self.assertTrue(self.obs.reihenfolge("Pause")[0].startswith("Bildschirmaufnahme"))  # großes Bild nach unten
        ok, _ = self.ausfuehren(self.q.quelle_entfernen, "Pause", "Bilddatei")
        self.assertTrue(ok)
        self.assertNotIn("Bilddatei", self.obs.quellen)
        # in zwei Shots: aus einem entfernen lässt die Quelle für den anderen da
        self.ausfuehren(self.q.quelle_hinzufuegen, "Szene 1", "kamera")
        self.ausfuehren(self.q.quelle_entfernen, "Pause", "Kamerabild")
        self.assertIn("Kamerabild", self.obs.quellen)
        self.assertIn("Kamerabild", self.obs.reihenfolge("Szene 1"))

    def test_ohne_verbindung_verstaendliche_meldung(self):
        self.lesen()
        self.v.beenden()
        self.assertEqual(self.ausfuehren(self.q.shot_anlegen, "kamera", "voll"),
                         (False, self.E.texte.meldung_nicht_verbunden))
        self.assertEqual(self.q.shots, [])


class VersionsnummerTest(MotorGrundlage):
    """Gefunden mit echtem OBS 33: Anlegen geht nur mit Versionsnummer (color_source_v3)."""

    def test_typ_mit_versionsnummer(self):
        vorlagen.QUELLENARTEN["testfarbe"] = vorlagen.QuellenArt("testfarbe", ("color_source",), "")
        try:
            self.lesen()
            self.E._werte["texte"]["quelle_name_testfarbe"] = "Farbe"
            ok, text = self.ausfuehren(self.q.quelle_hinzufuegen, "Pause", "testfarbe")
            self.assertTrue(ok, text)
            self.assertEqual(self.obs.quellen["Farbe"]["kind"], "color_source_v3")
        finally:
            del vorlagen.QUELLENARTEN["testfarbe"]

    def test_auswahl(self):
        art = vorlagen.QuellenArt("x", ("gibtsnicht", "color_source", "image_source"), "")
        self.assertEqual(vorlagen.obs_art_waehlen(art, ["image_source", "color_source_v3"]), "color_source_v3")
        self.assertEqual(vorlagen.obs_art_waehlen(art, ["color_source_vx"]), None)
        self.assertEqual(vorlagen.obs_art_waehlen(vorlagen.QUELLENARTEN["fenster"],
                                                  ["pipewire-screen-capture-source"]), "pipewire-screen-capture-source")


class StandbilderTest(MotorGrundlage):
    def breite_anfragen(self):
        return [d for a, d in self.obs.anfragen if a == "GetSourceScreenshot"
                and d.get("imageWidth") == int(self.E.quellen.vorschau_breite)]

    def test_ohne_namen_kein_takt_keine_anfrage(self):
        s = self.q.standbilder()
        warte(500)
        self.assertFalse(s.laeuft)
        self.assertEqual(self.breite_anfragen(), [])

    def test_holt_bilder_und_hoert_auf(self):
        s = self.q.standbilder()
        bilder = []
        s.neues_bild.connect(lambda n, b: bilder.append(n))
        s.beobachten(["Szene 1", "Pause"])
        self.assertTrue(warte_bis(lambda: {"Szene 1", "Pause"} <= set(bilder), 2000))
        self.assertTrue(warte_bis(lambda: len(bilder) >= 6, 3000))  # erneuert sich
        s.anhalten()
        self.assertFalse(s.laeuft)
        warte(100)
        n = len(self.breite_anfragen())
        warte(800)
        self.assertEqual(len(self.breite_anfragen()), n)

    def test_immer_nur_eine_anfrage_unterwegs(self):
        s = self.q.standbilder()
        self.obs.antworte = False
        s.beobachten(["Szene 1", "Pause", "Bildschirmaufnahme"])
        warte(700)
        self.assertEqual(len(self.breite_anfragen()), 1)
        s.anhalten()


# ---------------------------------------------------------------------------
#  Im Fenster
# ---------------------------------------------------------------------------
from .test_fenster import Grundlage, klick  # noqa: E402


class ShotFensterTest(Grundlage):
    mit_uno = False

    def setUp(self):
        import tests.test_fenster as tf
        alt = tf.internet_einstellungen

        def mit_schnellen_bildern(netz):
            E = alt(netz)
            E._werte["quellen"] = dict(E.quellen.als_dict(), vorschau_sekunden=0.2)
            return E
        tf.internet_einstellungen = mit_schnellen_bildern
        try:
            super().setUp()
        finally:
            tf.internet_einstellungen = alt
        self.obs.quelle_anlegen("Szene 1", "Bildschirmaufnahme", "pipewire-screen-capture-source")
        self.m.starten()  # OBS „läuft schon“ → nur verbinden
        self.assertTrue(warte_bis(lambda: self.v.verbunden, 3000))
        self.f.resize(1903, 971)  # Kevins Bildschirm
        self.l = self.f.shot_leiste
        self.assertTrue(warte_bis(lambda: set(self.l.kacheln) == {"Szene 1", "Pause"}, 3000))

    def bild_anfragen(self):
        return sum(1 for a, d in self.obs.anfragen if a == "GetSourceScreenshot"
                   and d.get("imageWidth") == int(self.E.quellen.vorschau_breite))

    def test_kacheln_mit_bild_und_live(self):
        self.assertTrue(warte_bis(lambda: all(k.bild is not None for k in self.l.kacheln.values()), 3000))
        self.assertTrue(self.l.kacheln["Szene 1"].live)
        self.assertFalse(self.l.kacheln["Pause"].live)
        self.assertTrue(self.l.plus.isVisible())
        for k in [*self.l.kacheln.values(), self.l.plus]:
            self.assertGreaterEqual(k.height(), 100)
            self.assertGreaterEqual(k.width(), 120)

    def test_ein_klick_schaltet_live(self):
        klick(self.l.kacheln["Pause"])
        self.assertTrue(warte_bis(lambda: self.obs.szene == "Pause", 3000))
        self.assertTrue(warte_bis(lambda: self.l.kacheln["Pause"].live, 2000))
        self.assertFalse(self.l.kacheln["Szene 1"].live)
        self.assertIs(self.f.bedienfelder.currentWidget(), self.f.uno_einrichtung)  # rechts bleibt, was war

    def test_zugeklappt_keine_bilder(self):
        self.assertTrue(warte_bis(lambda: self.bild_anfragen() >= 2, 3000))
        klick(self.l.knopf_auf_zu)
        self.assertFalse(self.l.koerper.isVisible())
        self.assertFalse(self.l.standbilder.laeuft)
        self.assertFalse(self.f.quellen.wird_beobachtet)
        warte(100)
        n = self.bild_anfragen()
        lesungen = self.f.quellen.lesungen
        self.obs.szene_anlegen("Neu")  # Änderung in OBS: wird jetzt NICHT gelesen
        warte(1000)
        self.assertEqual(self.bild_anfragen(), n)
        self.assertEqual(self.f.quellen.lesungen, lesungen)
        klick(self.l.knopf_auf_zu)
        self.assertTrue(warte_bis(lambda: "Neu" in self.l.kacheln, 3000))
        self.assertTrue(warte_bis(lambda: self.bild_anfragen() > n, 3000))

    def test_minimiert_keine_bilder(self):
        self.f.showMinimized()
        warte(200)
        self.f.shot_leiste.aktiv_pruefen()  # (offscreen schickt das Ereignis nicht immer)
        self.assertFalse(self.l.standbilder.laeuft)
        n = self.bild_anfragen()
        warte(800)
        self.assertEqual(self.bild_anfragen(), n)
        self.f.showNormal()
        warte(200)
        self.f.shot_leiste.aktiv_pruefen()
        self.assertTrue(self.l.standbilder.laeuft)

    def test_bearbeiten_umbenennen_loeschen(self):
        t = self.E.texte
        klick(self.l.knopf_bearbeiten)
        klick(self.l.kacheln["Pause"])
        b = self.f.shot_bedienfeld
        self.assertIs(self.f.bedienfelder.currentWidget(), b)
        self.assertEqual(self.obs.szene, "Szene 1")  # nicht live geschaltet
        self.assertEqual(b.name.text(), "Pause")
        klick(b.knopf_umbenennen)
        self.assertTrue(b.eingabe.isVisible())
        b.eingabe.feld.setText("Gleich live")
        klick(b.eingabe.ok)
        self.assertTrue(warte_bis(lambda: "Gleich live" in self.obs.szenen, 3000))
        self.assertTrue(warte_bis(lambda: "Gleich live" in self.l.kacheln, 3000))
        self.assertEqual(b.name.text(), "Gleich live")
        self.assertEqual(b.meldung.text(), t.meldung_umbenannt.format(name="Gleich live"))
        klick(b.knopf_loeschen)
        self.assertEqual(b.knopf_loeschen.text(), t.knopf_wirklich_loeschen)
        self.assertIn("Gleich live", self.obs.szenen)
        klick(b.knopf_loeschen)
        self.assertTrue(warte_bis(lambda: "Gleich live" not in self.obs.szenen, 3000))
        self.assertTrue(warte_bis(lambda: "Gleich live" not in self.l.kacheln, 3000))
        self.assertFalse(self.l.bearbeiten)
        self.assertIs(self.f.bedienfelder.currentWidget(), self.f.uno_einrichtung)

    def test_live_shot_nicht_loeschbar_und_sagt_warum(self):
        klick(self.l.knopf_bearbeiten)
        klick(self.l.kacheln["Szene 1"])
        b = self.f.shot_bedienfeld
        self.assertFalse(b.knopf_loeschen.isEnabled())
        from openregie.oberflaeche.bausteine import gesperrt_text
        self.assertEqual(gesperrt_text(b.knopf_loeschen), self.E.texte.gesperrt_shot_live)
        self.assertFalse(b.knopf_quelle_entfernen.isEnabled())
        self.assertEqual(gesperrt_text(b.knopf_quelle_entfernen), self.E.texte.gesperrt_keine_quelle)

    def test_quellen_als_kacheln_umbenennen_entfernen(self):
        klick(self.l.knopf_bearbeiten)
        klick(self.l.kacheln["Szene 1"])
        b = self.f.shot_bedienfeld
        self.assertTrue(warte_bis(lambda: "Bildschirmaufnahme" in b.kacheln, 3000))
        self.assertTrue(warte_bis(lambda: b.kacheln["Bildschirmaufnahme"].bild is not None, 3000))
        klick(b.kacheln["Bildschirmaufnahme"])
        self.assertTrue(b.knopf_quelle_umbenennen.isEnabled())
        klick(b.knopf_quelle_umbenennen)
        b.eingabe.feld.setText("Desktop")
        b.eingabe.feld.returnPressed.emit()
        self.assertTrue(warte_bis(lambda: "Desktop" in self.obs.quellen, 3000))
        self.assertTrue(warte_bis(lambda: "Desktop" in b.kacheln, 3000))
        self.assertEqual(b.quelle_name, "Desktop")
        klick(b.knopf_quelle_entfernen)
        self.assertTrue(warte_bis(lambda: "Desktop" not in self.obs.quellen, 3000))
        self.assertTrue(warte_bis(lambda: not b.kacheln, 3000))

    def test_bedienfeld_zu_keine_bilder(self):
        klick(self.l.knopf_bearbeiten)
        klick(self.l.kacheln["Szene 1"])
        b = self.f.shot_bedienfeld
        self.assertTrue(warte_bis(lambda: b.standbilder.laeuft, 2000))
        klick(b.knopf_fertig)
        self.assertFalse(b.standbilder.laeuft)
        self.assertFalse(b.isVisible())

    def test_shot_hinzufuegen(self):
        t = self.E.texte
        klick(self.l.plus)
        n = self.f.shot_neu
        self.assertIs(self.f.bedienfelder.currentWidget(), n)
        self.assertFalse(n.anlegen.isEnabled())  # Zweck ist Pflicht
        from openregie.oberflaeche.bausteine import gesperrt_text
        self.assertEqual(gesperrt_text(n.anlegen), t.gesperrt_zweck_fehlt)
        klick(n.zweck_knoepfe["reactions"])
        self.assertTrue(n.hinweis.isVisible())  # „Gleich fragt das System …“
        self.assertEqual(n.layout_wahl, "kamera_rechts_unten")  # Layout gleich vorgeschlagen
        self.assertTrue(n.layout_knoepfe["kamera_rechts_unten"].isChecked())
        klick(n.layout_knoepfe["kamera_links_unten"])
        klick(n.anlegen)
        self.assertTrue(warte_bis(lambda: "Reactions" in self.obs.szenen, 3000))
        self.assertTrue(warte_bis(lambda: self.f.bedienfelder.currentWidget() is self.f.shot_bedienfeld, 3000))
        self.assertEqual(self.f.shot_bedienfeld.shot_name, "Reactions")
        self.assertTrue(warte_bis(lambda: "Reactions" in self.l.kacheln, 3000))
        self.assertEqual(self.obs.szene, "Szene 1")  # nicht einfach live geschaltet
        ids = {n_: k for k, n_, _ in self.obs.szenen["Reactions"]}
        self.assertLess(self.obs.transform[ids["Kamerabild"]]["positionX"], 1280 / 2)  # links unten

    def test_bild_ohne_datei(self):
        klick(self.l.plus)
        n = self.f.shot_neu
        n._datei_waehlen = lambda: ""
        klick(n.zweck_knoepfe["bild"])
        klick(n.anlegen)
        self.assertEqual(n.meldung.text(), self.E.texte.meldung_kein_bild)
        n._datei_waehlen = lambda: "/tmp/pause.png"
        klick(n.anlegen)
        self.assertTrue(warte_bis(lambda: "Bilddatei" in self.obs.quellen, 3000))
        self.assertIn("Bild", self.obs.szenen)
        self.assertEqual(self.obs.quellen["Bilddatei"]["settings"]["file"], "/tmp/pause.png")

    def test_quelle_in_shot_hinzufuegen(self):
        klick(self.l.knopf_bearbeiten)
        klick(self.l.kacheln["Pause"])
        klick(self.f.shot_bedienfeld.knopf_quelle_neu)
        n = self.f.shot_neu
        self.assertEqual(n.modus, "quelle")
        klick(n.art_knoepfe["kamera"])
        klick(n.anlegen)
        self.assertTrue(warte_bis(lambda: self.obs.reihenfolge("Pause") == ["Kamerabild"], 3000))
        self.assertTrue(warte_bis(lambda: self.f.bedienfelder.currentWidget() is self.f.shot_bedienfeld, 3000))
        self.assertTrue(warte_bis(lambda: "Kamerabild" in self.f.shot_bedienfeld.kacheln, 3000))

    def test_overlay_klick_beendet_bearbeiten(self):
        klick(self.l.knopf_bearbeiten)
        klick(self.l.kacheln["Pause"])
        self.f.shot_leiste.bearbeiten_setzen(False)
        self.assertIsNot(self.f.bedienfelder.currentWidget(), self.f.shot_bedienfeld)

    def test_bleibt_fluessig_beim_anlegen(self):
        klick(self.l.plus)
        klick(self.f.shot_neu.zweck_knoepfe["spiel"])
        klick(self.f.shot_neu.anlegen)
        pause = groesste_pause_ms(1500, lambda: "Spiel" in self.l.kacheln)
        self.assertIn("Spiel", self.l.kacheln)
        self.assertLess(pause, 150)

    def test_knoepfe_gross_genug(self):
        klick(self.l.knopf_bearbeiten)
        klick(self.l.kacheln["Szene 1"])
        from PySide6.QtWidgets import QPushButton
        for k in self.f.findChildren(QPushButton):
            if k.isVisible():
                self.assertGreaterEqual(k.height(), self.E.groessen.knopf_hoehe, k.text())


class NurUeberDenMotorTest(unittest.TestCase):
    """Feste Regel: Die Oberfläche spricht nur über die Motor-Schicht mit OBS."""

    def test_keine_direkten_obs_aufrufe_in_der_oberflaeche(self):
        ordner = Path(__file__).resolve().parent.parent / "openregie" / "oberflaeche"
        verboten = re.compile(r"\.anfrage\(|jetzt_neu_verbinden\(|verbindung\.(starten|beenden)\(|QWebSocket")
        for datei in ordner.glob("*.py"):
            for nr, zeile in enumerate(datei.read_text().splitlines(), 1):
                self.assertIsNone(verboten.search(zeile), f"{datei.name}:{nr}: {zeile.strip()}")


if __name__ == "__main__":
    unittest.main()
