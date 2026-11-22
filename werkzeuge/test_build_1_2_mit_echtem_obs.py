"""Build 1.2 mit echtem OBS prüfen – ohne deine OBS-Einstellungen anzufassen.

Startet ein eigenes, unsichtbares Test-OBS (Wegwerf-Ordner, eigener Port) und prüft:
Shots lesen und live schalten, Shot anlegen mit Zweck und Layout (mit der echten Kamera),
Bild-Shot, umbenennen, löschen (Ressourcen werden frei), Vorschaubilder nur bei Bedarf,
Wenn-dann-Regeln mit echtem Stream (an einen kleinen Empfänger auf diesem PC), Ton stumm,
und misst die Rechenlast: nichts offen / Shot-Leiste offen / Regel aktiv.

Bildschirm- und Fensteraufnahme werden nur als „OBS kennt den Typ“ geprüft – anlegen würde das
Auswahlfenster des Systems öffnen. Stattdessen nimmt der Test eine Farbfläche als großes Bild.

Aufruf (aus dem OpenRegie-Ordner):  python3 werkzeuge/test_build_1_2_mit_echtem_obs.py [--ohne-kamera]
"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

OHNE_KAMERA = "--ohne-kamera" in sys.argv
S = tempfile.mkdtemp(prefix="openregie-obs-test12-")
K = Path(S) / "obs-studio"
(K / "plugin_config/obs-websocket").mkdir(parents=True)
(K / "basic/profiles/T").mkdir(parents=True)
(K / "basic/scenes").mkdir(parents=True)
(K / "basic/scenes/T.json").write_text(json.dumps({
    "name": "T", "current_scene": "Szene", "current_program_scene": "Szene",
    "scene_order": [{"name": "Szene"}, {"name": "Pause"}],
    "sources": [{"id": "scene", "versioned_id": "scene", "name": "Szene", "settings": {"items": []}},
                {"id": "scene", "versioned_id": "scene", "name": "Pause", "settings": {"items": []}}]}))
(K / "plugin_config/obs-websocket/config.json").write_text(json.dumps({
    "alerts_enabled": False, "auth_required": True, "first_load": False, "server_enabled": True,
    "server_password": "testpasswort12", "server_port": 4477}))
ini = ("[General]\nFirstRun=true\nEnableAutoUpdates=false\nConfirmOnExit=false\n[Basic]\nProfile=T\nProfileDir=T\n"
       "SceneCollection=T\nSceneCollectionFile=T\n[BasicWindow]\nSysTrayEnabled=true\nSysTrayWhenStarted=false\n"
       "WarnBeforeStartingStream=false\nWarnBeforeStoppingStream=false\n")
(K / "global.ini").write_text(ini)
(K / "user.ini").write_text(ini)
(K / "basic/profiles/T/basic.ini").write_text(
    "[General]\nName=T\n[Video]\nBaseCX=1280\nBaseCY=720\nOutputCX=1280\nOutputCY=720\nFPSCommon=30\n")
(K / "basic/profiles/T/service.json").write_text(json.dumps(
    {"type": "rtmp_custom", "settings": {"server": "rtmp://127.0.0.1:19351/live", "key": "test", "use_auth": False}}))

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtGui import QColor, QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from openregie import einstellungen  # noqa: E402
from openregie.automatik.motor import Automatik, Regel  # noqa: E402
from openregie.obs import vorlagen  # noqa: E402
from openregie.obs.quellen import ObsQuellen, bild_aus_daten  # noqa: E402
from openregie.obs.verbindung import ObsVerbindung, Sendung  # noqa: E402
from openregie.obs.zugang import Zugang  # noqa: E402
from tests.hilfen import warte, warte_bis  # noqa: E402

app = QApplication([])
E = einstellungen.lade()
E._werte["quellen"] = dict(E.quellen.als_dict())
ergebnisse = []


def pruef(name, ok, info=""):
    ergebnisse.append((name, bool(ok)))
    print(("OK    " if ok else "FEHLER"), name, info, flush=True)


umgebung = dict(os.environ, XDG_CONFIG_HOME=S)
umgebung.pop("QT_QPA_PLATFORM", None)
obs = subprocess.Popen(["obs", "--multi", "--minimize-to-tray", "--disable-shutdown-check"], env=umgebung,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
rtmp = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-listen", "1", "-i", "rtmp://127.0.0.1:19351/live/test",
                         "-f", "null", "-"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

oe = einstellungen.Bereich("obs", dict(E.obs.als_dict(), adresse="127.0.0.1"))
v = ObsVerbindung(oe, E.texte, zugang_finden=lambda: Zugang(port=4477, passwort="testpasswort12"),
                  obs_laeuft=lambda: True)
# Jede Anfrage von OpenRegie mitzählen (für „im Leerlauf keine Abfragen“)
gezaehlt = []
_anfrage = v.anfrage


def zaehlende_anfrage(typ, daten=None, rueckruf=None):
    gezaehlt.append(typ)
    _anfrage(typ, daten, rueckruf)


v.anfrage = zaehlende_anfrage
v.starten()
pruef("Test-OBS gestartet und verbunden", warte_bis(lambda: v.verbunden and v.szene, 60000),
      "" if v.verbunden else "OBS meldet sich nicht – läuft es? (z. B. fehlende Bibliothek nach Update)")
if not v.verbunden:
    obs.kill()
    rtmp.kill()
    sys.exit(1)

antworten = {}


def frag(typ, daten=None):
    antworten.pop(typ, None)
    _anfrage(typ, daten, lambda ok, d, f: antworten.__setitem__(typ, (ok, d, f)))
    warte_bis(lambda: typ in antworten, 8000)
    return antworten.get(typ, (False, {}, "keine Antwort"))


ok, d, _ = frag("GetVersion")
print("      OBS", d.get("obsVersion"), "WebSocket", d.get("obsWebSocketVersion"))
ok, d, _ = frag("GetInputKindList", {"unversioned": True})
arten = set(d.get("inputKinds", []))
ok, d, _ = frag("GetInputKindList", {"unversioned": False})
arten_v = set(d.get("inputKinds", []))
for art in ("v4l2_input", "pipewire-screen-capture-source", "image_source", "browser_source"):
    pruef(f"OBS kennt den Quellentyp „{art}“", art in arten)
print("      Fensteraufnahme eigen:", "pipewire-window-capture-source" in arten,
      "(sonst über die Bildschirmaufnahme – dort ist auch ein Fenster wählbar)")
for z in ("spiel", "reactions", "bildschirm", "kamera", "bild"):
    a_ = vorlagen.obs_art_waehlen(vorlagen.QUELLENARTEN[vorlagen.ZWECKE[z].haupt], arten_v)
    pruef(f"Zweck „{z}“ hat einen passenden OBS-Typ", a_ is not None, str(a_))

# Für den Test: eine Farbfläche statt Bildschirm/Fenster (würde sonst das System-Auswahlfenster öffnen)
vorlagen.QUELLENARTEN["testfarbe"] = vorlagen.QuellenArt("testfarbe", ("color_source",), "",
                                                        einstellungen={"color": 0xFF2B6F4A, "width": 1280,
                                                                       "height": 720})
vorlagen.ZWECKE["testreactions"] = vorlagen.Zweck("testreactions", "", "testfarbe", not OHNE_KAMERA,
                                                  ("kamera_rechts_unten", "nebeneinander"))
E._werte["texte"] = dict(E.texte.als_dict(), zweck_testreactions="Reactions Test", art_testfarbe="Farbe",
                         quelle_name_testfarbe="Reactions-Video")
q = ObsQuellen(v, E.texte, E.quellen)
ich = object()


def ausfuehren(aufruf, *args, **kw):
    erg = []
    aufruf(*args, lambda ok, text: erg.append((ok, text)), **kw)
    warte_bis(lambda: erg, 20000)
    warte(400)
    return erg[0] if erg else (False, "keine Antwort")


# --- Shots lesen und live schalten ------------------------------------------------
vorher = len(gezaehlt)
warte(1500)
pruef("Niemand schaut hin → keine Abfrage der Shots", "GetSceneList" not in gezaehlt[vorher:], gezaehlt[vorher:])
q.beobachten(ich)
pruef("Shots werden gelesen", warte_bis(lambda: q.gelesen, 5000), str([s.name for s in q.shots]))
pruef("Reihenfolge wie in OBS (oben zuerst)", [s.name for s in q.shots] == ["Szene", "Pause"],
      str([s.name for s in q.shots]))
for i in range(12):
    ziel = "Pause" if i % 2 == 0 else "Szene"
    ausfuehren(q.live_schalten, ziel)
    warte_bis(lambda: v.szene == ziel, 3000)
    if v.szene != ziel:
        break
pruef("12× live schalten (abwechselnd)", v.szene == "Szene", v.szene)

# --- Shot mit Zweck und Layout -----------------------------------------------------
t0 = time.monotonic()
ok, name = ausfuehren(q.shot_anlegen, "testreactions", "kamera_rechts_unten")
pruef("Shot „Reactions“ angelegt (Video groß + Kamera klein)", ok, f"{name} in {time.monotonic() - t0:.1f}s")
ok, liste, _ = frag("GetSceneItemList", {"sceneName": name})
eintraege = sorted(liste.get("sceneItems", []), key=lambda e: e["sceneItemIndex"])
namen = [e["sourceName"] for e in eintraege]
pruef("Inhalt des Shots stimmt", namen == (["Reactions-Video"] if OHNE_KAMERA else ["Reactions-Video", "Kamerabild"]),
      str(namen))
if not OHNE_KAMERA and "Kamerabild" in namen:
    ok, s, _ = frag("GetInputSettings", {"inputName": "Kamerabild"})
    pruef("Kamera ist ausgewählt (device_id gesetzt)", bool(s.get("inputSettings", {}).get("device_id")),
          str(s.get("inputSettings", {}).get("device_id")))
    kamera = next(e for e in eintraege if e["sourceName"] == "Kamerabild")
    ok, tr, _ = frag("GetSceneItemTransform", {"sceneName": name, "sceneItemId": kamera["sceneItemId"]})
    tr = tr.get("sceneItemTransform", {})
    pruef("Kamera klein rechts unten (OBS-Transform)",
          tr.get("positionX", 0) > 640 and tr.get("positionY", 0) > 360 and abs(tr.get("boundsWidth", 0) - 358.4) < 2,
          f"x={tr.get('positionX')} y={tr.get('positionY')} b={tr.get('boundsWidth')} h={tr.get('boundsHeight')}")
    def standbild(datei):
        ok, b, _ = frag("GetSourceScreenshot", {"sourceName": name, "imageFormat": "png", "imageWidth": 640})
        bild = bild_aus_daten(b.get("imageData", ""))
        if bild is None:
            return None, None
        bild.save(str(Path(S) / datei))
        print("      Standbild:", Path(S) / datei)
        return QColor(bild.pixel(160, 90)), QColor(bild.pixel(int(640 * 0.86), int(360 * 0.80)))

    warte(2500)  # Kamera braucht einen Moment
    mitte, ecke = standbild("reactions_nicht_live.png")
    pruef("Standbild: großes Bild füllt die Fläche", mitte is not None and abs(mitte.green() - 0x6F) < 25,
          mitte.name() if mitte else "")
    ausfuehren(q.live_schalten, name)
    warte_bis(lambda: False, 5000)  # die Kamera braucht nach dem Start einige Sekunden für das erste Bild
    mitte, ecke = standbild("reactions_live.png")
    ok, akt, _ = frag("GetSourceActive", {"sourceName": "Kamerabild"})
    ok, kb, f = frag("GetSourceScreenshot", {"sourceName": "Kamerabild", "imageFormat": "png", "imageWidth": 320})
    kbild = bild_aus_daten(kb.get("imageData", "")) if ok else None
    ok, liste, _ = frag("GetSceneItemList", {"sceneName": name})
    ok, tr, _ = frag("GetSceneItemTransform", {"sceneName": name, "sceneItemId": kamera["sceneItemId"]})
    print("      Kamera:", akt, "eigenes Bild:", kbild.size() if kbild else f,
          [(e["sourceName"], e["sceneItemEnabled"], e["sceneItemIndex"]) for e in liste.get("sceneItems", [])],
          {k: tr.get("sceneItemTransform", {}).get(k) for k in ("width", "height", "sourceWidth", "sourceHeight",
                                                                "scaleX", "scaleY")})
    pruef("Live: Kamera klein rechts unten zu sehen", ecke is not None and ecke != mitte, ecke.name() if ecke else "")
    ausfuehren(q.live_schalten, "Szene")
    warte(3000)
    mitte2, ecke2 = standbild("reactions_danach_nicht_live.png")
    print("      Nicht mehr live – Kamera im Vorschaubild noch zu sehen:",
          ecke2 is not None and ecke2 != mitte2, ecke2.name() if ecke2 else "")

# Bild-Shot
png = Path(S) / "pause.png"
img = QImage(640, 360, QImage.Format.Format_RGB32)
img.fill(QColor("#C0392B"))
img.save(str(png))
ok, name_bild = ausfuehren(q.shot_anlegen, "bild", "voll", datei=str(png))
pruef("Shot „Bild“ angelegt", ok, name_bild)
warte(800)
ok, b, _ = frag("GetSourceScreenshot", {"sourceName": name_bild, "imageFormat": "png", "imageWidth": 320})
bild = bild_aus_daten(b.get("imageData", ""))
farbe = QColor(bild.pixel(160, 90)).name() if bild is not None else "?"
pruef("Bild-Shot zeigt das Bild – auch wenn er nicht live ist", farbe.lower() == "#c0392b", farbe)

# Zweiter Shot mit Kamera → Kamera wird wiederverwendet
if not OHNE_KAMERA:
    ok, name2 = ausfuehren(q.shot_anlegen, "kamera", "voll")
    ok, d, _ = frag("GetInputList", {"inputKind": "v4l2_input"})
    pruef("Zweiter Kamera-Shot nutzt dieselbe Kamera", len(d.get("inputs", [])) == 1, str(d.get("inputs")))

# --- Umbenennen ---------------------------------------------------------------------
for i in range(12):
    neu = f"Reactions {i}"
    ok, text = ausfuehren(q.shot_umbenennen, name, neu)
    if not ok:
        break
    name = neu
ok, d, _ = frag("GetSceneList")
pruef("12× Shot umbenannt", name in [s["sceneName"] for s in d.get("scenes", [])], name)
ok, text = ausfuehren(q.quelle_umbenennen, "Reactions-Video", "Mein Video")
ok2, d, _ = frag("GetInputList")
pruef("Quelle umbenannt", ok and "Mein Video" in [e["inputName"] for e in d.get("inputs", [])], text)
ok, text = ausfuehren(q.shot_umbenennen, name, "Pause")
pruef("Name schon vergeben → verständliche Meldung", not ok and text == E.texte.meldung_name_vergeben, text)

# --- Standbilder nur bei Bedarf ----------------------------------------------------------
s = q.standbilder()
bilder = []
s.neues_bild.connect(lambda n, b: bilder.append(n))
s._takt.setInterval(500)
s.beobachten([x.name for x in q.shots])
warte(3000)
pruef("Vorschaubilder kommen", len(bilder) >= len(q.shots), f"{len(bilder)} Bilder")
s.anhalten()
warte(300)
n = len(bilder)
vorher = len(gezaehlt)
warte(2000)
pruef("Angehalten: keine Bild-Anfragen mehr", "GetSourceScreenshot" not in gezaehlt[vorher:] and len(bilder) == n)

# --- Löschen gibt frei -----------------------------------------------------------------
ok, text = ausfuehren(q.shot_loeschen, name)
ok2, d, _ = frag("GetInputList")
eingaenge = [e["inputName"] for e in d.get("inputs", [])]
pruef("Shot gelöscht, sein Video ganz aus OBS entfernt", ok and "Mein Video" not in eingaenge, str(eingaenge))
if not OHNE_KAMERA:
    pruef("Kamera bleibt (noch im Kamera-Shot)", "Kamerabild" in eingaenge)
    ok, _ = ausfuehren(q.shot_loeschen, name2)
    ok2, d, _ = frag("GetInputList")
    pruef("Letzter Kamera-Shot gelöscht → Kamera ist frei", "Kamerabild" not in [e["inputName"] for e in d["inputs"]])

# --- Wenn-dann mit echtem Stream --------------------------------------------------------
uno = type("U", (), {"overlays": {}})()
a = Automatik(E.texte, v, q, uno, datei=Path(S) / "automatik.json")
a.laden()
warte_bis(lambda: a.geladen, 3000)
pruef("Ohne Regel ruht die Automatik", not a.laeuft)
frag("CreateInput", {"sceneName": "Szene", "inputName": "Mikro Test", "inputKind": "pulse_input_capture",
                     "inputSettings": {"device_id": "default"}, "sceneItemEnabled": True})
a.regel_speichern(Regel("stream_startet", "shot_live", dann_wert="Pause"))
a.regel_speichern(Regel("stream_endet", "ton_aus", dann_wert="Mikro Test"))
pruef("Mit aktiver Regel läuft sie", a.laeuft)
ausfuehren(q.live_schalten, "Szene")
frag("StartStream")
pruef("Stream startet → Shot „Pause“ live", warte_bis(lambda: v.szene == "Pause", 15000), v.szene)
warte(2000)
frag("StopStream")
warte_bis(lambda: v.sendung is Sendung.AUS, 15000)
warte(1000)
ok, d, _ = frag("GetInputMute", {"inputName": "Mikro Test"})
pruef("Stream endet → Ton stumm", d.get("inputMuted") is True, str(d))


# --- Rechenlast --------------------------------------------------------------------------
def cpu(pid):
    f = open(f"/proc/{pid}/stat").read().rsplit(")", 1)[1].split()
    return (int(f[11]) + int(f[12])) / os.sysconf("SC_CLK_TCK")


def messen(sekunden=10):
    c_obs, c_ich, t0, n0 = cpu(obs.pid), cpu(os.getpid()), time.monotonic(), len(gezaehlt)
    warte(int(sekunden * 1000))
    d = time.monotonic() - t0
    return ((cpu(obs.pid) - c_obs) / d * 100, (cpu(os.getpid()) - c_ich) / d * 100, (len(gezaehlt) - n0) / d,
            gezaehlt[n0:])


for r in list(a.regeln):
    a.regel_loeschen(r.kennung)
q.loslassen(ich)
warte(1000)
o1, i1, a1, liste = messen()
pruef("Leerlauf (nichts offen, keine Regel): keine Abfragen außer On-Air-Prüfung",
      set(liste) <= {"GetStreamStatus"}, f"OBS {o1:.1f} % · OpenRegie {i1:.1f} % · {a1:.2f} Anfragen/s")
s = q.standbilder()
q.beobachten(ich)
s.beobachten([x.name for x in q.shots])  # wie die offene Shot-Leiste (alle 5 s)
o2, i2, a2, _ = messen()
print(f"      Shot-Leiste offen: OBS {o2:.1f} % · OpenRegie {i2:.1f} % · {a2:.2f} Anfragen/s")
s.anhalten()
q.loslassen(ich)
a.regel_speichern(Regel("stream_startet", "shot_live", dann_wert="Pause"))
o3, i3, a3, liste = messen()
pruef("Regel aktiv (Ereignis-Auslöser): keine zusätzlichen Abfragen", set(liste) <= {"GetStreamStatus"},
      f"OBS {o3:.1f} % · OpenRegie {i3:.1f} % · {a3:.2f} Anfragen/s")
a.beenden()

v.beenden()
obs.terminate()
try:
    obs.wait(15)
except subprocess.TimeoutExpired:
    obs.kill()
rtmp.kill()
print()
print(f"{sum(ok for _, ok in ergebnisse)} von {len(ergebnisse)} Prüfungen bestanden")
sys.exit(0 if all(ok for _, ok in ergebnisse) else 1)
