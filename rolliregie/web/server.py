"""Kleine lokale Webseite, die OBS als Browserquelle einbindet.

Läuft in einem eigenen Hintergrund-Thread und ist nur auf diesem PC
erreichbar (127.0.0.1). Seiten:

  /countdown          – die Countdown-Grafik (durchsichtiger Hintergrund)
  /countdown/zustand  – aktueller Stand als JSON (fragt die Seite 5× pro Sekunde ab)

Weitere lokale Titel (z. B. die Uhr in Build 1.1) bekommen hier eigene Seiten.
"""

from __future__ import annotations

import html
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ..titel.countdown import Countdown

VORLAGEN = Path(__file__).resolve().parent

_POSITIONEN = {
    # Position: (waagrecht, senkrecht) als CSS-Flexbox-Werte
    "oben links": ("flex-start", "flex-start"),
    "oben mitte": ("center", "flex-start"),
    "oben rechts": ("flex-end", "flex-start"),
    "mitte links": ("flex-start", "center"),
    "mitte": ("center", "center"),
    "mitte rechts": ("flex-end", "center"),
    "unten links": ("flex-start", "flex-end"),
    "unten mitte": ("center", "flex-end"),
    "unten rechts": ("flex-end", "flex-end"),
}


def _hex_zu_rgba(farbe: str, deckkraft: float) -> str:
    farbe = farbe.lstrip("#")
    r, g, b = (int(farbe[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r}, {g}, {b}, {max(0.0, min(1.0, float(deckkraft)))})"


def countdown_seite(cd_einstellungen) -> str:
    c = cd_einstellungen
    waagrecht, senkrecht = _POSITIONEN.get(str(c.position).strip().lower(), _POSITIONEN["mitte"])
    ersatz = {
        "WAAGRECHT": waagrecht,
        "SENKRECHT": senkrecht,
        "RAND": f"{int(c.randabstand)}px",
        "SCHRIFTART": html.escape(str(c.schriftart), quote=True),
        "SCHRIFTGROESSE": f"{int(c.schriftgroesse)}px",
        "ENDGROESSE": f"{int(c.endtext_schriftgroesse)}px",
        "TEXTFARBE": str(c.textfarbe),
        "HINTERGRUND": _hex_zu_rgba(str(c.hintergrundfarbe), c.hintergrund_deckkraft),
        # "<" maskieren, damit ein Text wie "</script>" die Seite nicht kaputt macht
        "ENDTEXT_JSON": json.dumps(str(c.endtext)).replace("<", "\\u003c"),
    }
    seite = (VORLAGEN / "countdown.html").read_text(encoding="utf-8")
    for schluessel, wert in ersatz.items():
        seite = seite.replace("{{" + schluessel + "}}", wert)
    return seite


class LokaleWebseite:
    def __init__(self, port: int, countdown: Countdown, cd_einstellungen):
        self.port = int(port)
        self.countdown = countdown
        self.cd_einstellungen = cd_einstellungen
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def countdown_adresse(self) -> str:
        return f"http://127.0.0.1:{self.port}/countdown"

    def starten(self) -> None:
        """Startet den Server. Wirft OSError, wenn der Port belegt ist."""
        webseite = self

        class Anfrage(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802 (Name von Python vorgegeben)
                pfad = self.path.split("?", 1)[0].rstrip("/") or "/"
                if pfad == "/countdown":
                    try:
                        inhalt = countdown_seite(webseite.cd_einstellungen).encode("utf-8")
                    except Exception as fehler:  # z. B. falsche Farbe in den Einstellungen
                        self._senden(500, "text/plain; charset=utf-8", str(fehler).encode())
                        return
                    self._senden(200, "text/html; charset=utf-8", inhalt)
                elif pfad == "/countdown/zustand":
                    daten = json.dumps(webseite.countdown.momentaufnahme()).encode("utf-8")
                    self._senden(200, "application/json", daten)
                else:
                    self._senden(404, "text/plain; charset=utf-8", "Nicht gefunden".encode())

            def _senden(self, code: int, art: str, inhalt: bytes) -> None:
                self.send_response(code)
                self.send_header("Content-Type", art)
                self.send_header("Content-Length", str(len(inhalt)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(inhalt)

            def log_message(self, *args):  # keine Ausgabe bei jeder Abfrage
                pass

        self._server = ThreadingHTTPServer(("127.0.0.1", self.port), Anfrage)
        self._server.daemon_threads = True
        self.port = self._server.server_address[1]  # wichtig, falls Port 0 (Tests)
        self._thread = threading.Thread(target=self._server.serve_forever, name="Rolliregie-Webseite", daemon=True)
        self._thread.start()

    def beenden(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
