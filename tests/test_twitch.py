"""Prüft Twitch-Anmeldung (Device Code Flow ohne Geheimnis) und Titel ändern."""

import json
import unittest

from openregie.geheimspeicher import Arbeitsspeicher
from openregie.twitch.konto import Anmeldung, TwitchKonto

from .falsches_internet import FalschesInternet
from .hilfen import app, internet_einstellungen, warte, warte_bis


class TwitchTest(unittest.TestCase):
    def setUp(self):
        app()
        self.netz = FalschesInternet()
        self.E = internet_einstellungen(self.netz)
        self.speicher = Arbeitsspeicher()
        self.codes = []
        self.meldungen = []
        self.konto = self.neues_konto()

    def neues_konto(self, E=None):
        k = TwitchKonto((E or self.E).twitch, self.E.texte, self.speicher)
        k.code_bereit.connect(lambda c, a: self.codes.append((c, a)))
        k.meldung.connect(lambda t, f: self.meldungen.append((t, f)))
        return k

    def tearDown(self):
        self.konto.beenden()
        self.netz.beenden()
        warte(20)

    def anmelden(self):
        self.konto.laden()
        self.konto.anmelden()
        self.assertTrue(warte_bis(lambda: self.konto.zustand is Anmeldung.WARTET, 3000))
        self.netz.bestaetigt = True
        self.assertTrue(warte_bis(lambda: self.konto.zustand is Anmeldung.ANGEMELDET, 4000))
        self.assertTrue(warte_bis(lambda: self.konto.titel == "Alter Titel", 3000))

    def titel_setzen(self, titel):
        ergebnis = []
        self.konto.titel_setzen(titel, lambda ok, m: ergebnis.append((ok, m)))
        self.assertTrue(warte_bis(lambda: ergebnis, 3000))
        return ergebnis[0]

    def test_ohne_client_id(self):
        E = internet_einstellungen(self.netz, client_id="")
        k = TwitchKonto(E.twitch, E.texte, self.speicher)
        k.laden()
        self.assertIs(k.zustand, Anmeldung.NICHT_EINGERICHTET)
        k.anmelden()
        warte(100)
        self.assertEqual(self.netz.anfragen, [])

    def test_anmelden_ohne_geheimnis(self):
        self.anmelden()
        self.assertEqual(self.codes[0][0], "ABCD-EFGH")
        self.assertIn("twitch.tv/activate", self.codes[0][1])
        # nie ein Geheimnis mitgeschickt
        for _m, _p, inhalt in self.netz.anfragen:
            self.assertNotIn("client_secret", inhalt or {})
        gespeichert = json.loads(self.speicher.daten["twitch"])
        self.assertEqual(gespeichert["user_id"], "4711")
        self.assertTrue(warte_bis(lambda: self.konto.name == "KevinTest", 3000))  # Anzeigename

    def test_titel_aendern(self):
        self.anmelden()
        ok, meldung = self.titel_setzen("  Neuer   Titel\nmit Umlauten äöü 🎮 ")
        self.assertTrue(ok, meldung)
        self.assertEqual(self.netz.titel, "Neuer Titel mit Umlauten äöü 🎮")
        self.assertEqual(meldung, self.E.texte.meldung_twitch_titel_ok)

    def test_titel_leer_oder_zu_lang(self):
        self.anmelden()
        self.assertEqual(self.titel_setzen("   "), (False, self.E.texte.meldung_twitch_titel_leer))
        ok, _ = self.titel_setzen("x" * 141)
        self.assertFalse(ok)
        self.assertEqual(self.netz.titel, "Alter Titel")

    def test_anmeldung_bleibt_nach_neustart(self):
        self.anmelden()
        self.konto.beenden()
        self.konto = self.neues_konto()
        self.konto.laden()
        self.assertTrue(warte_bis(lambda: self.konto.zustand is Anmeldung.ANGEMELDET, 3000))
        self.assertTrue(warte_bis(lambda: self.konto.titel == "Alter Titel", 3000))

    def test_abgelaufene_anmeldung_wird_erneuert(self):
        self.anmelden()
        self.netz.gueltige_tokens.clear()  # Zugangsschlüssel abgelaufen
        ok, meldung = self.titel_setzen("Nach Erneuerung")
        self.assertTrue(ok, meldung)
        self.assertEqual(self.netz.titel, "Nach Erneuerung")
        self.assertEqual(json.loads(self.speicher.daten["twitch"])["access_token"], "tok2")

    def test_abgelaufen_beim_start(self):
        self.anmelden()
        self.netz.gueltige_tokens.clear()
        self.konto.beenden()
        self.konto = self.neues_konto()
        self.konto.laden()
        self.assertTrue(warte_bis(lambda: self.konto.zustand is Anmeldung.ANGEMELDET and self.konto.titel, 3000))

    def test_nach_30_tagen_neu_anmelden(self):
        self.anmelden()
        self.netz.gueltige_tokens.clear()
        self.netz.gueltige_erneuerungen.clear()  # auch Erneuerung abgelaufen
        ok, _ = self.titel_setzen("Geht nicht")
        self.assertFalse(ok)
        self.assertIs(self.konto.zustand, Anmeldung.ABGEMELDET)
        self.assertIn((self.E.texte.meldung_twitch_neu_anmelden, True), self.meldungen)
        self.assertNotIn("twitch", self.speicher.daten)

    def test_abgelehnt(self):
        self.konto.laden()
        self.netz.abgelehnt = True
        self.konto.anmelden()
        self.assertTrue(warte_bis(lambda: self.konto.zustand is Anmeldung.WARTET, 3000))
        self.assertTrue(warte_bis(lambda: self.konto.zustand is Anmeldung.ABGEMELDET, 4000))
        self.assertIn((self.E.texte.meldung_twitch_abgelehnt, True), self.meldungen)

    def test_abbrechen(self):
        self.konto.laden()
        self.konto.anmelden()
        self.assertTrue(warte_bis(lambda: self.konto.zustand is Anmeldung.WARTET, 3000))
        self.konto.anmeldung_abbrechen()
        self.netz.bestaetigt = True
        warte(1500)
        self.assertIs(self.konto.zustand, Anmeldung.ABGEMELDET)

    def test_code_abgelaufen(self):
        jetzt = [1000.0]
        k = TwitchKonto(self.E.twitch, self.E.texte, self.speicher, uhr=lambda: jetzt[0])
        k.meldung.connect(lambda t, f: self.meldungen.append((t, f)))
        k.laden()
        k.anmelden()
        self.assertTrue(warte_bis(lambda: k.zustand is Anmeldung.WARTET, 3000))
        jetzt[0] += 1801
        self.assertTrue(warte_bis(lambda: k.zustand is Anmeldung.ABGEMELDET, 3000))
        self.assertIn((self.E.texte.meldung_twitch_code_abgelaufen, True), self.meldungen)
        k.beenden()

    def test_falsche_client_id(self):
        E = internet_einstellungen(self.netz, client_id="falsch")
        k = TwitchKonto(E.twitch, E.texte, self.speicher)
        k.meldung.connect(lambda t, f: self.meldungen.append((t, f)))
        k.laden()
        k.anmelden()
        self.assertTrue(warte_bis(lambda: self.meldungen, 3000))
        self.assertEqual(self.meldungen[-1], (self.E.texte.meldung_twitch_client_id_falsch, True))
        self.assertIs(k.zustand, Anmeldung.ABGEMELDET)
        k.beenden()

    def test_abmelden(self):
        self.anmelden()
        self.konto.abmelden()
        self.assertIs(self.konto.zustand, Anmeldung.ABGEMELDET)
        self.assertNotIn("twitch", self.speicher.daten)
        self.assertTrue(warte_bis(lambda: not self.netz.gueltige_tokens, 3000))  # bei Twitch ungültig gemacht

    def test_kein_internet_beim_start(self):
        self.anmelden()
        self.konto.beenden()
        self.netz.aus = True
        self.konto = self.neues_konto()
        self.konto.laden()
        self.assertTrue(warte_bis(lambda: self.meldungen and self.meldungen[-1][0] ==
                                  self.E.texte.meldung_twitch_kein_internet, 3000))
        self.assertIs(self.konto.zustand, Anmeldung.ANGEMELDET)  # Anmeldung nicht weggeworfen
        self.assertIn("twitch", self.speicher.daten)


if __name__ == "__main__":
    unittest.main()
