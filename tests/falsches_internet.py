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

# kleines gültiges PNG (2×2 Pixel, gelb) als Vorschaubild
VORSCHAU_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000002000000020802000000fdd49a73000000097048597300000ec400000ec4"
    "01952b0e1b0000001249444154089963fcb4c19481818189010c0016fb01db022b8dd50000000049454e44ae426082")
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
        self.einzel = FalschesSingular()
        self.einzel_befehle: list[dict] = []  # was beim Einzel-Uno ankam (…/api und PATCH)
        self.uno_mit_sichtbarkeit = True
        self.uno_kaputt = False  # True = Uno antwortet mit Fehler 500
        self.unbekannte_befehle: set[str] = set()  # diese …/api-Befehle lehnt Uno mit 400 „Invalid command“ ab
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
        self.einzel.vorschau_adresse = f"{self.adresse}/bild/vorschau.png"
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
                if pfad.path == "/bild/vorschau.png":
                    self.send_response(200)
                    self.send_header("Content-Type", "image/png")
                    self.send_header("Content-Length", str(len(VORSCHAU_PNG)))
                    self.end_headers()
                    self.wfile.write(VORSCHAU_PNG)
                    return
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
                if netz.uno_kaputt and len(teile) >= 4 and teile[3] in bekannt:
                    return self._antwort(500, {"error": {"message": "Server Error", "code": 500}})
                if len(teile) >= 4 and teile[3] in netz.einzel_tokens and not (len(teile) >= 5 and teile[4] == "api"):
                    return self._singular(methode, teile[4] if len(teile) >= 5 else "", d)
                if methode != "PUT" or len(teile) < 5 or teile[3] not in bekannt:
                    # so antwortet das echte Uno auf einen unbekannten Schlüssel
                    return self._antwort(404, {"error": {"message": "API Not Found", "code": 404}})
                if netz.uno_kaputt:
                    return self._antwort(500, {"error": {"message": "Server Error", "code": 500}})
                befehl = (d or {}).get("command")
                ok = lambda payload: self._antwort(200, {"status": 200, "result": "ok", "payload": payload})
                if befehl in netz.unbekannte_befehle:
                    return self._antwort(400, {"error": {"message": f"Invalid command: {befehl}", "code": 400}})
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
                """…/api bei einem Einzel-Uno – genau wie beim echten getestet."""
                with netz.lock:
                    netz.einzel_befehle.append(dict(d))
                if befehl in ("ShowOverlay", "HideOverlay"):
                    # Das echte Einzel-Uno sagt „ok“, zeigt aber NICHTS an.
                    return ok(befehl == "ShowOverlay")
                # alle anderen (auch GetOverlays, GetOverlayContent): HTTP 400
                return self._antwort(400, {"error": {"message": f"Invalid command: {befehl}", "code": 400}})

            def _singular(self, methode, pfad, d):
                """Singular-Schnittstelle des Einzel-Unos: GET /, /model, /control und PATCH /control."""
                e = netz.einzel
                with netz.lock:
                    if methode == "GET" and pfad == "":
                        return self._antwort(200, e.info())
                    if methode == "GET" and pfad == "model":
                        return self._antwort(200, e.model())
                    if methode == "GET" and pfad == "control":
                        return self._antwort(200, e.control())
                    if methode == "PATCH" and pfad == "control":
                        netz.einzel_befehle.append({"PATCH": d})
                        if not e.patch(d):
                            return self._antwort(400, {"error": {"message": "Bad request", "code": 400}})
                        return self._antwort(200, {"success": True})
                return self._antwort(404, {"error": {"message": "API Not Found", "code": 404}})

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


# ---------------------------------------------------------------------------
HAUPT, CONTENT, COUNTDOWN, MESSAGE = "-Haupt1", "teil-content", "teil-countdown", "teil-message"


class FalschesSingular:
    """Ein Einzel-Uno „Countdown | Circles“, aufgebaut wie das echte (Stand 14.11.2026).

    Komplett sichtbar ist es nur, wenn Hauptteil, Content und Countdown auf „In“ stehen
    UND „Active“ an ist – sonst sieht man nur den Kreis ohne Zahlen (wie beim echten).
    """

    def __init__(self):
        self.jetzt = None  # für Tests: feste Uhrzeit in ms (None = echte Uhr)
        self.vorschau_adresse = "//image.example/vorschau.jpg"  # wie beim echten: ohne „https:“
        self.name = "Countdown | Circles"
        self.zustand = {HAUPT: "Out1", CONTENT: "Out1", COUNTDOWN: "Out1", MESSAGE: "Out1"}
        self.werte = {
            HAUPT: {"Active": False, "Color": {"r": 42, "g": 42, "b": 42, "a": 1}, "Text": "#ffffff",
                    "Image": "https://assets.example/bild.svg"},
            CONTENT: {"BeginTime": 300, "Message": "COUNTDOWN END MESSAGE", "ShowOverlay": True,
                      "Timer": {"value": 0, "UTC": 0, "isRunning": False}, "UseMessage": True},
            COUNTDOWN: {}, MESSAGE: {},
        }

    def uhr(self) -> int:
        return int(self.jetzt if self.jetzt is not None else time.time() * 1000)

    # --- was man sieht ------------------------------------------------------
    def komplett_sichtbar(self) -> bool:
        return (all(self.zustand[t] == "In" for t in (HAUPT, CONTENT, COUNTDOWN))
                and self.werte[HAUPT]["Active"] is True)

    def ganz_aus(self) -> bool:
        return all(z != "In" for z in self.zustand.values()) and self.werte[HAUPT]["Active"] is False

    def restzeit_s(self) -> float:
        t = self.werte[CONTENT]["Timer"]
        abgelaufen = t["value"] + ((self.uhr() - t["UTC"]) if t["isRunning"] else 0)
        return self.werte[CONTENT]["BeginTime"] - abgelaufen / 1000

    # --- Antworten ----------------------------------------------------------
    def info(self):
        return {"id": 1, "type": "controlapp", "name": self.name,
                "thumbnail": self.vorschau_adresse,
                "outputUrl": "https://controlapi.example/output/AUSGABE/Output?aspect=16:9"}

    def model(self):
        feld = lambda i, art, std=None: {"id": i, "title": i, "type": art, "defaultValue": std}
        return [{"id": HAUPT, "name": "default",
                 "model": [feld("Image", "image"), feld("Color", "color"), feld("Text", "color"),
                           feld("Active", "checkbox", True)],
                 "subcompositions": [{
                     "id": CONTENT, "name": "Content", "state": "In",
                     "model": [feld("BeginTime", "number", "0"), feld("Timer", "timecontrol"),
                               feld("UseMessage", "checkbox", True), feld("Message", "text", "End"),
                               feld("ShowOverlay", "checkbox", True)],
                     "subcompositions": [
                         {"id": COUNTDOWN, "name": "Countdown", "state": "In", "model": [], "subcompositions": []},
                         {"id": MESSAGE, "name": "Message", "state": "Out", "model": [], "subcompositions": []}]}]}]

    def control(self):
        namen = {HAUPT: "mainComposition", CONTENT: "Content", COUNTDOWN: "Countdown", MESSAGE: "Message"}
        return [{"subCompositionId": t, "subCompositionName": namen[t], "mainComposition": t == HAUPT,
                 "state": self.zustand[t], "payload": json.loads(json.dumps(self.werte[t]))} for t in namen]

    def patch(self, liste) -> bool:
        namen = {"mainComposition": HAUPT, "Content": CONTENT, "Countdown": COUNTDOWN, "Message": MESSAGE}
        if not isinstance(liste, list):
            return False
        for eintrag in liste:
            teil = eintrag.get("subCompositionId") or namen.get(eintrag.get("subCompositionName"))
            if teil not in self.zustand:
                return False
            if "state" in eintrag:
                # wie beim echten: „Out“ wird als „Out2“ gespeichert
                self.zustand[teil] = "In" if eintrag["state"] == "In" else "Out2"
            for feld, wert in (eintrag.get("payload") or {}).items():
                if isinstance(wert, dict) and "command" in wert:
                    self._timer(teil, feld, wert["command"])
                else:
                    self.werte[teil][feld] = wert
        return True

    def _timer(self, teil, feld, befehl):
        t = self.werte[teil][feld]
        jetzt = self.uhr()
        if befehl in ("play", "start") and not t["isRunning"]:
            t.update(UTC=jetzt, isRunning=True)
        elif befehl == "pause" and t["isRunning"]:
            t.update(value=t["value"] + (jetzt - t["UTC"]), UTC=jetzt, isRunning=False)
        elif befehl == "reset":
            t.update(value=0, UTC=jetzt, isRunning=False)
