"""Prüft die Overlays.uno-Anbindung mit einem nachgeahmten Uno."""

import unittest

from openregie.geheimspeicher import Arbeitsspeicher
import json

from openregie.uno.verwaltung import (KEIN_INTERNET, NICHT_GEFUNDEN, SONSTIGER_FEHLER, UNBEKANNTER_BEFEHL,
                                      UnoVerwaltung, felder_lesen, fehlerart, ist_textfeld, overlays_lesen,
                                      sichtbarkeit_lesen, token_aus_text)

from .falsches_internet import (CONTENT, EINZEL_ADRESSE_TEXT, EINZEL_TOKEN, HAUPT, MESSAGE, UNO_ADRESSE_TEXT,
                                UNO_TOKEN, FalschesInternet)
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
        paare = lambda felder: [(f.kennung, f.wert) for f in felder]
        self.assertEqual(paare(felder_lesen(inhalt)), [("Name", "Kevin"), ("Leer", "")])
        self.assertEqual(paare(felder_lesen({"content": {"A": "b"}})), [("A", "b")])
        self.assertEqual(paare(felder_lesen([{"fieldId": "A", "value": "b"}, {"id": "C", "value": 3}])), [("A", "b")])
        self.assertFalse(ist_textfeld("#abc"))
        self.assertTrue(ist_textfeld("#1 im Stream"))


class FehlerartTest(unittest.TestCase):
    def test_invalid_command_heisst_adresse_gueltig(self):
        # genau die Antwort, die ein echtes Einzel-Uno auf GetOverlays gibt
        antwort = {"error": {"message": "Invalid command: GetOverlays", "code": 400}}
        self.assertEqual(fehlerart(400, antwort), UNBEKANNTER_BEFEHL)
        self.assertEqual(fehlerart(400, {"error": {"message": "invalid command"}}), UNBEKANNTER_BEFEHL)

    def test_nicht_gefunden(self):
        self.assertEqual(fehlerart(404, {"error": {"message": "API Not Found", "code": 404}}), NICHT_GEFUNDEN)
        self.assertEqual(fehlerart(401, None), NICHT_GEFUNDEN)
        self.assertEqual(fehlerart(403, {}), NICHT_GEFUNDEN)

    def test_sonstiges(self):
        self.assertEqual(fehlerart(0, None), KEIN_INTERNET)
        self.assertEqual(fehlerart(500, {"error": {"message": "Server Error"}}), SONSTIGER_FEHLER)
        self.assertEqual(fehlerart(429, None), SONSTIGER_FEHLER)  # zu viele Anfragen
        self.assertEqual(fehlerart(400, {"error": {"message": "Missing id"}}), SONSTIGER_FEHLER)
        self.assertEqual(fehlerart(400, "kein json"), SONSTIGER_FEHLER)


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
        self.assertTrue(warte_bis(lambda: self.uno.speicher_fehler, 3000))
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
        self.assertEqual([(f.kennung, f.wert) for f in o.felder], [("Name", "Kevin"), ("Titel", "Live aus dem Studio")])
        fertig.clear()
        self.uno.feld_setzen(o, o.felder[1], "Neuer Text äöü", lambda ok, f: fertig.append(ok))
        self.assertTrue(warte_bis(lambda: fertig, 3000))
        self.assertEqual(self.netz.inhalte["ov-1"]["Titel"], "Neuer Text äöü")
        self.assertEqual(o.felder[1].wert, "Neuer Text äöü")

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
        # „nicht erreichbar“ steht EINMAL unter der Bibliothek, nicht zusätzlich im Bedienfeld
        self.assertEqual(ergebnis[0], (False, ""))
        self.assertIn((self.E.texte.meldung_uno_kein_internet, True), self.meldungen)
        self.assertIs(o.projekt.erreichbar, False)

    def test_projekt_entfernen(self):
        self.hinzufuegen()
        self.uno.projekt_entfernen(self.uno.projekte[0])
        self.assertEqual(self.uno.overlays, {})
        self.assertTrue(warte_bis(lambda: UNO_TOKEN not in self.speicher.daten["uno"], 3000))

    def test_langsames_uno_stapelt_nicht(self):
        self.uno.laden()
        self.hinzufuegen()
        self.netz.verzoegerung = 1.5
        vorher = self.netz.anzahl("GetOverlays")
        warte(3500)
        self.netz.verzoegerung = 0
        # Abfrage jede Sekunde, aber höchstens eine gleichzeitig: deutlich weniger als 3
        self.assertLessEqual(self.netz.anzahl("GetOverlays") - vorher, 3)

    # --- Einzel-Unos (kennen kein GetOverlays, Steuerung über Singular) -------
    def einzel(self):
        return self.uno.overlays[f"{EINZEL_TOKEN}/"]

    def api_befehle_einzel(self):
        return [d for d in self.netz.einzel_befehle if "command" in d]

    def test_einzel_uno_hinzufuegen(self):
        """Der Fehler aus Build 1.1: Einzel-Uno galt als „Adresse unbekannt“."""
        self.netz.einzel.vorschau_adresse = "//image.example/vorschau.jpg"  # so liefert es das echte Uno
        self.uno.laden()
        ok, meldung = self.hinzufuegen(EINZEL_ADRESSE_TEXT)
        self.assertTrue(ok, meldung)
        self.assertEqual(meldung, self.E.texte.meldung_uno_einzel_ok)
        self.assertEqual(len(self.uno.overlays), 1)
        o = self.einzel()
        self.assertEqual(o.name, "Countdown | Circles")  # echter Name von Uno
        self.assertEqual(o.vorschaubild, "https://image.example/vorschau.jpg")
        self.assertFalse(o.sichtbar)
        self.assertTrue(o.hat_countdown)
        self.assertEqual(o.dauer, 300)
        self.assertEqual([(f.kennung, f.wert) for f in o.felder], [("Message", "COUNTDOWN END MESSAGE")])
        gespeichert = json.loads(self.speicher.daten["uno"])
        self.assertEqual(gespeichert, [{"name": "Countdown | Circles", "token": EINZEL_TOKEN, "einzeln": True}])
        self.assertFalse([m for m in self.meldungen if m[1]])  # keine rote Meldung

    def test_einzel_uno_komplett_ein_und_aus(self):
        """Wie mit dem echten Uno herausgefunden: Haupt+Content+Countdown auf In und Active an."""
        self.hinzufuegen(EINZEL_ADRESSE_TEXT)
        o = self.einzel()
        self.uno.umschalten(o)
        self.assertTrue(warte_bis(lambda: o.sichtbar is True, 3000))
        self.assertTrue(self.netz.einzel.komplett_sichtbar(), self.netz.einzel.zustand)
        self.assertEqual(self.netz.einzel.zustand[MESSAGE], "Out1")  # Endtext-Teil bleibt aus
        self.uno.umschalten(o)
        self.assertTrue(warte_bis(lambda: o.sichtbar is False, 3000))
        # der gemeldete Fehler: vorher blieben hier die Kreise in der Mitte stehen
        self.assertEqual(self.netz.einzel.was_man_sieht(), "nichts")
        # kein „ShowOverlay“ über …/api – das zeigt beim echten Einzel-Uno nichts an
        self.assertEqual([d["command"] for d in self.api_befehle_einzel()], ["GetOverlays"])

    def test_einzel_uno_texte(self):
        self.hinzufuegen(EINZEL_ADRESSE_TEXT)
        o = self.einzel()
        fertig = []
        self.uno.feld_setzen(o, o.felder[0], "Gleich geht's los!", lambda ok, f: fertig.append(ok))
        self.assertTrue(warte_bis(lambda: fertig == [True], 3000))
        self.assertEqual(self.netz.einzel.werte[CONTENT]["Message"], "Gleich geht's los!")
        self.assertEqual(o.felder[0].wert, "Gleich geht's los!")

    def test_einzel_uno_countdown(self):
        e = self.netz.einzel
        e.jetzt = 1_000_000
        self.hinzufuegen(EINZEL_ADRESSE_TEXT)
        o = self.einzel()

        def schritt(befehl):
            fertig = []
            self.uno.timer_befehl(o, befehl, lambda ok, f: fertig.append(ok))
            self.assertTrue(warte_bis(lambda: fertig, 3000))
            self.assertEqual(fertig, [True])

        self.assertEqual(o.restzeit_ms(e.jetzt), 300_000)
        schritt("play")
        self.assertTrue(o.timer["isRunning"])
        e.jetzt += 5_000
        self.assertEqual(o.restzeit_ms(e.jetzt), 295_000)  # läuft, auch ohne neue Abfrage
        schritt("pause")
        self.assertFalse(o.timer["isRunning"])
        self.assertEqual(o.restzeit_ms(e.jetzt + 60_000), 295_000)  # pausiert: bleibt stehen
        schritt("reset")
        self.assertEqual(o.restzeit_ms(e.jetzt), 300_000)
        fertig = []
        self.uno.dauer_setzen(o, 600, lambda ok, f: fertig.append(ok))
        self.assertEqual(o.dauer, 600)  # sofort angezeigt
        self.assertTrue(warte_bis(lambda: fertig == [True], 3000))
        self.assertEqual(e.werte[CONTENT]["BeginTime"], 600)
        self.uno.dauer_setzen(o, -50)
        self.assertTrue(warte_bis(lambda: e.werte[CONTENT]["BeginTime"] == 0, 3000))  # nie unter 0

    def test_einzel_uno_nur_control_abfragen(self):
        self.speicher.json_schreiben("uno", [{"name": "Countdown | Circles", "token": EINZEL_TOKEN, "einzeln": True}])
        self.uno.laden()
        self.assertTrue(warte_bis(lambda: self.uno.overlays and self.einzel().bauplan is not None, 3000))
        self.netz.einzel.zustand[HAUPT] = "In"  # jemand blendet in Uno selbst ein
        self.assertTrue(warte_bis(lambda: self.einzel().sichtbar is True, 3000))  # Tally folgt
        self.netz.einzel.werte[CONTENT]["ShowOverlay"] = False  # in Uno selbst ausgeschaltet
        self.assertTrue(warte_bis(lambda: self.einzel().sichtbar is False, 3000))  # Tally folgt auch hier
        self.assertEqual(self.api_befehle_einzel(), [])  # kein sinnloses GetOverlays

    def test_altes_gespeichertes_einzel_uno_wird_erkannt(self):
        # gespeichert mit Build 1.1, noch ohne „einzeln“
        self.speicher.json_schreiben("uno", [{"name": "Uno-Projekt 1", "token": EINZEL_TOKEN}])
        self.uno.laden()
        self.assertTrue(warte_bis(lambda: f"{EINZEL_TOKEN}/" in self.uno.overlays
                                  and self.einzel().bauplan is not None, 3000))
        self.assertEqual(len(self.uno.overlays), 1)
        self.assertTrue(warte_bis(lambda: json.loads(self.speicher.daten["uno"])[0].get("einzeln"), 3000))
        gespeichert = json.loads(self.speicher.daten["uno"])[0]
        self.assertEqual(gespeichert["name"], "Countdown | Circles")
        self.assertFalse([m for m in self.meldungen if m[1]])

    def test_einzel_uno_ohne_internet_beim_start(self):
        self.speicher.json_schreiben("uno", [{"name": "Countdown | Circles", "token": EINZEL_TOKEN, "einzeln": True}])
        self.netz.aus = True
        self.uno.laden()
        self.assertTrue(warte_bis(lambda: self.uno.overlays, 3000))
        o = self.einzel()  # steht trotzdem in der Liste
        self.assertEqual(o.name, "Countdown | Circles")
        self.assertFalse(o.bereit)
        ergebnis = []
        self.uno.umschalten(o, lambda ok, f: ergebnis.append((ok, f)))
        self.assertTrue(warte_bis(lambda: ergebnis, 3000))
        self.assertEqual(ergebnis[0], (False, ""))  # still: wird noch geladen
        self.assertTrue(warte_bis(lambda: self.meldungen, 4000))
        self.assertEqual(self.meldungen, [(self.E.texte.meldung_uno_kein_internet, True)])
        warte(2500)  # weitere vergebliche Abfragen …
        self.assertEqual(len(self.meldungen), 1)  # … aber die Meldung kommt nur EINMAL
        self.netz.aus = False
        self.assertTrue(warte_bis(lambda: o.bereit, 6000))  # nächste Abfrage holt es
        self.assertIs(self.einzel(), o)  # dasselbe Overlay, nicht ausgetauscht
        self.assertTrue(warte_bis(lambda: ("", False) in self.meldungen, 3000))  # Meldung verschwindet

    def test_neustart_overlay_wird_gefuellt_nicht_ersetzt(self):
        """Fehler aus Build 1.1: nach dem Neustart hing „Ausgewählt“ an einem leeren Platzhalter."""
        self.speicher.json_schreiben("uno", [{"name": "Countdown | Circles", "token": EINZEL_TOKEN, "einzeln": True}])
        self.netz.verzoegerung = 0.3
        self.uno.laden()
        self.assertTrue(warte_bis(lambda: self.uno.overlays, 3000))
        platzhalter = self.einzel()
        self.assertFalse(platzhalter.bereit)
        self.assertTrue(warte_bis(lambda: platzhalter.bereit, 5000))
        self.assertIs(self.einzel(), platzhalter)
        self.assertTrue(platzhalter.hat_countdown)
        self.assertEqual([f.kennung for f in platzhalter.felder], ["Message"])
        self.assertFalse([m for m in self.meldungen if m[1]])

    def test_uno_antwortet_gar_nicht(self):
        """Zeitüberschreitung: nach dem Zeitlimit „nicht erreichbar“ – nicht ewig warten."""
        import time
        self.hinzufuegen(EINZEL_ADRESSE_TEXT)
        o = self.einzel()
        self.netz.verzoegerung = 4  # länger als das Zeitlimit (2 s in den Tests)
        ergebnis = []
        start = time.monotonic()
        self.uno.umschalten(o, lambda ok, f: ergebnis.append((ok, f)))
        self.assertTrue(warte_bis(lambda: ergebnis, 3500))
        self.assertLess(time.monotonic() - start, 3.0)
        self.assertEqual(ergebnis[0], (False, ""))
        self.assertIn((self.E.texte.meldung_uno_kein_internet, True), self.meldungen)
        self.assertFalse(o.beschaeftigt)  # Knopf wieder frei
        self.netz.verzoegerung = 0

    def test_invalid_command_still_ausgrauen(self):
        """400 „Invalid command“ bei einer Funktion: still ausgrauen, keine rote Meldung."""
        from openregie.uno.verwaltung import TEXTE
        self.hinzufuegen()
        o = self.uno.overlays[f"{UNO_TOKEN}/ov-1"]
        self.netz.unbekannte_befehle.add("GetOverlayContent")
        ergebnis = []
        self.uno.felder_laden(o, lambda ok, f: ergebnis.append((ok, f)))
        self.assertTrue(warte_bis(lambda: ergebnis, 3000))
        self.assertEqual(ergebnis[0], (False, ""))
        self.assertIn(TEXTE, o.nicht_unterstuetzt)
        self.assertFalse([m for m in self.meldungen if m[1]])
        self.assertIsNot(o.projekt.erreichbar, False)  # Uno ist ja erreichbar

    def test_adresse_ungueltig_spaeter(self):
        """Token wird bei Uno gelöscht: „Adresse ungültig“, einmal, Lampen grau."""
        from openregie.oberflaeche.overlay_bereich import AUS, lampen_zustand
        self.uno.laden()
        self.hinzufuegen(EINZEL_ADRESSE_TEXT)
        self.netz.einzel_tokens.clear()
        self.assertTrue(warte_bis(lambda: (self.E.texte.meldung_uno_adresse_unbekannt, True) in self.meldungen, 3000))
        warte(2200)
        self.assertEqual(self.meldungen.count((self.E.texte.meldung_uno_adresse_unbekannt, True)), 1)
        self.assertEqual(lampen_zustand(self.einzel()), AUS)

    def test_beide_arten_zusammen(self):
        self.uno.laden()
        self.assertTrue(self.hinzufuegen()[0])
        self.assertTrue(self.hinzufuegen(EINZEL_ADRESSE_TEXT)[0])
        self.assertEqual([o.name for o in self.uno.overlays.values()],
                         ["Bauchbinde", "News-Ticker", "Countdown", "Countdown | Circles"])
        self.uno.auffrischen()
        warte(500)
        self.assertEqual(len(self.uno.overlays), 4)
        self.uno.projekt_entfernen(self.uno.projekte[1])
        self.assertEqual(len(self.uno.overlays), 3)

    def test_einzel_uno_doppelt(self):
        self.assertTrue(self.hinzufuegen(EINZEL_ADRESSE_TEXT)[0])
        self.assertEqual(self.hinzufuegen(EINZEL_ADRESSE_TEXT), (False, self.E.texte.meldung_uno_schon_da))

    def test_nur_echtes_nicht_gefunden_ist_rot_adresse_unbekannt(self):
        """Kein Internet oder Uno-Störung darf nicht als „Adresse unbekannt“ erscheinen."""
        self.netz.aus = True
        self.assertEqual(self.hinzufuegen(), (False, self.E.texte.meldung_uno_kein_internet))
        self.netz.aus = False
        self.netz.uno_kaputt = True
        self.assertEqual(self.hinzufuegen(), (False, self.E.texte.meldung_uno_fehler))
        self.netz.uno_kaputt = False
        self.assertEqual(self.hinzufuegen("https://app.overlays.uno/apiv2/controlapps/GIBTSNICHT123/api"),
                         (False, self.E.texte.meldung_uno_adresse_unbekannt))
        self.assertNotIn("uno", self.speicher.daten)

    def test_geheimer_teil_nicht_im_protokoll(self):
        with self.assertLogs("openregie.uno", level="INFO") as protokoll:
            self.netz.uno_kaputt = True
            self.hinzufuegen()
        self.assertNotIn(UNO_TOKEN, "\n".join(protokoll.output))


if __name__ == "__main__":
    unittest.main()
