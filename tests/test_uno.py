"""Prüft die Overlays.uno-Anbindung mit einem nachgeahmten Uno."""

import unittest

from openregie.geheimspeicher import Arbeitsspeicher
from openregie.uno.verwaltung import (UnoVerwaltung, felder_lesen, ist_textfeld, overlays_lesen,
                                      sichtbarkeit_lesen, token_aus_text)

from .falsches_internet import UNO_ADRESSE_TEXT, UNO_TOKEN, FalschesInternet
from .hilfen import app, internet_einstellungen, warte, warte_bis


class AdresseTest(unittest.TestCase):
    def test_adresse_erkennen(self):
        self.assertEqual(token_aus_text(UNO_ADRESSE_TEXT), UNO_TOKEN)
        self.assertEqual(token_aus_text(f"  {UNO_ADRESSE_TEXT}\n"), UNO_TOKEN)
        self.assertEqual(token_aus_text(f'"{UNO_ADRESSE_TEXT}"'), UNO_TOKEN)
        self.assertEqual(token_aus_text(UNO_ADRESSE_TEXT.removesuffix("/api")), UNO_TOKEN)
        self.assertEqual(token_aus_text(UNO_TOKEN), UNO_TOKEN)

    def test_unsinn_abweisen(self):
        for text in ("", "Hallo Welt", "https://overlays.uno", "abc", "x" * 500, None,
                     "https://app.overlays.uno/output/abc", "token mit leerzeichen"):
            self.assertIsNone(token_aus_text(text), text)


class AntwortenLesenTest(unittest.TestCase):
    def test_liste(self):
        self.assertEqual(overlays_lesen([{"id": "a", "name": "A", "visible": True}, {"id": "b", "title": "B"}]),
                         [("a", "A", True), ("b", "B", None)])

    def test_verschachtelt_und_als_woerterbuch(self):
        self.assertEqual(overlays_lesen({"overlays": [{"id": "a", "name": "A"}]}), [("a", "A", None)])
        self.assertEqual(overlays_lesen({"a": {"name": "A", "state": "In"}, "b": "B"}),
                         [("a", "A", True), ("b", "B", None)])

    def test_unsinn(self):
        for unsinn in (None, 5, "x", [None, 5, {"name": "ohne id"}]):
            self.assertEqual(overlays_lesen(unsinn), [] if unsinn != "x" else [])

    def test_ohne_name(self):
        self.assertEqual(overlays_lesen([{"id": "a"}]), [("a", "Overlay 1", None)])

    def test_sichtbarkeit(self):
        self.assertTrue(sichtbarkeit_lesen({"visible": True}))
        self.assertFalse(sichtbarkeit_lesen({"isVisible": "false"}))
        self.assertTrue(sichtbarkeit_lesen({"state": "In"}))
        self.assertFalse(sichtbarkeit_lesen({"state": "Out1"}))
        self.assertIsNone(sichtbarkeit_lesen({"state": "irgendwas"}))
        self.assertIsNone(sichtbarkeit_lesen({}))

    def test_felder(self):
        inhalt = {"Name": "Kevin", "Farbe": "#FF0000", "Logo": "https://x/y.png", "An": True, "Zahl": 5, "Leer": ""}
        self.assertEqual(felder_lesen(inhalt), [("Name", "Kevin"), ("Leer", "")])
        self.assertEqual(felder_lesen({"content": {"A": "b"}}), [("A", "b")])
        self.assertEqual(felder_lesen([{"fieldId": "A", "value": "b"}, {"id": "C", "value": 3}]), [("A", "b")])
        self.assertFalse(ist_textfeld("#abc"))
        self.assertTrue(ist_textfeld("#1 im Stream"))


class VerwaltungTest(unittest.TestCase):
    def setUp(self):
        app()
        self.netz = FalschesInternet()
        self.E = internet_einstellungen(self.netz)
        self.speicher = Arbeitsspeicher()
        self.uno = UnoVerwaltung(self.E.uno, self.E.texte, self.speicher)
        self.meldungen = []
        self.uno.meldung.connect(lambda t, f: self.meldungen.append((t, f)))

    def tearDown(self):
        self.uno.beenden()
        self.netz.beenden()
        warte(20)

    def hinzufuegen(self, text=UNO_ADRESSE_TEXT):
        ergebnis = []
        self.uno.projekt_hinzufuegen(text, lambda ok, m: ergebnis.append((ok, m)))
        self.assertTrue(warte_bis(lambda: ergebnis, 3000))
        return ergebnis[0]

    def test_projekt_hinzufuegen_und_speichern(self):
        self.uno.laden()
        ok, meldung = self.hinzufuegen()
        self.assertTrue(ok, meldung)
        self.assertIn("3", meldung)
        self.assertEqual([o.name for o in self.uno.overlays.values()], ["Bauchbinde", "News-Ticker", "Countdown"])
        # gespeichert ist es nur im (hier nachgeahmten) Passwortspeicher
        self.assertIn(UNO_TOKEN, self.speicher.daten["uno"])
        # nach Neustart wieder da
        uno2 = UnoVerwaltung(self.E.uno, self.E.texte, self.speicher)
        uno2.laden()
        self.assertTrue(warte_bis(lambda: len(uno2.overlays) == 3, 3000))
        uno2.beenden()

    def test_falsche_adresse(self):
        ok, meldung = self.hinzufuegen("Hallo")
        self.assertFalse(ok)
        self.assertEqual(meldung, self.E.texte.meldung_uno_adresse_falsch)
        ok, meldung = self.hinzufuegen("https://app.overlays.uno/apiv2/controlapps/GIBTSNICHT123/api")
        self.assertFalse(ok)
        self.assertEqual(meldung, self.E.texte.meldung_uno_adresse_unbekannt)
        self.assertNotIn("uno", self.speicher.daten)

    def test_doppelt(self):
        self.assertTrue(self.hinzufuegen()[0])
        ok, meldung = self.hinzufuegen()
        self.assertFalse(ok)
        self.assertEqual(meldung, self.E.texte.meldung_uno_schon_da)

    def test_speicher_kaputt(self):
        self.speicher.kaputt = True
        self.uno.laden()
        self.assertTrue(self.uno.speicher_fehler)
        ok, meldung = self.hinzufuegen()
        self.assertFalse(ok)
        self.assertEqual(meldung, self.E.texte.meldung_speicher_fehler)
        self.assertEqual(self.uno.projekte, [])

    def test_ein_und_ausblenden(self):
        self.hinzufuegen()
        bauchbinde = self.uno.overlays[f"{UNO_TOKEN}/ov-1"]
        self.assertFalse(bauchbinde.sichtbar)
        self.uno.umschalten(bauchbinde)
        self.assertTrue(bauchbinde.beschaeftigt)
        self.uno.umschalten(bauchbinde)  # Doppelklick während es läuft: wird ignoriert
        self.assertTrue(warte_bis(lambda: bauchbinde.sichtbar is True, 3000))
        self.assertTrue(self.netz.overlays[0]["visible"])
        self.assertEqual(self.netz.anzahl("ShowOverlay"), 1)
        self.uno.umschalten(bauchbinde)
        self.assertTrue(warte_bis(lambda: bauchbinde.sichtbar is False, 3000))
        self.assertFalse(self.netz.overlays[0]["visible"])

    def test_tally_folgt_aenderungen_in_uno(self):
        self.uno.laden()
        self.hinzufuegen()
        ticker = self.uno.overlays[f"{UNO_TOKEN}/ov-2"]
        self.assertTrue(ticker.sichtbar)
        self.netz.overlays[1]["visible"] = False  # jemand blendet in Uno selbst aus
        self.assertTrue(warte_bis(lambda: ticker.sichtbar is False, 3000))

    def test_ohne_sichtbarkeit_von_uno(self):
        self.netz.uno_mit_sichtbarkeit = False
        self.hinzufuegen()
        o = self.uno.overlays[f"{UNO_TOKEN}/ov-1"]
        self.assertIsNone(o.sichtbar)  # unbekannt, bis OpenRegie selbst schaltet
        self.uno.umschalten(o)
        self.assertTrue(warte_bis(lambda: o.sichtbar is True, 3000))
        self.uno.auffrischen()
        warte(300)
        self.assertTrue(o.sichtbar)  # bleibt, auch wenn Uno nichts dazu sagt

    def test_neues_overlay_in_uno(self):
        self.uno.laden()
        self.hinzufuegen()
        self.netz.overlays.append({"id": "ov-4", "name": "Uhr", "visible": False})
        self.uno.auffrischen()
        self.assertTrue(warte_bis(lambda: len(self.uno.overlays) == 4, 3000))
        del self.netz.overlays[0]
        self.uno.auffrischen()
        self.assertTrue(warte_bis(lambda: len(self.uno.overlays) == 3, 3000))
        self.assertNotIn(f"{UNO_TOKEN}/ov-1", self.uno.overlays)

    def test_texte_lesen_und_aendern(self):
        self.hinzufuegen()
        o = self.uno.overlays[f"{UNO_TOKEN}/ov-1"]
        fertig = []
        self.uno.felder_laden(o, lambda ok, f: fertig.append(ok))
        self.assertTrue(warte_bis(lambda: fertig, 3000))
        self.assertEqual(o.felder, [("Name", "Kevin"), ("Titel", "Live aus dem Studio")])
        fertig.clear()
        self.uno.feld_setzen(o, "Titel", "Neuer Text äöü", lambda ok, f: fertig.append(ok))
        self.assertTrue(warte_bis(lambda: fertig, 3000))
        self.assertEqual(self.netz.inhalte["ov-1"]["Titel"], "Neuer Text äöü")
        self.assertEqual(dict(o.felder)["Titel"], "Neuer Text äöü")

    def test_uno_fehler_und_kein_internet(self):
        self.hinzufuegen()
        o = self.uno.overlays[f"{UNO_TOKEN}/ov-1"]
        ergebnis = []
        self.netz.uno_kaputt = True
        self.uno.umschalten(o, lambda ok, f: ergebnis.append((ok, f)))
        self.assertTrue(warte_bis(lambda: ergebnis, 3000))
        self.assertEqual(ergebnis[0], (False, self.E.texte.meldung_uno_fehler))
        self.assertFalse(o.sichtbar)
        self.assertFalse(o.beschaeftigt)  # Knopf wieder frei
        ergebnis.clear()
        self.netz.uno_kaputt = False
        self.netz.aus = True
        self.uno.umschalten(o, lambda ok, f: ergebnis.append((ok, f)))
        self.assertTrue(warte_bis(lambda: ergebnis, 3000))
        self.assertEqual(ergebnis[0], (False, self.E.texte.meldung_uno_kein_internet))

    def test_projekt_entfernen(self):
        self.hinzufuegen()
        self.uno.projekt_entfernen(self.uno.projekte[0])
        self.assertEqual(self.uno.overlays, {})
        self.assertNotIn(UNO_TOKEN, self.speicher.daten["uno"])

    def test_langsames_uno_stapelt_nicht(self):
        self.uno.laden()
        self.hinzufuegen()
        self.netz.verzoegerung = 1.5
        vorher = self.netz.anzahl("GetOverlays")
        warte(3500)
        self.netz.verzoegerung = 0
        # Abfrage jede Sekunde, aber höchstens eine gleichzeitig: deutlich weniger als 3
        self.assertLessEqual(self.netz.anzahl("GetOverlays") - vorher, 3)

    def test_geheimer_teil_nicht_im_protokoll(self):
        with self.assertLogs("openregie.uno", level="INFO") as protokoll:
            self.netz.uno_kaputt = True
            self.hinzufuegen()
        self.assertNotIn(UNO_TOKEN, "\n".join(protokoll.output))


if __name__ == "__main__":
    unittest.main()
