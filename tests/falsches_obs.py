"""Ein nachgeahmtes OBS für die Tests.

Spricht das echte OBS-WebSocket-Protokoll (Version 5) mit Passwort-Prüfung,
merkt sich Szenen und Quellen und kann Ereignisse (z. B. „Stream gestartet“)
verschicken. So lässt sich alles prüfen, ohne dass OBS laufen muss.
"""

from __future__ import annotations

import base64
import json

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QObject
from PySide6.QtGui import QColor, QImage
from PySide6.QtNetwork import QHostAddress
from PySide6.QtWebSockets import QWebSocketProtocol, QWebSocketServer

from openregie.obs.verbindung import anmeldeschluessel

SALZ = "salzSALZ123"
AUFGABE = "aufgabe456"


def testbild_daten(breite=320, hoehe=180) -> str:
    bild = QImage(breite, hoehe, QImage.Format.Format_RGB32)
    bild.fill(QColor("#336699"))
    puffer = QBuffer()
    puffer.open(QIODevice.OpenModeFlag.WriteOnly)
    bild.save(puffer, "JPG")
    return "data:image/jpg;base64," + base64.b64encode(bytes(puffer.data())).decode()


class FalschesObs(QObject):
    def __init__(self, passwort: str | None = "geheim", rpc_version: int = 1):
        super().__init__()
        self.passwort = passwort
        self.rpc_version = rpc_version
        self.server = QWebSocketServer("FalschesObs", QWebSocketServer.SslMode.NonSecureMode)
        assert self.server.listen(QHostAddress.SpecialAddress.LocalHost, 0)
        self.port = self.server.serverPort()
        self.server.newConnection.connect(self._neu)
        self.clients = []
        self.anfragen: list[tuple[str, dict]] = []
        self.identify_daten: dict | None = None
        self.antworte = True  # False = OBS „hängt“
        self.ohne_begruessung = False

        # „Zustand“ des nachgeahmten OBS
        self.stream_aktiv = False
        self.szene = "Szene 1"
        self.szenen = {"Szene 1": [], "Pause": []}  # Szene -> Liste von (id, quellenname, an)
        self.quellen: dict[str, dict] = {}  # name -> {"kind":..., "settings":...}
        # wie das echte OBS 33 unter Wayland (Fensteraufnahme geht dort über die Bildschirmaufnahme)
        self.arten = ["browser_source", "image_source", "color_source_v3", "v4l2_input", "slideshow_v2",
                      "pipewire-screen-capture-source", "pulse_input_capture", "text_ft2_source_v2"]
        # wie Kevins Logitech BRIO: zuerst die Infrarot-Kamera (nur nachgebildete Formate), dann die echte
        self.geraete = [{"itemName": "Logitech BRIO", "itemValue": "/dev/video2", "itemEnabled": True},
                        {"itemName": "Logitech BRIO", "itemValue": "/dev/video0", "itemEnabled": True}]
        self.formate = {"/dev/video2": ["BGR3 (Emulated)", "YU12 (Emulated)"],
                        "/dev/video0": ["YUYV 4:2:2", "Motion-JPEG", "BGR3 (Emulated)"]}
        self.naechste_id = 1
        self.transform: dict[int, dict] = {}
        self.bild = testbild_daten()
        self.sammlung = "Unbenannt"
        self.umsortiert = 0  # wie oft SetSceneItemIndex kam
        self.sammlungen = ["Unbenannt", "Show"]

    # ------------------------------------------------------------------
    def _neu(self):
        while self.server.hasPendingConnections():
            client = self.server.nextPendingConnection()
            self.clients.append(client)
            client.textMessageReceived.connect(lambda text, c=client: self._nachricht(c, text))
            client.disconnected.connect(lambda c=client: self.clients.remove(c) if c in self.clients else None)
            if not self.ohne_begruessung:
                hallo = {"obsWebSocketVersion": "5.5.0", "rpcVersion": self.rpc_version}
                if self.passwort is not None:
                    hallo["authentication"] = {"challenge": AUFGABE, "salt": SALZ}
                self._senden(client, 0, hallo)

    def _senden(self, client, op, d):
        client.sendTextMessage(json.dumps({"op": op, "d": d}))

    def _nachricht(self, client, text):
        n = json.loads(text)
        op, d = n["op"], n["d"]
        if op == 1:
            self.identify_daten = d
            if d.get("rpcVersion") != self.rpc_version:
                client.close(QWebSocketProtocol.CloseCode(4010), "UnsupportedRpcVersion")
                return
            if self.passwort is not None:
                erwartet = anmeldeschluessel(self.passwort, SALZ, AUFGABE)
                if d.get("authentication") != erwartet:
                    client.close(QWebSocketProtocol.CloseCode(4009), "AuthenticationFailed")
                    return
            self._senden(client, 2, {"negotiatedRpcVersion": 1})
        elif op == 6:
            typ, kennung = d["requestType"], d["requestId"]
            daten = d.get("requestData") or {}
            self.anfragen.append((typ, daten))
            if not self.antworte:
                return
            ok, code, kommentar, antwort = self._bearbeiten(typ, daten)
            status = {"result": ok, "code": code}
            if kommentar:
                status["comment"] = kommentar
            nachricht = {"requestType": typ, "requestId": kennung, "requestStatus": status}
            if antwort is not None:
                nachricht["responseData"] = antwort
            self._senden(client, 7, nachricht)

    def _bearbeiten(self, typ, d):
        OK = (True, 100, None)
        if typ == "GetStreamStatus":
            return (*OK, {"outputActive": self.stream_aktiv, "outputReconnecting": False})
        if typ == "GetCurrentProgramScene":
            return (*OK, {"sceneName": self.szene, "currentProgramSceneName": self.szene})
        if typ == "GetSourceScreenshot":
            if d.get("sourceName") not in self.szenen and d.get("sourceName") not in self.quellen:
                return (False, 600, "No source was found by the name of `x`.", None)
            return (*OK, {"imageData": self.bild})
        if typ == "SetCurrentProgramScene":
            if d.get("sceneName") not in self.szenen:
                return (False, 600, "No scene", None)
            self.szene_wechseln(d["sceneName"])
            return (*OK, None)
        if typ == "CreateScene":
            if d["sceneName"] in self.szenen or d["sceneName"] in self.quellen:
                return (False, 601, "A source already exists by that scene name.", None)
            self.szene_anlegen(d["sceneName"])
            return (*OK, {"sceneUuid": "s"})
        if typ == "RemoveScene":
            if d["sceneName"] not in self.szenen:
                return (False, 600, "No scene", None)
            del self.szenen[d["sceneName"]]
            if self.szene == d["sceneName"]:
                self.szene_wechseln(next(iter(self.szenen)))
            self.ereignis("SceneRemoved", {"sceneName": d["sceneName"]})
            return (*OK, None)
        if typ == "SetSceneName":
            alt, neu = d["sceneName"], d["newSceneName"]
            if alt not in self.szenen:
                return (False, 600, "No scene", None)
            if neu in self.szenen or neu in self.quellen:
                return (False, 601, "A source already exists by that new scene name.", None)
            self.szenen = {(neu if k == alt else k): v for k, v in self.szenen.items()}
            if self.szene == alt:
                self.szene = neu
            self.ereignis("SceneNameChanged", {"oldSceneName": alt, "sceneName": neu})
            return (*OK, None)
        if typ == "SetInputName":
            alt, neu = d["inputName"], d["newInputName"]
            if alt not in self.quellen:
                return (False, 600, "No source", None)
            if neu in self.szenen or neu in self.quellen:
                return (False, 601, "A source already exists by that new input name.", None)
            self.quellen = {(neu if k == alt else k): v for k, v in self.quellen.items()}
            for szene in self.szenen:
                self.szenen[szene] = [(k, neu if n == alt else n, an) for k, n, an in self.szenen[szene]]
            self.ereignis("InputNameChanged", {"oldInputName": alt, "inputName": neu})
            return (*OK, None)
        if typ == "RemoveSceneItem":
            liste = self.szenen.get(d["sceneName"])
            if liste is None or not any(e[0] == d["sceneItemId"] for e in liste):
                return (False, 600, "No scene item", None)
            self.szenen[d["sceneName"]] = [e for e in liste if e[0] != d["sceneItemId"]]
            self.ereignis("SceneItemRemoved", {"sceneName": d["sceneName"], "sceneItemId": d["sceneItemId"]})
            return (*OK, None)
        if typ == "GetInputPropertiesListPropertyItems":
            if d.get("inputName") not in self.quellen:
                return (False, 600, "No source", None)
            if d.get("propertyName") == "pixelformat":
                geraet = self.quellen[d["inputName"]]["settings"].get("device_id")
                return (*OK, {"propertyItems": [{"itemName": n, "itemValue": i, "itemEnabled": True}
                                                for i, n in enumerate(self.formate.get(geraet, []))]})
            return (*OK, {"propertyItems": list(self.geraete) if d.get("propertyName") == "device_id" else []})
        if typ == "SetSceneItemIndex" and d.get("sceneName") not in self.szenen:
            return (False, 600, "No scene", None)
        if typ == "GetSceneCollectionList":
            return (*OK, {"currentSceneCollectionName": self.sammlung, "sceneCollections": list(self.sammlungen)})
        if typ == "SetCurrentSceneCollection":
            if d.get("sceneCollectionName") not in self.sammlungen:
                return (False, 600, "No scene collection", None)
            self.sammlung = d["sceneCollectionName"]
            return (*OK, None)
        if typ == "StopStream":
            self.stream_stoppen()
            return (*OK, None)
        if typ == "GetSceneList":
            return (*OK, {"currentProgramSceneName": self.szene,
                          "scenes": [{"sceneName": n, "sceneIndex": i} for i, n in enumerate(self.szenen)]})
        if typ == "GetInputList":
            art = d.get("inputKind")
            return (*OK, {"inputs": [{"inputName": n, "inputKind": q["kind"]} for n, q in self.quellen.items()
                                     if not art or q["kind"] == art]})
        if typ == "RemoveInput":
            if d["inputName"] not in self.quellen:
                return (False, 600, "No source", None)
            del self.quellen[d["inputName"]]
            for szene in self.szenen:
                self.szenen[szene] = [e for e in self.szenen[szene] if e[1] != d["inputName"]]
            self.ereignis("InputRemoved", {"inputName": d["inputName"]})
            return (*OK, None)
        if typ == "GetSceneItemList":
            if d.get("sceneName") not in self.szenen:
                return (False, 600, "No scene", None)
            return (*OK, {"sceneItems": [
                {"sceneItemId": k, "sourceName": n, "sceneItemIndex": i, "sceneItemEnabled": an,
                 "inputKind": self.quellen.get(n, {}).get("kind")}
                for i, (k, n, an) in enumerate(self.szenen[d["sceneName"]])]})
        if typ == "SetSceneItemIndex":
            liste = self.szenen[d["sceneName"]]
            eintrag = next(e for e in liste if e[0] == d["sceneItemId"])
            liste.remove(eintrag)
            liste.insert(min(int(d["sceneItemIndex"]), len(liste)), eintrag)
            self.umsortiert += 1
            self.ereignis("SceneItemListReindexed", {"sceneName": d["sceneName"]})
            return (*OK, None)
        if typ == "GetInputKindList":
            if d.get("unversioned"):  # wie OBS: ohne Versionsnummer, z. B. color_source statt color_source_v3
                import re as _re
                return (*OK, {"inputKinds": [_re.sub(r"_v\d+$", "", a) for a in self.arten]})
            return (*OK, {"inputKinds": list(self.arten)})
        if typ == "GetVideoSettings":
            return (*OK, {"baseWidth": 1280, "baseHeight": 720, "outputWidth": 1280, "outputHeight": 720})
        if typ == "GetInputSettings":
            q = self.quellen.get(d["inputName"])
            if not q:
                return (False, 600, "No source was found by the name of `x`.", None)
            return (*OK, {"inputKind": q["kind"], "inputSettings": q["settings"]})
        if typ == "CreateInput":
            if d["inputKind"] not in self.arten:  # wie OBS: nur mit Versionsnummer, z. B. color_source_v3
                return (False, 400, "Your specified input kind is not supported by OBS. Check that your "
                                    "specified kind is properly versioned and that any necessary plugins are loaded.",
                        None)
            if d["inputName"] in self.quellen:
                return (False, 601, "A source already exists by that input name.", None)
            if d["sceneName"] not in self.szenen:
                return (False, 600, "No scene", None)
            self.quellen[d["inputName"]] = {"kind": d["inputKind"], "settings": dict(d.get("inputSettings", {}))}
            kennung = self._in_szene(d["sceneName"], d["inputName"], d.get("sceneItemEnabled", True))
            self.ereignis("InputCreated", {"inputName": d["inputName"]})
            return (*OK, {"inputUuid": "u", "sceneItemId": kennung})
        if typ == "SetInputSettings":
            q = self.quellen.get(d["inputName"])
            if not q:
                return (False, 600, "No source", None)
            q["settings"].update(d["inputSettings"])
            return (*OK, None)
        if typ == "PressInputPropertiesButton":
            return (*OK, None)
        if typ == "GetSceneItemId":
            for kennung, name, _an in self.szenen.get(d["sceneName"], []):
                if name == d["sourceName"]:
                    return (*OK, {"sceneItemId": kennung})
            return (False, 600, "No scene items were found", None)
        if typ == "CreateSceneItem":
            if d.get("sceneName") not in self.szenen or (d.get("sourceName") not in self.quellen
                                                         and d.get("sourceName") not in self.szenen):
                return (False, 600, "No scene or source", None)
            kennung = self._in_szene(d["sceneName"], d["sourceName"], d.get("sceneItemEnabled", True))
            return (*OK, {"sceneItemId": kennung})
        if typ == "SetSceneItemEnabled":
            liste = self.szenen[d["sceneName"]]
            for i, (kennung, name, _an) in enumerate(liste):
                if kennung == d["sceneItemId"]:
                    liste[i] = (kennung, name, d["sceneItemEnabled"])
            return (*OK, None)
        if typ == "SetSceneItemTransform":
            self.transform[d["sceneItemId"]] = d["sceneItemTransform"]
            return (*OK, None)
        return (False, 204, "Unknown request type", None)

    def _in_szene(self, szene, quelle, an):
        """Neue Quellen kommen wie in OBS ganz nach oben (Ende der Liste)."""
        kennung = self.naechste_id
        self.naechste_id += 1
        self.szenen[szene].append((kennung, quelle, an))
        self.ereignis("SceneItemCreated", {"sceneName": szene, "sourceName": quelle, "sceneItemId": kennung})
        return kennung

    # --- Hilfen für Tests: Quellen von Hand anlegen (wie in OBS geklickt) ----
    def quelle_anlegen(self, szene, name, art, einstellungen=None):
        if name not in self.quellen:
            self.quellen[name] = {"kind": art, "settings": dict(einstellungen or {})}
        return self._in_szene(szene, name, True)

    def reihenfolge(self, szene) -> list[str]:
        """Namen von unten nach oben."""
        return [n for _k, n, _an in self.szenen[szene]]

    def szene_anlegen(self, name):
        self.szenen[name] = []
        self.ereignis("SceneCreated", {"sceneName": name, "isGroup": False})

    # --- Steuerung aus dem Test -------------------------------------------
    def ereignis(self, typ, daten):
        for c in list(self.clients):
            self._senden(c, 5, {"eventType": typ, "eventIntent": 1, "eventData": daten})

    def stream_starten(self):
        self.ereignis("StreamStateChanged", {"outputActive": False, "outputState": "OBS_WEBSOCKET_OUTPUT_STARTING"})
        self.stream_aktiv = True
        self.ereignis("StreamStateChanged", {"outputActive": True, "outputState": "OBS_WEBSOCKET_OUTPUT_STARTED"})

    def stream_stoppen(self):
        self.ereignis("StreamStateChanged", {"outputActive": True, "outputState": "OBS_WEBSOCKET_OUTPUT_STOPPING"})
        self.stream_aktiv = False
        self.ereignis("StreamStateChanged", {"outputActive": False, "outputState": "OBS_WEBSOCKET_OUTPUT_STOPPED"})

    def szene_wechseln(self, name):
        self.szene = name
        self.ereignis("CurrentProgramSceneChanged", {"sceneName": name})

    def alle_trennen(self):
        for c in list(self.clients):
            c.close()

    def beenden(self):
        for c in list(self.clients):
            c.abort()
        self.server.close()
