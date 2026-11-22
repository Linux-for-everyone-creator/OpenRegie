"""Build 1.2.1: Jede Kachel gehört fest zu IHRER Szene – über die feste OBS-Kennung, nie über die Position.

Fehlerbericht: Zwei Szenen „Countdown“ und „Bildschirmaufnahme“. Klick auf die Bildschirmaufnahme →
im großen Bild war nur der Countdown zu sehen. Ursache: Die Bildschirmaufnahme lieferte kein Bild
(Bildschirm im System-Fenster nicht freigegeben) und das Uno-Overlay „Countdown“ liegt in JEDER Szene
ganz oben. Hier wird geprüft: Kachel → richtige Szene (auch nach Umbenennen, Neuanlegen, Umsortieren,
Namen tauschen, mit 5 Szenen), Vorschaubild → richtige Szene, und „⚠ Kein Bild“ wird angezeigt.
"""

import random

from PySide6.QtGui import QColor

from openregie.automatik.motor import Automatik, Regel

from .falsches_obs import testbild_daten
from .hilfen import warte, warte_bis
from .test_fenster import Grundlage, klick

RUNDEN = 12  # jede Prüfung 12-mal (Auftrag: 10- bis 16-mal)
FARBEN = {"Countdown": "#E5484D", "Bildschirmaufnahme": "#2D6CDF", "Pause": "#3FB950", "Kamera": "#F2B035",
          "Spiel": "#9B59B6"}


class ZuordnungGrundlage(Grundlage):
    mit_uno = False
    szenen = ["Countdown", "Bildschirmaufnahme"]  # oben zuerst, wie in der OBS-Liste

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
        o = self.obs
        # Kevins Aufbau: jede Szene hat ihren Inhalt, das Uno-Countdown-Overlay liegt in JEDER Szene oben
        o.szenen = {}
        for name in reversed(self.szenen):  # OBS zählt von unten
            o.szenen[name] = []
        o.szene = self.szenen[0]
        for name in self.szenen:
            o.bilder[name] = testbild_daten(farbe=FARBEN[name])
            if name == "Bildschirmaufnahme":
                o.quelle_anlegen(name, "Bildschirmaufnahme", "pipewire-screen-capture-source")
            else:
                o.quelle_anlegen(name, f"{name}-Bild", "image_source")
            o.quelle_anlegen(name, "Uno: Countdown | Circles", "browser_source")
        self.m.starten()
        self.assertTrue(warte_bis(lambda: self.v.verbunden and self.v.szene, 3000))
        self.f.resize(1903, 971)
        self.l = self.f.shot_leiste
        self.assertTrue(warte_bis(lambda: self.namen() == self.szenen, 3000), self.namen())

    def sichtbar(self):
        return [k.name for k in sorted((k for k in self.l.kacheln.values() if k.isVisible()), key=lambda k: k.x())]

    def namen(self):
        """Namen aller Kacheln in der Reihenfolge, wie Kevin sie sieht (Seite für Seite mit ▶ geblättert)."""
        alle = []
        for _ in range(self.l._seiten()):  # erst zur ersten Seite
            if self.l.seite == 0:
                break
            klick(self.l.vor)
        for _ in range(self.l._seiten()):
            alle += self.sichtbar()
            if self.l.vor.isVisible():
                klick(self.l.vor)
        return alle

    def hinblaettern(self, name):
        for _ in range(self.l._seiten() + 1):
            if name in self.sichtbar():
                return self.l.kachel(name)
            klick(self.l.vor)
        self.fail(f"Kachel {name} nicht zu finden: {self.namen()}")

    def live_kacheln(self):
        return [k.name for k in self.l.kacheln.values() if k.live]

    def geschickt(self):
        return [d for a, d in self.obs.anfragen if a == "SetCurrentProgramScene"]

    def klick_und_pruefen(self, name):
        vorher = len(self.geschickt())
        klick(self.hinblaettern(name))
        self.assertTrue(warte_bis(lambda: len(self.geschickt()) > vorher, 2000))  # erst die Anfrage abwarten
        self.assertTrue(warte_bis(lambda: self.obs.szene == name, 2000), f"{name} → OBS zeigt {self.obs.szene}")
        neu = self.geschickt()[vorher:]
        self.assertEqual(neu, [{"sceneUuid": self.obs.kennungen[name]}])  # die feste Kennung, nicht Name/Nummer
        self.assertTrue(warte_bis(lambda: self.l.kachel(name).live, 2000))
        self.assertEqual([n for n in self.live_kacheln()], [name])
        self.assertEqual(self.v.szene, name)

    def farbe_der_kachel(self, name):
        k = self.l.kachel(name)
        if k is not None and not k.isVisible():
            k = self.hinblaettern(name)
        if k is None or k.bild is None:
            return None
        bild = k.bild.toImage()
        return bild.pixelColor(bild.width() // 2, bild.height() // 2)

    def bild_passt(self, name, szene_farbe):
        c = self.farbe_der_kachel(name)
        z = QColor(szene_farbe)
        return c is not None and all(abs(a - b) < 24 for a, b in
                                     ((c.red(), z.red()), (c.green(), z.green()), (c.blue(), z.blue())))


class KevinsFallTest(ZuordnungGrundlage):
    def test_bildschirmaufnahme_schaltet_bildschirmaufnahme(self):
        for _ in range(RUNDEN):
            self.klick_und_pruefen("Bildschirmaufnahme")
            self.klick_und_pruefen("Countdown")

    def test_vorschaubild_gehoert_zur_eigenen_szene(self):
        for name in self.szenen:
            self.assertTrue(warte_bis(lambda n=name: self.bild_passt(n, FARBEN[n]), 3000), name)

    def test_aufnahme_ohne_bild_zeigt_hinweis(self):
        t = self.E.texte
        self.obs.ohne_bild.add("Bildschirmaufnahme")
        self.obs.ereignis("SceneItemEnableStateChanged", {"sceneName": "Bildschirmaufnahme"})  # Liste neu lesen
        self.assertTrue(warte_bis(lambda: self.l.kachel("Bildschirmaufnahme").hinweis == t.shot_kein_bild, 3000))
        self.assertEqual(self.l.kachel("Countdown").hinweis, "")
        self.assertIn(t.shot_kein_bild, self.l.kachel("Bildschirmaufnahme").accessibleName())
        # Trotzdem: ein Klick schaltet die richtige Szene
        self.klick_und_pruefen("Bildschirmaufnahme")
        # Bearbeiten: Quelle wählen → Hinweis und Knopf „Bildschirm neu auswählen“
        klick(self.l.knopf_bearbeiten)
        klick(self.l.kachel("Bildschirmaufnahme"))
        b = self.f.shot_bedienfeld
        self.assertTrue(warte_bis(lambda: b.kachel("Bildschirmaufnahme") is not None, 2000))
        self.assertTrue(warte_bis(lambda: b.kachel("Bildschirmaufnahme").hinweis == t.shot_kein_bild, 3000))
        self.assertFalse(b.knopf_neu_auswaehlen.isVisible())  # erst, wenn die Quelle gewählt ist
        klick(b.kachel("Bildschirmaufnahme"))
        self.assertTrue(b.knopf_neu_auswaehlen.isVisible())
        self.assertIn(t.quelle_kein_bild, b.quelle_text.text())
        klick(b.knopf_neu_auswaehlen)
        self.assertTrue(warte_bis(lambda: self.obs.knopf_gedrueckt == [("Bildschirmaufnahme", "Reselect")], 2000))
        self.assertTrue(warte_bis(lambda: b.meldung.text() == t.meldung_neu_auswaehlen, 2000))
        # Bildschirm freigegeben → Hinweis verschwindet von selbst (ohne neues Ereignis von OBS)
        self.obs.ohne_bild.clear()
        self.assertTrue(warte_bis(lambda: b.kachel("Bildschirmaufnahme").hinweis == "", 3000))
        self.assertFalse(b.knopf_neu_auswaehlen.isVisible())
        klick(b.knopf_fertig)
        self.assertTrue(warte_bis(lambda: self.l.kachel("Bildschirmaufnahme").hinweis == "", 3000))

    def test_ohne_hinweis_keine_extra_abfragen(self):
        """Liefern alle Aufnahmen ein Bild, fragt die Leiste nur die Szenen ab – nichts zusätzlich."""
        warte(1500)
        ziele = {d.get("sourceUuid") or d.get("sourceName") for a, d in self.obs.anfragen
                 if a == "GetSourceScreenshot" and d.get("imageWidth") == int(self.E.quellen.vorschau_breite)}
        self.assertEqual(ziele, {self.obs.kennungen[n] for n in self.szenen})

    def test_neu_auswaehlen_gesperrt_hat_hinweis(self):
        b = self.f.shot_bedienfeld
        self.assertTrue(b._grund_neu_auswaehlen())  # nichts gewählt → es gibt einen Grund (Hinweis)


class FuenfSzenenTest(ZuordnungGrundlage):
    szenen = ["Countdown", "Bildschirmaufnahme", "Pause", "Kamera", "Spiel"]

    def test_jede_kachel_schaltet_ihre_szene(self):
        zufall = random.Random(12)
        for _ in range(RUNDEN):
            reihe = list(self.szenen)
            zufall.shuffle(reihe)
            for name in reihe:
                if self.obs.szene != name:
                    self.klick_und_pruefen(name)

    def test_umsortieren_in_obs(self):
        zufall = random.Random(7)
        for _ in range(RUNDEN):
            neu = list(self.szenen)
            zufall.shuffle(neu)
            self.obs.szenen_umsortieren(neu)
            self.assertTrue(warte_bis(lambda: self.namen() == neu, 3000), (self.namen(), neu))
            ziel = next(n for n in neu if n != self.obs.szene)
            self.klick_und_pruefen(ziel)
            for n in neu:  # auch die Vorschaubilder bleiben bei ihrer Szene
                self.assertTrue(warte_bis(lambda n=n: self.bild_passt(n, FARBEN[n]), 3000), n)

    def test_neu_angelegt_oben(self):
        for i in range(RUNDEN):
            name = f"Neu {i}"
            FARBEN[name] = "#%02X%02X%02X" % (40 + i * 15, 200 - i * 10, 90)
            self.obs.bilder[name] = testbild_daten(farbe=FARBEN[name])
            self.obs.szene_anlegen(name)
            self.obs.szenen_umsortieren([name] + [n for n in reversed(list(self.obs.szenen)) if n != name])
            self.assertTrue(warte_bis(lambda n=name: n in self.namen(), 3000))
            # die alten Kacheln schalten weiter ihre eigene Szene, die neue ihre
            self.klick_und_pruefen(name)
            self.klick_und_pruefen("Bildschirmaufnahme" if i % 2 else "Countdown")

    def test_umbenennen_in_obs_kachel_bleibt(self):
        for i in range(RUNDEN):
            alt = "Bildschirmaufnahme" if i == 0 else f"Bildschirm {i - 1}"
            neu = f"Bildschirm {i}"
            kachel = self.l.kachel(alt)
            self.obs.szene_umbenennen(alt, neu)
            FARBEN[neu] = FARBEN["Bildschirmaufnahme"]
            self.assertTrue(warte_bis(lambda n=neu: self.l.kachel(n) is kachel, 3000))  # dieselbe Kachel
            self.assertIsNone(self.l.kachel(alt))
            self.assertEqual(kachel.name, neu)
            self.klick_und_pruefen(neu)
            self.klick_und_pruefen("Countdown")
            self.assertTrue(warte_bis(lambda n=neu: self.bild_passt(n, FARBEN["Bildschirmaufnahme"]), 3000))

    def test_namen_tauschen(self):
        """Härtefall: zwei Szenen tauschen die Namen – jede Kachel folgt ihrer Szene, nicht dem Namen."""
        for _ in range(RUNDEN):
            a, b = "Countdown", "Pause"
            kachel_a, kachel_b = self.l.kachel(a), self.l.kachel(b)
            farbe_a, farbe_b = FARBEN[a], FARBEN[b]
            self.obs.szene_umbenennen(a, "Zwischen")
            self.obs.szene_umbenennen(b, a)
            self.obs.szene_umbenennen("Zwischen", b)
            FARBEN[a], FARBEN[b] = farbe_b, farbe_a
            self.assertTrue(warte_bis(lambda: kachel_a.name == b and kachel_b.name == a, 3000))
            self.assertIs(self.l.kachel(a), kachel_b)
            self.klick_und_pruefen(a)
            self.klick_und_pruefen(b)
            self.assertTrue(warte_bis(lambda: self.bild_passt(a, FARBEN[a]) and self.bild_passt(b, FARBEN[b]), 3000))

    def test_live_szene_umbenannt_sofort_richtig(self):
        for i in range(RUNDEN):
            alt = self.obs.szene
            neu = f"Live {i}"
            anfragen = len(self.obs.anfragen)
            self.obs.szene_umbenennen(alt, neu)
            # sofort (ohne Fehlversuche des großen Vorschaubilds) der neue Name
            self.assertTrue(warte_bis(lambda n=neu: self.v.szene == n, 500))
            self.assertTrue(warte_bis(lambda n=neu: self.live_kacheln() == [n], 2000))
            self.assertEqual(self.f.szenenname.text(), neu)
            fehler = [d for a, d in self.obs.anfragen[anfragen:] if a == "GetSourceScreenshot"
                      and "sourceName" in d]  # großes Bild und Kacheln fragen nur über die Kennung
            self.assertEqual(fehler, [])
            self.klick_und_pruefen(next(n for n in self.namen() if n != neu))
            self.klick_und_pruefen(neu)

    def test_geloeschte_szene_schaltet_nichts_falsches(self):
        kachel = self.hinblaettern("Spiel")
        del self.obs.szenen["Spiel"]
        # Klick, bevor OpenRegie die neue Liste hat → lieber Fehlermeldung als falsche Szene
        vorher = self.obs.szene
        klick(kachel)
        warte(300)
        self.assertEqual(self.obs.szene, vorher)
        self.obs.ereignis("SceneRemoved", {"sceneName": "Spiel"})
        self.assertTrue(warte_bis(lambda: self.l.kachel("Spiel") is None, 3000))


class OhneKennungTest(ZuordnungGrundlage):
    """Altes OBS ohne feste Kennungen: dann eben über den Namen (nie über die Nummer)."""

    def setUp(self):
        from .falsches_obs import FalschesObs
        alt = FalschesObs.__init__

        def ohne(self_, *a, **kw):
            alt(self_, *a, **kw)
            self_.mit_kennung = False
        FalschesObs.__init__ = ohne
        try:
            super().setUp()
        finally:
            FalschesObs.__init__ = alt

    def test_name_statt_kennung(self):
        for _ in range(RUNDEN):
            for name in ("Bildschirmaufnahme", "Countdown"):
                vorher = len(self.geschickt())
                klick(self.l.kachel(name))
                self.assertTrue(warte_bis(lambda n=name: self.obs.szene == n, 2000))
                self.assertEqual(self.geschickt()[vorher:], [{"sceneName": name}])
                self.assertTrue(warte_bis(lambda n=name: self.live_kacheln() == [n], 2000))


class RegelFolgtUmbenennenTest(ZuordnungGrundlage):
    def test_regel_zieht_neuen_namen_mit(self):
        import tempfile
        from pathlib import Path

        from tests.test_automatik import UnoAttrappe
        ordner = tempfile.mkdtemp()
        a = Automatik(self.E.texte, self.v, self.f.quellen, UnoAttrappe(), datei=Path(ordner) / "a.json")
        try:
            a.laden()
            self.assertTrue(warte_bis(lambda: a.geladen, 2000))
            a.regel_speichern(Regel("shot_live", "shot_live", "Bildschirmaufnahme", "Countdown"))
            for i in range(RUNDEN):
                alt_w, alt_d = a.regeln[0].wenn_wert, a.regeln[0].dann_wert
                self.obs.szene_umbenennen(alt_w, f"Bild {i}")
                self.obs.szene_umbenennen(alt_d, f"Zähler {i}")
                self.assertTrue(warte_bis(lambda i=i: (a.regeln[0].wenn_wert, a.regeln[0].dann_wert)
                                          == (f"Bild {i}", f"Zähler {i}"), 2000))
            # und sie wirkt mit den neuen Namen
            n = len(self.geschickt())
            self.f.quellen.live_schalten(f"Zähler {RUNDEN - 1}")
            self.assertTrue(warte_bis(lambda: len(self.geschickt()) > n, 2000))
            self.assertTrue(warte_bis(lambda: self.obs.szene == f"Zähler {RUNDEN - 1}", 2000))
            vorher = len(self.geschickt())
            self.f.quellen.live_schalten(f"Bild {RUNDEN - 1}")
            bild, zaehler = self.obs.kennungen[f"Bild {RUNDEN - 1}"], self.obs.kennungen[f"Zähler {RUNDEN - 1}"]
            # erst „Bild“ live (von Hand), dann schaltet die Regel auf „Zähler“
            self.assertTrue(warte_bis(lambda: self.geschickt()[vorher:] == [{"sceneUuid": bild}, {"sceneUuid": zaehler}],
                                      3000), self.geschickt()[vorher:])
            self.assertTrue(warte_bis(lambda: self.obs.szene == f"Zähler {RUNDEN - 1}", 3000))
            self.assertEqual(a.ausloesungen, 1)
        finally:
            a.beenden()
            import shutil
            shutil.rmtree(ordner, ignore_errors=True)
