"""Kleine Hilfe für Internet-Anfragen (Overlays.uno, Twitch).

Alles läuft im Hintergrund (das Fenster friert nicht ein). Der Rückruf kommt immer
genau einmal: rueckruf(http_code, antwort_als_json_oder_None, fehlertext).
http_code ist 0, wenn gar keine Verbindung zustande kam.
"""

from __future__ import annotations

import json
import logging
from typing import Callable
from urllib.parse import urlencode

from PySide6.QtCore import QByteArray, QCoreApplication, QObject, QTimer, QUrl
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

log = logging.getLogger("openregie.netz")

NetzRueckruf = Callable[[int, object, str], None]
ZEITLIMIT_MS = 15000


_gemeinsamer_manager: QNetworkAccessManager | None = None


def _manager() -> QNetworkAccessManager:
    """Ein einziger Netz-Manager für das ganze Programm. Er lebt so lange wie OpenRegie –
    wird er vorher gelöscht, während noch Antworten unterwegs sind, stürzt Qt ab."""
    global _gemeinsamer_manager
    if _gemeinsamer_manager is None:
        _gemeinsamer_manager = QNetworkAccessManager(QCoreApplication.instance())
    return _gemeinsamer_manager


class Netz(QObject):
    def __init__(self, parent=None, zeitlimit_ms: int = ZEITLIMIT_MS):
        super().__init__(parent)
        self._manager = _manager()
        self._zeitlimit_ms = zeitlimit_ms
        self._offen: set[QNetworkReply] = set()

    def anfrage(self, methode: str, adresse: str, rueckruf: NetzRueckruf, *, json_daten=None,
                formular: dict | None = None, kopfzeilen: dict | None = None) -> None:
        anfrage = QNetworkRequest(QUrl(adresse))
        anfrage.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                             QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy)
        inhalt = QByteArray()
        if json_daten is not None:
            anfrage.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
            inhalt = QByteArray(json.dumps(json_daten).encode("utf-8"))
        elif formular is not None:
            anfrage.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/x-www-form-urlencoded")
            inhalt = QByteArray(urlencode(formular).encode("utf-8"))
        for name, wert in (kopfzeilen or {}).items():
            anfrage.setRawHeader(name.encode(), str(wert).encode())

        antwort = self._manager.sendCustomRequest(anfrage, methode.upper().encode(), inhalt)
        self._offen.add(antwort)
        uhr = QTimer(antwort)
        uhr.setSingleShot(True)
        uhr.timeout.connect(antwort.abort)
        uhr.start(self._zeitlimit_ms)
        antwort.finished.connect(lambda a=antwort: self._fertig(a, rueckruf))

    def _fertig(self, antwort: QNetworkReply, rueckruf: NetzRueckruf) -> None:
        self._offen.discard(antwort)
        code = antwort.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute) or 0
        roh = bytes(antwort.readAll())
        fehler = ""
        if antwort.error() != QNetworkReply.NetworkError.NoError and not code:
            fehler = antwort.errorString()
        antwort.deleteLater()
        daten = None
        if roh:
            try:
                daten = json.loads(roh)
            except ValueError:
                daten = None
        try:
            rueckruf(int(code), daten, fehler)
        except Exception:
            log.exception("Fehler beim Verarbeiten einer Antwort aus dem Internet")

    def alle_abbrechen(self) -> None:
        """Beim Beenden: alles Offene abbrechen, ohne dass noch Rückrufe kommen."""
        for antwort in list(self._offen):
            self._offen.discard(antwort)
            try:
                antwort.finished.disconnect()
            except (RuntimeError, TypeError):
                pass
            antwort.abort()
            antwort.deleteLater()
