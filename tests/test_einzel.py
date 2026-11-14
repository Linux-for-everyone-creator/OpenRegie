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
        self.assertEqual(p.timer, (CONTENT, "Timer"))
        self.assertEqual(p.dauer, (CONTENT, "BeginTime"))
        self.assertEqual(p.textfelder, [(CONTENT, "Message", "Message")])

    def test_ein_aus_befehl(self):
        ein = einzel.ein_aus_befehl(self.plan, True)
        self.assertEqual(ein, [{"subCompositionId": HAUPT, "state": "In", "payload": {"Active": True}},
                               {"subCompositionId": CONTENT, "state": "In"},
                               {"subCompositionId": COUNTDOWN, "state": "In"}])
        self.assertTrue(self.s.patch(ein))
        self.assertTrue(self.s.komplett_sichtbar())
        self.assertTrue(self.s.patch(einzel.ein_aus_befehl(self.plan, False)))
        self.assertTrue(self.s.ganz_aus())

    def test_ohne_active_nur_kreis(self):
        """Gegenprobe zum echten Test: nur die Teile einblenden reicht nicht."""
        self.s.patch([{"subCompositionId": t, "state": "In"} for t in (HAUPT, CONTENT, COUNTDOWN)])
        self.assertFalse(self.s.komplett_sichtbar())

    def test_zustand(self):
        teile = einzel.teile_lesen(self.s.control())
        self.assertFalse(einzel.ist_sichtbar(teile, self.plan))
        self.s.zustand[HAUPT] = "In"
        self.assertTrue(einzel.ist_sichtbar(einzel.teile_lesen(self.s.control()), self.plan))
        self.s.zustand[HAUPT] = "Out2"
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


if __name__ == "__main__":
    unittest.main()
