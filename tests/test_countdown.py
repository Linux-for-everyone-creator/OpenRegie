import threading
import unittest

from openregie.titel.countdown import Countdown, Zustand, als_text


class TestUhr:
    def __init__(self):
        self.jetzt = 1000.0

    def __call__(self):
        return self.jetzt

    def vor(self, sekunden):
        self.jetzt += sekunden


def neuer(start=300, hoechst=5999):
    uhr = TestUhr()
    return Countdown("Countdown", start, hoechst, uhr=uhr), uhr


class TextTest(unittest.TestCase):
    def test_format(self):
        self.assertEqual(als_text(300), "05:00")
        self.assertEqual(als_text(0), "00:00")
        self.assertEqual(als_text(5999), "99:59")
        self.assertEqual(als_text(59), "00:59")
        self.assertEqual(als_text(61), "01:01")

    def test_aufrunden(self):
        self.assertEqual(als_text(4.2), "00:05")
        self.assertEqual(als_text(0.001), "00:01")
        self.assertEqual(als_text(299.9999999), "05:00")  # Rechen-Ungenauigkeit
        self.assertEqual(als_text(-3), "00:00")


class CountdownTest(unittest.TestCase):
    def test_startzustand(self):
        cd, _ = neuer()
        self.assertEqual(cd.zustand, Zustand.BEREIT)
        self.assertEqual(cd.text(), "05:00")
        self.assertEqual(cd.dauer, 300)

    def test_laeuft_ab(self):
        cd, uhr = neuer(10)
        cd.start()
        self.assertEqual(cd.zustand, Zustand.LAEUFT)
        self.assertEqual(cd.text(), "00:10")
        uhr.vor(0.5)
        self.assertEqual(cd.text(), "00:10")
        uhr.vor(0.5)
        self.assertEqual(cd.text(), "00:09")
        uhr.vor(8.9)
        self.assertEqual(cd.text(), "00:01")
        self.assertEqual(cd.zustand, Zustand.LAEUFT)
        uhr.vor(0.1)
        self.assertEqual(cd.text(), "00:00")
        self.assertEqual(cd.zustand, Zustand.ABGELAUFEN)
        uhr.vor(100)
        self.assertEqual(cd.rest(), 0)

    def test_pause_und_weiter(self):
        cd, uhr = neuer(60)
        cd.start()
        uhr.vor(20)
        cd.pause()
        self.assertEqual(cd.zustand, Zustand.PAUSIERT)
        uhr.vor(500)  # Zeit in der Pause zählt nicht
        self.assertEqual(cd.text(), "00:40")
        cd.start()
        self.assertEqual(cd.zustand, Zustand.LAEUFT)
        uhr.vor(10)
        self.assertEqual(cd.text(), "00:30")

    def test_mehrfach_pause_und_start(self):
        cd, uhr = neuer(60)
        cd.start(); cd.start()  # doppelt Start darf nichts verschieben
        uhr.vor(5)
        cd.start()
        self.assertEqual(cd.text(), "00:55")
        cd.pause(); cd.pause()
        self.assertEqual(cd.zustand, Zustand.PAUSIERT)
        self.assertEqual(cd.text(), "00:55")

    def test_stopp_setzt_zurueck(self):
        cd, uhr = neuer(90)
        cd.start(); uhr.vor(30); cd.stopp()
        self.assertEqual(cd.zustand, Zustand.BEREIT)
        self.assertEqual(cd.text(), "01:30")
        cd.start(); uhr.vor(30); cd.pause(); cd.stopp()
        self.assertEqual(cd.text(), "01:30")
        cd.start(); uhr.vor(1000); cd.stopp()
        self.assertEqual(cd.zustand, Zustand.BEREIT)
        self.assertEqual(cd.text(), "01:30")

    def test_plus_minus_im_stand(self):
        cd, _ = neuer(300)
        cd.aendern(60)
        self.assertEqual(cd.text(), "06:00")
        cd.aendern(-10)
        self.assertEqual(cd.text(), "05:50")
        self.assertEqual(cd.dauer, 350)

    def test_grenzen(self):
        cd, _ = neuer(30, hoechst=5999)
        cd.aendern(-60)
        self.assertEqual(cd.dauer, 0)
        self.assertEqual(cd.text(), "00:00")
        cd.aendern(-10)
        self.assertEqual(cd.dauer, 0)
        for _ in range(200):
            cd.aendern(60)
        self.assertEqual(cd.dauer, 5999)
        self.assertEqual(cd.text(), "99:59")

    def test_startdauer_wird_begrenzt(self):
        cd, _ = neuer(99999, hoechst=5999)
        self.assertEqual(cd.dauer, 5999)
        cd, _ = neuer(-5)
        self.assertEqual(cd.dauer, 0)

    def test_start_bei_null_tut_nichts(self):
        cd, _ = neuer(0)
        cd.start()
        self.assertEqual(cd.zustand, Zustand.BEREIT)

    def test_plus_minus_waehrend_lauf(self):
        cd, uhr = neuer(60)
        cd.start(); uhr.vor(10)
        cd.aendern(60)
        self.assertEqual(cd.zustand, Zustand.LAEUFT)
        self.assertEqual(cd.text(), "01:50")
        self.assertEqual(cd.dauer, 60)  # eingestellte Dauer bleibt
        uhr.vor(10)
        self.assertEqual(cd.text(), "01:40")
        cd.aendern(-200)
        self.assertEqual(cd.zustand, Zustand.ABGELAUFEN)
        cd.stopp()
        self.assertEqual(cd.text(), "01:00")

    def test_plus_minus_in_pause(self):
        cd, uhr = neuer(60)
        cd.start(); uhr.vor(10); cd.pause()
        cd.aendern(10)
        self.assertEqual(cd.text(), "01:00")
        self.assertEqual(cd.zustand, Zustand.PAUSIERT)
        cd.aendern(-100)
        self.assertEqual(cd.text(), "00:00")
        self.assertEqual(cd.zustand, Zustand.PAUSIERT)
        cd.start()  # Pause bei 0 + Start = fertig
        self.assertEqual(cd.zustand, Zustand.ABGELAUFEN)

    def test_plus_waehrend_lauf_ueber_hoechstwert(self):
        cd, uhr = neuer(5990, hoechst=5999)
        cd.start(); cd.aendern(60)
        self.assertEqual(cd.text(), "99:59")

    def test_neustart_nach_ablauf(self):
        cd, uhr = neuer(5)
        cd.start(); uhr.vor(10)
        self.assertEqual(cd.zustand, Zustand.ABGELAUFEN)
        cd.start()
        self.assertEqual(cd.zustand, Zustand.LAEUFT)
        self.assertEqual(cd.text(), "00:05")

    def test_plus_nach_ablauf_stellt_neu(self):
        cd, uhr = neuer(5)
        cd.start(); uhr.vor(10)
        cd.aendern(10)
        self.assertEqual(cd.zustand, Zustand.BEREIT)
        self.assertEqual(cd.text(), "00:15")

    def test_pause_nach_ablauf_tut_nichts(self):
        cd, uhr = neuer(5)
        cd.start(); uhr.vor(10); cd.pause()
        self.assertEqual(cd.zustand, Zustand.ABGELAUFEN)

    def test_momentaufnahme(self):
        cd, uhr = neuer(65)
        m = cd.momentaufnahme()
        self.assertEqual(m["text"], "01:05")
        self.assertEqual(m["zustand"], "bereit")
        cd.start(); uhr.vor(70)
        self.assertEqual(cd.momentaufnahme()["zustand"], "abgelaufen")

    def test_gleichzeitige_zugriffe(self):
        """Fenster und Webseite greifen gleichzeitig zu – darf nie abstürzen."""
        import time
        cd = Countdown("Countdown", 3, 5999)
        fehler = []
        stopp = threading.Event()

        def lesen():
            try:
                while not stopp.is_set():
                    m = cd.momentaufnahme()
                    assert m["zustand"] in ("bereit", "laeuft", "pausiert", "abgelaufen")
                    assert len(m["text"]) == 5
            except Exception as f:  # pragma: no cover
                fehler.append(f)

        leser = [threading.Thread(target=lesen) for _ in range(4)]
        for t in leser:
            t.start()
        for i in range(3000):
            [cd.start, cd.pause, cd.stopp, lambda: cd.aendern(1), lambda: cd.aendern(-1)][i % 5]()
        time.sleep(0.05)
        stopp.set()
        for t in leser:
            t.join()
        self.assertEqual(fehler, [])


if __name__ == "__main__":
    unittest.main()
