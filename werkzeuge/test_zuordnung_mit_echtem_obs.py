"""Build 1.2.1 mit echtem OBS prüfen: Gehört jede Kachel fest zu IHRER Szene?

Startet ein eigenes, unsichtbares Test-OBS (Wegwerf-Ordner, eigener Port – deine OBS-Einstellungen
bleiben unberührt) mit 5 Szenen in 5 Farben, darunter „Countdown“ und „Bildschirmaufnahme“, und prüft
je 12 Runden lang:
  - Klick auf jede Kachel → OBS sendet genau diese Szene (über die feste Kennung), roter Rahmen stimmt
  - Vorschaubild jeder Kachel hat die Farbe IHRER Szene
  - Umbenennen in OBS (auch die Live-Szene), Neuanlegen, zwei Szenen tauschen die Namen
  - großes Live-Bild fragt über die Kennung
  - Aufnahme ohne Bild (Kamera, die es nicht gibt) → „⚠ Kein Bild“ auf der Kachel
Umsortieren mit der Maus kann man über die OBS-Schnittstelle nicht auslösen – das prüfen die Unit-Tests.

Aufruf (aus dem OpenRegie-Ordner):  python3 werkzeuge/test_zuordnung_mit_echtem_obs.py
"""
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RUNDEN = 12
FARBEN = {"Countdown": 0xFF4D48E5, "Bildschirmaufnahme": 0xFFDF6C2D, "Pause": 0xFF50B93F, "Kamera": 0xFF35B0F2,
          "Spiel": 0xFFB6599B}  # OBS: 0xAABBGGRR

S = tempfile.mkdtemp(prefix="openregie-obs-zuordnung-")
K = Path(S) / "obs-studio"
(K / "plugin_config/obs-websocket").mkdir(parents=True)
(K / "basic/profiles/T").mkdir(parents=True)
(K / "basic/scenes").mkdir(parents=True)
quellen = []
for n, f in FARBEN.items():
    quellen.append({"id": "color_source_v3", "versioned_id": "color_source_v3", "name": f"{n} Farbe",
                    "settings": {"color": f, "width": 1280, "height": 720}})
    quellen.append({"id": "scene", "versioned_id": "scene", "name": n,
                    "settings": {"items": [{"name": f"{n} Farbe", "visible": True, "id": 1}], "id_counter": 1}})
(K / "basic/scenes/T.json").write_text(json.dumps({
    "name": "T", "current_scene": "Countdown", "current_program_scene": "Countdown",
    "scene_order": [{"name": n} for n in FARBEN], "sources": quellen}))
(K / "plugin_config/obs-websocket/config.json").write_text(json.dumps({
    "alerts_enabled": False, "auth_required": True, "first_load": False, "server_enabled": True,
    "server_password": "testpasswort12", "server_port": 4478}))
ini = ("[General]\nFirstRun=true\nEnableAutoUpdates=false\nConfirmOnExit=false\n[Basic]\nProfile=T\nProfileDir=T\n"
       "SceneCollection=T\nSceneCollectionFile=T\n[BasicWindow]\nSysTrayEnabled=true\nSysTrayWhenStarted=false\n")
(K / "global.ini").write_text(ini)
(K / "user.ini").write_text(ini)
(K / "basic/profiles/T/basic.ini").write_text(
    "[General]\nName=T\n[Video]\nBaseCX=1280\nBaseCY=720\nOutputCX=1280\nOutputCY=720\nFPSCommon=30\n")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtGui import QColor  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from openregie import einstellungen  # noqa: E402
from openregie.obs.quellen import ObsQuellen  # noqa: E402
from openregie.obs.verbindung import ObsVerbindung  # noqa: E402
from openregie.obs.vorschau import Vorschau  # noqa: E402
from openregie.obs.zugang import Zugang  # noqa: E402
from openregie.oberflaeche.shot_bereich import ShotLeiste  # noqa: E402
from tests.hilfen import warte, warte_bis  # noqa: E402
from tests.test_fenster import klick  # noqa: E402

app = QApplication([])
E = einstellungen.lade()
E._werte["quellen"] = dict(E.quellen.als_dict(), vorschau_sekunden=0.5)
ergebnisse = []


def pruef(name, ok, info=""):
    ergebnisse.append((name, bool(ok)))
    print(("OK    " if ok else "FEHLER"), name, info, flush=True)


umgebung = dict(os.environ, XDG_CONFIG_HOME=S)
umgebung.pop("QT_QPA_PLATFORM", None)
obs = subprocess.Popen(["obs", "--multi", "--minimize-to-tray", "--disable-shutdown-check"], env=umgebung,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    oe = einstellungen.Bereich("obs", dict(E.obs.als_dict(), adresse="127.0.0.1"))
    v = ObsVerbindung(oe, E.texte, zugang_finden=lambda: Zugang(port=4478, passwort="testpasswort12"),
                      obs_laeuft=lambda: True)
    gesendet = []
    _anfrage = v.anfrage

    def zaehlende_anfrage(typ, daten=None, rueckruf=None):
        gesendet.append((typ, dict(daten or {})))
        _anfrage(typ, daten, rueckruf)
    v.anfrage = zaehlende_anfrage
    v.starten()
    pruef("Test-OBS gestartet und verbunden", warte_bis(lambda: v.verbunden and v.szene, 60000))
    if not v.verbunden:
        sys.exit(1)

    antworten = {}

    def frag(typ, daten=None):
        antworten.pop(typ, None)
        _anfrage(typ, daten, lambda ok, d, f: antworten.__setitem__(typ, (ok, d, f)))
        warte_bis(lambda: typ in antworten, 8000)
        return antworten.get(typ, (False, {}, "keine Antwort"))

    ok, d, _ = frag("GetVersion")
    print("      OBS", d.get("obsVersion"), "WebSocket", d.get("obsWebSocketVersion"))
    pruef("OBS meldet die feste Kennung der Live-Szene", bool(v.szene_kennung), v.szene_kennung)

    q = ObsQuellen(v, E.texte, E.quellen)
    l = ShotLeiste(E, q)
    l.resize(1900, 160)  # alle 5 auf einer Seite
    l.show()
    vs = Vorschau(v, E.vorschau)
    pruef("5 Kacheln in OBS-Reihenfolge", warte_bis(lambda: [s.name for s in q.shots] == list(FARBEN), 8000),
          str([s.name for s in q.shots]))
    pruef("jeder Shot hat eine feste Kennung", all(s.uuid for s in q.shots))

    def obs_live():
        ok, d, _ = frag("GetCurrentProgramScene")
        return d.get("sceneName"), d.get("sceneUuid")

    def schalten(name):
        """Kachel klicken; True, wenn OBS danach genau diese Szene sendet und nur ihre Kachel rot ist."""
        k = l.kachel(name)
        if k is None:
            return False, "keine Kachel"
        vorher = len(gesendet)
        klick(k)
        warte_bis(lambda: any(t == "SetCurrentProgramScene" for t, _ in gesendet[vorher:]), 3000)
        warte_bis(lambda: v.szene == name and k.live, 3000)
        geschickt = [d for t, d in gesendet[vorher:] if t == "SetCurrentProgramScene"]
        live_name, live_uuid = obs_live()
        shot = q.shot(name)
        rot = [x.name for x in l.kacheln.values() if x.live]
        gut = (geschickt == [{"sceneUuid": shot.uuid}] and live_name == name and live_uuid == shot.uuid
               and rot == [name])
        return gut, f"geschickt={geschickt} OBS={live_name} rot={rot}"

    def farbe_passt(name, abgr):
        k = l.kachel(name)
        if k is None or k.bild is None:
            return False
        b = k.bild.toImage()
        c = b.pixelColor(b.width() // 2, b.height() // 2)
        z = QColor(abgr & 0xFF, (abgr >> 8) & 0xFF, (abgr >> 16) & 0xFF)
        return all(abs(x - y) < 30 for x, y in ((c.red(), z.red()), (c.green(), z.green()), (c.blue(), z.blue())))

    farbe = dict(FARBEN)
    zufall = random.Random(12)

    # 1) Kevins Fall + alle Szenen in zufälliger Reihenfolge
    fehler = []
    for runde in range(RUNDEN):
        for name in ("Bildschirmaufnahme", "Countdown"):
            gut, info = schalten(name)
            if not gut:
                fehler.append((runde, name, info))
    pruef(f"Kevins Fall: Bildschirmaufnahme/Countdown je {RUNDEN}× richtig", not fehler, str(fehler[:2]))
    fehler = []
    for runde in range(RUNDEN):
        reihe = list(FARBEN)
        zufall.shuffle(reihe)
        for name in reihe:
            if v.szene != name:
                gut, info = schalten(name)
                if not gut:
                    fehler.append((runde, name, info))
    pruef(f"5 Szenen, {RUNDEN} Runden zufällig: jede Kachel schaltet ihre Szene", not fehler, str(fehler[:2]))

    # 2) Vorschaubilder gehören zu ihrer Szene
    pruef("Vorschaubild jeder Kachel = Farbe ihrer Szene",
          warte_bis(lambda: all(farbe_passt(n, f) for n, f in farbe.items()), 8000))
    bild_anfragen = [d for t, d in gesendet if t == "GetSourceScreenshot"]
    pruef("Kacheln und großes Bild fragen nur über die Kennung", bool(bild_anfragen) and
          all("sourceUuid" in d and "sourceName" not in d for d in bild_anfragen))
    pruef("großes Live-Bild kommt an", warte_bis(lambda: vs.bilder_erhalten > 3, 5000), str(vs.bilder_erhalten))

    # 3) Umbenennen in OBS (wie mit Rechtsklick) – die Kachel bleibt dieselbe
    fehler = []
    alt = "Pause"
    for runde in range(RUNDEN):
        neu = f"Pause {runde}"
        kachel = l.kachel(alt)
        frag("SetSceneName", {"sceneName": alt, "newSceneName": neu})
        if not warte_bis(lambda: l.kachel(neu) is kachel and kachel.name == neu, 3000):
            fehler.append((runde, "Kachel nicht mitgenommen"))
        farbe[neu] = farbe.pop(alt)
        gut, info = schalten(neu)
        if not gut:
            fehler.append((runde, info))
        gut, info = schalten("Countdown")
        if not gut:
            fehler.append((runde, info))
        alt = neu
    pruef(f"Umbenennen in OBS {RUNDEN}×: gleiche Kachel, richtige Szene", not fehler, str(fehler[:2]))

    # 4) Die Live-Szene umbenennen – OpenRegie merkt es sofort
    fehler = []
    for runde in range(RUNDEN):
        gut, info = schalten("Spiel" if runde == 0 else f"Spiel {runde - 1}")
        if not gut:
            fehler.append((runde, info))
        alt_name = v.szene
        neu = f"Spiel {runde}"
        vorher = len(gesendet)
        frag("SetSceneName", {"sceneName": alt_name, "newSceneName": neu})
        if not warte_bis(lambda: v.szene == neu, 1000):
            fehler.append((runde, "Live-Name nicht sofort", v.szene))
        if not warte_bis(lambda: [x.name for x in l.kacheln.values() if x.live] == [neu], 2000):
            fehler.append((runde, "roter Rahmen falsch"))
        if any(t == "GetCurrentProgramScene" for t, _ in gesendet[vorher:]):
            fehler.append((runde, "musste nachfragen"))
        farbe[neu] = farbe.pop(alt_name)
    pruef(f"Live-Szene umbenannt {RUNDEN}×: sofort richtig, ohne Nachfragen", not fehler, str(fehler[:2]))

    # 5) Neue Szenen anlegen – alte Kacheln bleiben bei ihrer Szene
    fehler = []
    for runde in range(RUNDEN):
        name = f"Neu {runde}"
        frag("CreateScene", {"sceneName": name})
        if not warte_bis(lambda: l.kachel(name) is not None or name in [s.name for s in q.shots], 3000):
            fehler.append((runde, "neue Kachel fehlt"))
            continue
        for ziel in ("Countdown", "Bildschirmaufnahme"):
            if l.kachel(ziel) is None:
                continue  # auf einer anderen Seite
            gut, info = schalten(ziel)
            if not gut:
                fehler.append((runde, ziel, info))
    pruef(f"{RUNDEN} neue Szenen angelegt: alte Kacheln schalten weiter richtig", not fehler, str(fehler[:2]))
    for runde in range(RUNDEN):
        frag("RemoveScene", {"sceneName": f"Neu {runde}"})
    pruef("Testszenen wieder weg", warte_bis(lambda: len(q.shots) == 5, 5000), str(len(q.shots)))

    # 6) Zwei Szenen tauschen die Namen
    fehler = []
    a, b = "Countdown", "Bildschirmaufnahme"
    for runde in range(RUNDEN):
        ka, kb = l.kachel(a), l.kachel(b)
        frag("SetSceneName", {"sceneName": a, "newSceneName": "Zwischen"})
        frag("SetSceneName", {"sceneName": b, "newSceneName": a})
        frag("SetSceneName", {"sceneName": "Zwischen", "newSceneName": b})
        farbe[a], farbe[b] = farbe[b], farbe[a]
        if not warte_bis(lambda: ka.name == b and kb.name == a, 3000):
            fehler.append((runde, "Kacheln folgen nicht", ka.name, kb.name))
        for ziel in (a, b):
            gut, info = schalten(ziel)
            if not gut:
                fehler.append((runde, ziel, info))
        if not warte_bis(lambda: farbe_passt(a, farbe[a]) and farbe_passt(b, farbe[b]), 5000):
            fehler.append((runde, "Bild falsch"))
    pruef(f"Namen tauschen {RUNDEN}×: jede Kachel folgt ihrer Szene (Bild und Schalten)", not fehler,
          str(fehler[:2]))

    # 7) Aufnahme ohne Bild → „⚠ Kein Bild“ (eine Kamera, die es nicht gibt – kein System-Fenster nötig)
    frag("CreateInput", {"sceneName": b, "inputName": "Kamera weg", "inputKind": "v4l2_input",
                         "inputSettings": {"device_id": "/dev/gibtesnicht"}})
    pruef("Aufnahme ohne Bild: Hinweis auf der Kachel",
          warte_bis(lambda: l.kachel(b) is not None and l.kachel(b).hinweis == E.texte.shot_kein_bild, 8000),
          repr(l.kachel(b).hinweis if l.kachel(b) else None))
    pruef("… nur auf dieser Kachel", all(not x.hinweis for x in l.kacheln.values() if x.name != b))
    gut, info = schalten(b)
    pruef("… und der Klick schaltet trotzdem die richtige Szene", gut, info)
    frag("RemoveInput", {"inputName": "Kamera weg"})
    pruef("Quelle weg → Hinweis weg", warte_bis(lambda: l.kachel(b).hinweis == "", 5000))

    # 8) Sparsam: ohne kaputte Quelle nur die Szenenbilder
    warte(1500)
    vorher = len(gesendet)
    warte(3000)
    ziele = {d.get("sourceUuid") for t, d in gesendet[vorher:]
             if t == "GetSourceScreenshot" and d.get("imageWidth") == int(E.quellen.vorschau_breite)}
    pruef("Kacheln fragen nur ihre 5 Szenen ab (keine Extra-Abfragen)", ziele <= {s.uuid for s in q.shots},
          f"{len(ziele)} Ziele")
    l.hide()
    warte(300)
    vorher = len(gesendet)
    warte(2000)
    pruef("Leiste weg → keine Kachel-Bilder mehr", not [1 for t, d in gesendet[vorher:]
                                                          if t == "GetSourceScreenshot"
                                                          and d.get("imageWidth") == int(E.quellen.vorschau_breite)])
    vs.anhalten()
finally:
    obs.terminate()
    try:
        obs.wait(15)
    except subprocess.TimeoutExpired:
        obs.kill()
    shutil.rmtree(S, ignore_errors=True)

gut = sum(1 for _, ok in ergebnisse if ok)
print(f"\nErgebnis: {gut} von {len(ergebnisse)} Prüfungen bestanden", flush=True)
sys.exit(0 if gut == len(ergebnisse) else 1)
