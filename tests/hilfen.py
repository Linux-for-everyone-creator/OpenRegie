import time

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from openregie import einstellungen
from openregie.obs.zugang import Zugang


def app():
    return QApplication.instance() or QApplication([])


def warte_bis(bedingung, ms=3000) -> bool:
    ende = time.monotonic() + ms / 1000
    while time.monotonic() < ende:
        QCoreApplication.processEvents()
        if bedingung():
            return True
        time.sleep(0.005)
    QCoreApplication.processEvents()
    return bool(bedingung())


def warte(ms):
    warte_bis(lambda: False, ms)


def obs_einstellungen(**aenderungen):
    E = einstellungen.lade()
    werte = E.obs.als_dict()
    werte.update({"adresse": "127.0.0.1", "neu_verbinden_sekunden": 0.2})
    werte.update(aenderungen)
    return einstellungen.Bereich("obs", werte), E


def zugang(port, passwort="geheim"):
    return lambda: Zugang(port=port, passwort=passwort, passwort_noetig=True, server_an=True)
