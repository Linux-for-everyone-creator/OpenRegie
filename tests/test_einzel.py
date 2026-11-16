"""Prüft, wie OpenRegie Bauplan und Zustand eines Einzel-Unos versteht.

Die Beispieldaten haben denselben Aufbau wie die echte Antwort von Kevins
„Countdown | Circles“ (14.11.2026), nur mit erfundenen Kennungen.
"""

import unittest

from openregie.uno import einzel

from .falsches_internet import CONTENT, COUNTDOWN, HAUPT, MESSAGE, FalschesSingular


class BauplanTest(unittest.TestCase):
    def setUp(self):
        self.s = FalschesSingular()
        self.plan = einzel.bauplan_lesen(self.s.model())

    def test_bauplan(self):
        p = self.plan
        self.assertEqual(p.haupt, HAUPT)
        self.assertEqual(p.ein_teile, [HAUPT, CONTENT, COUNTDOWN])  # Message steht von Haus aus auf „Out“
        self.assertEqual(p.aktiv_feld, "Active")
        self.assertEqual(p.zeigen_feld, (CONTENT, "ShowOverlay"))  # Uno-eigener Ein/Aus-Schalter
        self.assertEqual(p.timer, (CONTENT, "Timer"))
        self.assertEqual(p.dauer, (CONTENT, "BeginTime"))
        self.assertEqual(p.textfelder, [(CONTENT, "Message", "Message")])

    def test_ein_aus_befehl(self):
        ein = einzel.ein_aus_befehl(self.plan, True)
        self.assertEqual(ein, [{"subCompositionId": HAUPT, "state": "In", "payload": {"Active": True}},
                               {"subCompositionId": CONTENT, "state": "In", "payload": {"ShowOverlay": True}},
                               {"subCompositionId": COUNTDOWN, "state": "In"}])
        self.assertTrue(self.s.patch(ein))
        self.assertEqual(self.s.was_man_sieht(), "komplett")
        aus = einzel.ein_aus_befehl(self.plan, False)
        # Ausblenden NUR über den Uno-Schalter: blendet an Ort und Stelle (in der Mitte) aus
        self.assertEqual(aus, [{"subCompositionId": CONTENT, "payload": {"ShowOverlay": False}}])
        self.assertTrue(self.s.patch(aus))
        self.assertEqual(self.s.was_man_sieht(), "nichts")
        self.assertTrue(self.s.patch(ein))  # und wieder einblenden geht
        self.assertEqual(self.s.was_man_sieht(), "komplett")

    def test_alter_weg_laesst_kreise_stehen(self):
        """Gegenprobe zum gemeldeten Fehler: Teile auf „Out“ + Active aus → Kreise bleiben in der Mitte."""
        self.s.patch(einzel.ein_aus_befehl(self.plan, True))
        self.s.patch([{"subCompositionId": HAUPT, "state": "Out", "payload": {"Active": False}},
                      {"subCompositionId": CONTENT, "state": "Out"}, {"subCompositionId": COUNTDOWN, "state": "Out"}])
        self.assertEqual(self.s.was_man_sieht(), "nur_kreise")

    def test_ohne_uno_schalter_alter_weg(self):
        model = self.s.model()
        model[0]["subcompositions"][0]["model"] = [f for f in model[0]["subcompositions"][0]["model"]
                                                  if f["id"] != "ShowOverlay"]
        plan = einzel.bauplan_lesen(model)
        self.assertIsNone(plan.zeigen_feld)
        aus = einzel.ein_aus_befehl(plan, False)
        self.assertEqual([e["state"] for e in aus], ["Out", "Out", "Out"])

    def test_ohne_active_nur_kreis(self):
        """Gegenprobe zum echten Test: nur die Teile einblenden reicht nicht."""
        self.s.patch([{"subCompositionId": t, "state": "In"} for t in (HAUPT, CONTENT, COUNTDOWN)])
        self.assertEqual(self.s.was_man_sieht(), "nur_kreise")

    def test_zustand(self):
        teile = einzel.teile_lesen(self.s.control())
        self.assertFalse(einzel.ist_sichtbar(teile, self.plan))
        self.s.zustand[HAUPT] = "In"
        self.assertTrue(einzel.ist_sichtbar(einzel.teile_lesen(self.s.control()), self.plan))
        self.s.zustand[HAUPT] = "Out2"
        self.assertFalse(einzel.ist_sichtbar(einzel.teile_lesen(self.s.control()), self.plan))
        self.s.zustand[HAUPT] = "In"
        self.s.werte[CONTENT]["ShowOverlay"] = False  # Uno-Schalter aus (z. B. in Uno selbst)
        self.assertFalse(einzel.ist_sichtbar(einzel.teile_lesen(self.s.control()), self.plan))
        self.assertEqual(einzel.wert(teile, self.plan.dauer), 300)
        self.assertEqual([f.wert for f in einzel.textfelder_lesen(teile, self.plan)], ["COUNTDOWN END MESSAGE"])

    def test_ohne_countdown_und_unsinn(self):
        model = [{"id": "h", "model": [{"id": "Name", "type": "text", "title": "Name"}], "subcompositions": []}]
        p = einzel.bauplan_lesen(model)
        self.assertEqual((p.timer, p.dauer, p.aktiv_feld, p.ein_teile), (None, None, None, ["h"]))
        self.assertEqual(p.textfelder, [("h", "Name", "Name")])
        for unsinn in (None, [], {}, "x", [{"name": "ohne id"}]):
            self.assertIsNone(einzel.bauplan_lesen(unsinn))
        self.assertEqual(einzel.teile_lesen("x"), {})
        self.assertIsNone(einzel.ist_sichtbar({}, p))


class RestzeitTest(unittest.TestCase):
    def test_echte_werte(self):
        # Echte Werte vom Test: nach ~6,5 s angehalten, Dauer 17980 s (04:59:40)
        timer = {"UTC": 1794674104112, "isRunning": False, "value": 6493}
        self.assertEqual(einzel.restzeit_ms(timer, 17980, 0), 17980_000 - 6493)
        self.assertEqual(einzel.zeit_text(einzel.restzeit_ms(timer, 17980, 0)), "4:59:34")

    def test_laeuft(self):
        timer = {"UTC": 1000, "isRunning": True, "value": 2000}
        self.assertEqual(einzel.restzeit_ms(timer, 10, 4000), 10_000 - 2000 - 3000)
        self.assertEqual(einzel.restzeit_ms(timer, 10, 999_999), 0)  # nie unter 0

    def test_zeit_text(self):
        self.assertEqual(einzel.zeit_text(300_000), "05:00")
        self.assertEqual(einzel.zeit_text(299_001), "05:00")  # aufgerundet
        self.assertEqual(einzel.zeit_text(0), "00:00")
        self.assertEqual(einzel.zeit_text(17980_000), "4:59:40")
        self.assertEqual(einzel.zeit_text(None), "--:--")

    def test_unsinn(self):
        self.assertIsNone(einzel.restzeit_ms(None, 10, 0))
        self.assertIsNone(einzel.restzeit_ms({"value": 0}, None, 0))
        self.assertIsNone(einzel.restzeit_ms({"value": "x"}, 10, 0))
        self.assertEqual(einzel.dauer_sekunden("17980"), 17980)
        self.assertIsNone(einzel.dauer_sekunden("abc"))


class ZeitLesenTest(unittest.TestCase):
    """Eingetippte Countdown-Zeit verstehen (Klick auf die große Zeit)."""
    HOECHST = 35999  # 9:59:59 wie in einstellungen.toml

    def lesen(self, text):
        return einzel.zeit_lesen(text, self.HOECHST)

    def test_gueltige_zeiten(self):
        for text, sekunden in [("5:00", 300), ("12:30", 750), ("05:00", 300), ("0:30", 30), ("0:01", 1),
                               ("5", 300), ("90", 5400), ("90:00", 5400), ("1:05:00", 3900), ("9:59:59", 35999),
                               (" 5 : 00 ", 300), ("5.30", 330), ("5,30", 330), ("599:59", 35999)]:
            self.assertEqual(self.lesen(text), (sekunden, ""), text)

    def test_buchstaben_und_unsinn(self):
        for text in ["abc", "5:0a", "fünf", "5:", ":30", "5::00", "-5:00", "5:3", "5:300", "1:2:3",
                     "+5", "5 Min", "1:00:00:00", "12345", "٥:٠٠", "5e2", "0x10"]:
            self.assertEqual(self.lesen(text), (None, einzel.ZEIT_FORMAT), text)

    def test_unmoegliche_zeiten(self):
        for text in ["5:60", "5:99", "1:60:00", "1:00:60"]:
            self.assertEqual(self.lesen(text), (None, einzel.ZEIT_UEBER_59), text)
        for text in ["0", "0:00", "00:00", "0:00:00"]:
            self.assertEqual(self.lesen(text), (None, einzel.ZEIT_NULL), text)
        for text in ["10:00:00", "600:00", "9999", "9:59:60"]:
            self.assertIn(self.lesen(text)[1], (einzel.ZEIT_ZU_LANG, einzel.ZEIT_UEBER_59), text)
        self.assertEqual(self.lesen("10:00:00"), (None, einzel.ZEIT_ZU_LANG))
        for text in ["", "   ", None]:
            self.assertEqual(self.lesen(text), (None, einzel.ZEIT_LEER), repr(text))

    def test_hat_gezaehlt(self):
        self.assertFalse(einzel.hat_gezaehlt(None))
        self.assertFalse(einzel.hat_gezaehlt({"value": 0, "UTC": 0, "isRunning": False}))
        self.assertTrue(einzel.hat_gezaehlt({"value": 0, "UTC": 5, "isRunning": True}))
        self.assertTrue(einzel.hat_gezaehlt({"value": 1200, "UTC": 0, "isRunning": False}))
        self.assertTrue(einzel.hat_gezaehlt({"value": "kaputt", "isRunning": False}))


if __name__ == "__main__":
    unittest.main()
