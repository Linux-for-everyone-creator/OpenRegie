"""Nachgeahmtes Overlays.uno und Twitch für die Tests.

Ein kleiner Webserver auf diesem PC, der so antwortet wie die echten Dienste.
So lässt sich alles prüfen, ohne Internet und ohne echtes Konto.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

UNO_TOKEN = "TESTtoken_123abc"
UNO_ADRESSE_TEXT = f"https://app.overlays.uno/apiv2/controlapps/{UNO_TOKEN}/api"
# Einzel-Uno (z. B. ein einzelnes „Countdown | Circles“): kennt kein GetOverlays
EINZEL_TOKEN = "EINZELtoken_456def"
EINZEL_ADRESSE_TEXT = f"https://app.overlays.uno/apiv2/controlapps/{EINZEL_TOKEN}/api"


class FalschesInternet:
    def __init__(self):
        self.lock = threading.Lock()
        self.anfragen: list[tuple[str, str, object]] = []  # (methode, pfad, inhalt)
        self.verzoegerung = 0.0
        self.aus = False  # True = „kein Internet“ (Verbindung wird sofort geschlossen)

        # --- Uno ---------------------------------------------------------
        self.uno_tokens = {UNO_TOKEN}
        self.einzel_tokens = {EINZEL_TOKEN}
        self.einzel = {"visible": False, "inhalt": {"Titel": "Gleich geht's los"}}
        self.einzel_befehle: list[dict] = []  # was beim Einzel-Uno ankam
        self.uno_mit_sichtbarkeit = True
        self.uno_kaputt = False  # True = Uno antwortet mit Fehler 500
        self.overlays = [
            {"id": "ov-1", "name": "Bauchbinde", "visible": False},
            {"id": "ov-2", "name": "News-Ticker", "visible": True},
            {"id": "ov-3", "name": "Countdown", "visible": False},
        ]
        self.inhalte = {
            "ov-1": {"Name": "Kevin", "Titel": "Live aus dem Studio", "Farbe": "#FF0000",
                     "Logo": "https://example.com/logo.png", "Zeigen": True},
            "ov-2": {"Ticker Text": "Willkommen im Stream!"},
            "ov-3": {"Minuten": 5},
        }

        # --- Twitch --------------------------------------------------------
        self.client_id = "testclient"
        self.bestaetigt = False  # Kevin hat im Browser auf „Autorisieren“ geklickt
        self.abgelehnt = False
        self.gueltige_tokens = set()
        self.gueltige_erneuerungen = set()
        self.titel = "Alter Titel"
        self._nummer = 0
        self.code_intervall = 1

        server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler_klasse())
        server.daemon_threads = True
        self.server = server
        self.port = server.server_address[1]
        self.adresse = f"http://127.0.0.1:{self.port}"
        threading.Thread(target=server.serve_forever, daemon=True).start()

    def beenden(self):
        self.server.shutdown()
        self.server.server_close()

    def anzahl(self, befehl: str) -> int:
        with self.lock:
            return sum(1 for _m, _p, d in self.anfragen if isinstance(d, dict) and d.get("command") == befehl)

    def neues_token(self) -> tuple[str, str]:
        with self.lock:
            self._nummer += 1
            token, erneuerung = f"tok{self._nummer}", f"ern{self._nummer}"
            self.gueltige_tokens.add(token)
            self.gueltige_erneuerungen.add(erneuerung)
        return token, erneuerung

    # ------------------------------------------------------------------
    def _handler_klasse(self):
        netz = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def _antwort(self, code, daten=None):
                roh = b"" if daten is None else json.dumps(daten).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(roh)))
                self.end_headers()
                try:
                    self.wfile.write(roh)
                except (BrokenPipeError, ConnectionResetError):
                    pass  # OpenRegie hat schon aufgegeben (z. B. beim Beenden)

            def _inhalt(self):
                laenge = int(self.headers.get("Content-Length") or 0)
                roh = self.rfile.read(laenge).decode() if laenge else ""
                if "json" in (self.headers.get("Content-Type") or ""):
                    return json.loads(roh) if roh else None
                return {k: v[0] for k, v in parse_qs(roh).items()}

            def _bearbeiten(self, methode):
                inhalt = self._inhalt()
                with netz.lock:
                    netz.anfragen.append((methode, self.path, inhalt))
                if netz.verzoegerung:
                    time.sleep(netz.verzoegerung)
                if netz.aus:
                    self.close_connection = True
                    self.connection.close()
                    return
                pfad = urlparse(self.path)
                if pfad.path.startswith("/apiv2/controlapps/"):
                    return self._uno(methode, pfad.path, inhalt)
                return self._twitch(methode, pfad, inhalt)

            do_GET = lambda self: self._bearbeiten("GET")
            do_PUT = lambda self: self._bearbeiten("PUT")
            do_POST = lambda self: self._bearbeiten("POST")
            do_PATCH = lambda self: self._bearbeiten("PATCH")

            # --- Uno -------------------------------------------------------
            def _uno(self, methode, pfad, d):
                teile = pfad.split("/")  # ['', 'apiv2', 'controlapps', TOKEN, 'api']
                bekannt = netz.uno_tokens | netz.einzel_tokens
                if methode != "PUT" or len(teile) < 5 or teile[3] not in bekannt:
                    # so antwortet das echte Uno auf einen unbekannten Schlüssel
                    return self._antwort(404, {"error": {"message": "API Not Found", "code": 404}})
                if netz.uno_kaputt:
                    return self._antwort(500, {"error": {"message": "Server Error", "code": 500}})
                befehl = (d or {}).get("command")
                ok = lambda payload: self._antwort(200, {"status": 200, "result": "ok", "payload": payload})
                if teile[3] in netz.einzel_tokens:
                    return self._einzel_uno(befehl, d or {}, ok)
                if befehl == "GetOverlays":
                    with netz.lock:
                        liste = [dict(o) for o in netz.overlays]
                    if not netz.uno_mit_sichtbarkeit:
                        for o in liste:
                            o.pop("visible", None)
                    return ok(liste)
                overlay = next((o for o in netz.overlays if o["id"] == d.get("id")), None)
                if overlay is None:
                    return self._antwort(404, {"error": {"message": "Overlay Not Found", "code": 404}})
                if befehl in ("ShowOverlay", "HideOverlay"):
                    overlay["visible"] = befehl == "ShowOverlay"
                    return ok(overlay["visible"])
                if befehl == "GetOverlayContent":
                    return ok(dict(netz.inhalte.get(overlay["id"], {})))
                if befehl == "SetOverlayContentField":
                    netz.inhalte.setdefault(overlay["id"], {})[d["fieldId"]] = d["value"]
                    return ok(True)
                return self._antwort(400, {"error": {"message": "Unknown command", "code": 400}})

            def _einzel_uno(self, befehl, d, ok):
                with netz.lock:
                    netz.einzel_befehle.append(dict(d))
                e = netz.einzel
                if befehl in ("ShowOverlay", "HideOverlay"):
                    e["visible"] = befehl == "ShowOverlay"
                    return ok(e["visible"])
                if befehl == "GetOverlayContent":
                    return ok(dict(e["inhalt"]))
                if befehl == "SetOverlayContentField":
                    e["inhalt"][d["fieldId"]] = d["value"]
                    return ok(True)
                # so antwortet das echte Einzel-Uno auf „GetOverlays“ (HTTP 400)
                return self._antwort(400, {"error": {"message": f"Invalid command: {befehl}", "code": 400}})

            # --- Twitch ----------------------------------------------------
            def _twitch(self, methode, pfad, d):
                p = pfad.path
                if p == "/oauth2/device":
                    if (d or {}).get("client_id") != netz.client_id:
                        return self._antwort(400, {"status": 400, "message": "invalid client"})
                    return self._antwort(200, {"device_code": "geraet1", "user_code": "ABCD-EFGH",
                                               "verification_uri": "https://www.twitch.tv/activate?device-code=ABCDEFGH",
                                               "expires_in": 1800, "interval": netz.code_intervall})
                if p == "/oauth2/token":
                    art = d.get("grant_type")
                    if "client_secret" in d:
                        return self._antwort(400, {"message": "no secret expected in test"})
                    if art.endswith("device_code"):
                        if netz.abgelehnt:
                            return self._antwort(400, {"status": 400, "message": "access_denied"})
                        if not netz.bestaetigt:
                            return self._antwort(400, {"status": 400, "message": "authorization_pending"})
                        token, erneuerung = netz.neues_token()
                        return self._antwort(200, {"access_token": token, "refresh_token": erneuerung,
                                                   "expires_in": 14000, "token_type": "bearer"})
                    if art == "refresh_token":
                        if d.get("refresh_token") not in netz.gueltige_erneuerungen:
                            return self._antwort(400, {"status": 400, "message": "Invalid refresh token"})
                        netz.gueltige_erneuerungen.discard(d["refresh_token"])
                        token, erneuerung = netz.neues_token()
                        return self._antwort(200, {"access_token": token, "refresh_token": erneuerung})
                if p == "/oauth2/validate":
                    token = (self.headers.get("Authorization") or "").removeprefix("OAuth ")
                    if token not in netz.gueltige_tokens:
                        return self._antwort(401, {"status": 401, "message": "invalid access token"})
                    return self._antwort(200, {"client_id": netz.client_id, "login": "kevin_test",
                                               "user_id": "4711", "scopes": ["channel:manage:broadcast"]})
                if p == "/oauth2/revoke":
                    netz.gueltige_tokens.discard(d.get("token"))
                    return self._antwort(200)
                if p.startswith("/helix/"):
                    token = (self.headers.get("Authorization") or "").removeprefix("Bearer ")
                    if token not in netz.gueltige_tokens or self.headers.get("Client-Id") != netz.client_id:
                        return self._antwort(401, {"status": 401, "message": "Invalid OAuth token"})
                    if p == "/helix/users":
                        return self._antwort(200, {"data": [{"id": "4711", "display_name": "KevinTest"}]})
                    if p == "/helix/channels":
                        if parse_qs(pfad.query).get("broadcaster_id") != ["4711"]:
                            return self._antwort(400, {"message": "wrong broadcaster"})
                        if methode == "GET":
                            return self._antwort(200, {"data": [{"broadcaster_id": "4711", "title": netz.titel}]})
                        if methode == "PATCH":
                            netz.titel = d["title"]
                            return self._antwort(204)
                return self._antwort(404, {"message": "not found"})

        return Handler
