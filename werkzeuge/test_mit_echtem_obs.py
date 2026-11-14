"""Test mit echtem OBS – ohne deine OBS-Einstellungen anzufassen.

OpenRegie startet ein eigenes Test-OBS (unsichtbar, mit leeren Einstellungen in einem
Wegwerf-Ordner), dazu einen kleinen Test-Streamempfänger (ffmpeg) auf diesem PC, und prüft:
unsichtbarer Start, Verbindung, Szenensammlung, Vorschau, On Air, Absturz, Passwort,
sauberes Beenden.

Aufruf (aus dem OpenRegie-Ordner):  python3 werkzeuge/test_mit_echtem_obs.py
"""
import os, sys, time, subprocess, signal, tempfile, json, shutil
from pathlib import Path

S = tempfile.mkdtemp(prefix="openregie-obs-test-")
K = Path(S) / "obs-test" / "obs-studio"
(K / "plugin_config/obs-websocket").mkdir(parents=True)
(K / "basic/profiles/OpenRegie_Test").mkdir(parents=True)
(K / "basic/scenes").mkdir(parents=True)
for sammlung in ("OpenRegie_Test", "Zweite Sammlung"):
    (K / f"basic/scenes/{sammlung.replace(' ', '_')}.json").write_text(json.dumps({
        "name": sammlung, "current_scene": "Szene", "current_program_scene": "Szene",
        "scene_order": [{"name": "Szene"}],
        "sources": [{"id": "scene", "versioned_id": "scene", "name": "Szene", "settings": {"items": []}}]}))
(K / "plugin_config/obs-websocket/config.json").write_text(json.dumps({
    "alerts_enabled": False, "auth_required": True, "first_load": False, "server_enabled": True,
    "server_password": "testpasswort123", "server_port": 4466}))
ini = """[General]
FirstRun=true
EnableAutoUpdates=false
ConfirmOnExit=false

[Basic]
Profile=OpenRegie_Test
ProfileDir=OpenRegie_Test
SceneCollection=OpenRegie_Test
SceneCollectionFile=OpenRegie_Test

[BasicWindow]
SysTrayEnabled=true
SysTrayWhenStarted=false
WarnBeforeStartingStream=false
WarnBeforeStoppingStream=false
"""
(K / "global.ini").write_text(ini)
(K / "user.ini").write_text(ini)
(K / "basic/profiles/OpenRegie_Test/basic.ini").write_text(
    "[General]\nName=OpenRegie_Test\n\n[Video]\nBaseCX=1280\nBaseCY=720\nOutputCX=1280\nOutputCY=720\nFPSCommon=30\n")
(K / "basic/profiles/OpenRegie_Test/service.json").write_text(json.dumps(
    {"type": "rtmp_custom", "settings": {"server": "rtmp://127.0.0.1:19350/live", "key": "test", "use_auth": False}}))

os.environ["XDG_CONFIG_HOME"] = f"{S}/obs-test"   # OpenRegie liest Port/Passwort hier automatisch
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication
from openregie import einstellungen
from openregie.obs.motor import MotorZustand, ObsMotor
from openregie.obs.verbindung import ObsVerbindung, Sendung, Status
from openregie.obs.vorschau import Vorschau
from openregie.obs import zugang
from tests.hilfen import warte, warte_bis

app = QApplication([])
E = einstellungen.lade()
ergebnisse = []
def pruef(name, ok, info=""):
    ergebnisse.append((name, ok))
    print(("OK    " if ok else "FEHLER"), name, info, flush=True)

# OBS bekommt die echte Bildschirm-Umgebung (nicht „offscreen“)
os.environ.pop("QT_QPA_PLATFORM")
def obs_einstellungen(**werte):
    w = dict(E.obs.als_dict(), startbefehl="obs --multi", szenensammlung="Zweite Sammlung",
             start_zeitlimit_sekunden=40)
    w.update(werte)
    return einstellungen.Bereich("obs", w)

z = zugang.ermitteln(E.obs)
pruef("Port/Passwort automatisch gelesen", z.port == 4466 and z.passwort == "testpasswort123", f"port={z.port}")

oe = obs_einstellungen()
v = ObsVerbindung(oe, E.texte)
# Ein eventuell offenes eigenes OBS soll den Test nicht stören: „läuft OBS?“ fragt nur nach unserem
m = ObsMotor(oe, E.texte, v, obs_laeuft=lambda: False)
sendungen = []
v.sendung_geaendert.connect(lambda s: sendungen.append(s.value))
sammlung_meldungen = []
m.sammlung_meldung.connect(sammlung_meldungen.append)

rtmp = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-listen", "1", "-i", "rtmp://127.0.0.1:19350/live/test",
                         "-f", "null", "-"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
t0 = time.monotonic()
m.starten()
pruef("OBS wird unsichtbar gestartet", m.zustand is MotorZustand.STARTET and "--minimize-to-tray" in m.befehl(),
      " ".join(m.befehl()))
pruef("Verbindet automatisch, sobald OBS da ist", warte_bis(lambda: v.verbunden, 40000),
      f"nach {time.monotonic()-t0:.1f}s")
pruef("Motor meldet „läuft“", m.zustand is MotorZustand.LAEUFT, m.zustand.value)
warte(1500)

def obs_fenster_sichtbar() -> bool | None:
    """Fragt KDE (KWin), ob ein OBS-Hauptfenster offen ist. None = kann nicht prüfen."""
    import re
    for befehl in ("qdbus6", "qdbus"):
        try:
            aus = subprocess.run([befehl, "--literal", "org.kde.KWin", "/WindowsRunner", "org.kde.krunner1.Match",
                                  "OBS"], capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if aus.returncode == 0:
            titel = re.findall(r'\(sssida\{sv\}\) "[^"]*", "([^"]*)"', aus.stdout)
            return any(t.startswith("OBS ") for t in titel)
    return None
sichtbar = obs_fenster_sichtbar()
pruef("Kein OBS-Fenster auf dem Bildschirm", sichtbar is not True,
      "KWin nicht erreichbar – nicht geprüft" if sichtbar is None else "")

antworten = {}
def frag(typ, daten=None):
    antworten.pop(typ, None)
    v.anfrage(typ, daten, lambda ok, d, f: antworten.__setitem__(typ, (ok, d, f)))
    warte_bis(lambda: typ in antworten, 8000)
    return antworten.get(typ, (False, {}, "keine Antwort"))
ok, d, _ = frag("GetVersion")
print("      OBS", d.get("obsVersion"), "WebSocket", d.get("obsWebSocketVersion"))
ok, d, _ = frag("GetSceneCollectionList")
pruef("Richtige Szenensammlung beim Start (--collection)", d.get("currentSceneCollectionName") == "Zweite Sammlung",
      str(d.get("currentSceneCollectionName")))

# Umschalten über die Fernsteuerung (falls OBS schon lief)
m2 = ObsMotor(obs_einstellungen(szenensammlung="OpenRegie_Test"), E.texte, v, obs_laeuft=lambda: True)
m2.sammlung_meldung.connect(sammlung_meldungen.append)
sammlung_meldungen.clear()
m2._sammlung_pruefen()
warte_bis(lambda: sammlung_meldungen, 15000)
warte_bis(lambda: v.verbunden, 10000)
ok, d, _ = frag("GetSceneCollectionList")
pruef("Szenensammlung per Fernsteuerung gewechselt",
      sammlung_meldungen == [""] and d.get("currentSceneCollectionName") == "OpenRegie_Test",
      f"{d.get('currentSceneCollectionName')} {sammlung_meldungen}")
m3 = ObsMotor(obs_einstellungen(szenensammlung="Gibt es nicht"), E.texte, v, obs_laeuft=lambda: True)
fehlt = []
m3.sammlung_meldung.connect(fehlt.append)
m3._sammlung_pruefen()
warte_bis(lambda: fehlt, 5000)
pruef("Fehlende Szenensammlung wird verständlich gemeldet", bool(fehlt) and "Gibt es nicht" in fehlt[0],
      fehlt[0] if fehlt else "")
warte_bis(lambda: v.szene, 3000)

# Etwas Farbe in die Szene, damit die Vorschau Inhalt hat
frag("CreateInput", {"sceneName": v.szene or "Szene", "inputName": "Testfarbe", "inputKind": "color_source_v3",
                     "inputSettings": {"color": 0xFF6F4A2B, "width": 1280, "height": 720}, "sceneItemEnabled": True})

# Vorschau
vorschau = Vorschau(v, E.vorschau)
bilder = []
vorschau.neues_bild.connect(bilder.append)
warte(1500)
bilder.clear()
obs_pid = m._prozess.processId()
def cpu(pid):
    f = open(f"/proc/{pid}/stat").read().rsplit(")", 1)[1].split()
    return (int(f[11]) + int(f[12])) / os.sysconf("SC_CLK_TCK")
c_obs0, t0 = cpu(obs_pid), time.monotonic()
warte(5000)
dauer = time.monotonic() - t0
c_obs = (cpu(obs_pid) - c_obs0) / dauer * 100
fps = len(bilder) / dauer
pruef("Vorschau liefert Bilder", fps >= 5, f"{fps:.1f} Bilder/s, Rechenlast OBS {c_obs:.0f}% eines Kerns")

# On Air
sendungen.clear()
frag("StartStream")
pruef("On Air leuchtet beim Streamen", warte_bis(lambda: v.sendung is Sendung.AN, 15000), str(sendungen))
pruef("Beim Schließen würde nachgefragt (live)", m.braucht_nachfrage_beim_beenden)
warte(2000)
frag("StopStream")
pruef("On Air geht aus nach Stopp", warte_bis(lambda: v.sendung is Sendung.AUS, 15000), str(sendungen))
pruef("Ohne Stream keine Nachfrage", not m.braucht_nachfrage_beim_beenden)

# Uno-Quellen: alte Countdown-Quelle weg, Uno-Ausgabe in jede Szene, immer ganz oben
from PySide6.QtCore import QObject, Signal
from openregie.obs.overlays_in_obs import ObsOverlays
class UnoAttrappe(QObject):
    ausgaben_geaendert = Signal()
    def ausgaben(self):
        return [("Countdown | Circles", "https://controlapi.singular.live/output/OPENREGIETEST/Output?aspect=16:9")]
szene = v.szene or "Szene"
frag("CreateInput", {"sceneName": szene, "inputName": "Rolliregie Countdown", "inputKind": "browser_source",
                     "inputSettings": {"url": "http://127.0.0.1:8787/countdown"}, "sceneItemEnabled": True})
frag("CreateInput", {"sceneName": szene, "inputName": "Bildschirmaufnahme", "inputKind": "color_source_v3",
                     "inputSettings": {"color": 0xFF00AA00}, "sceneItemEnabled": True})
frag("CreateScene", {"sceneName": "Pause"})
def reihenfolge(sz):
    ok, d, _ = frag("GetSceneItemList", {"sceneName": sz})
    return [i["sourceName"] for i in sorted(d.get("sceneItems", []), key=lambda i: i["sceneItemIndex"])]
uno_attrappe = UnoAttrappe()
oo = ObsOverlays(oe, v, uno_attrappe)
oo.anstossen("ganz")
UNO = "Uno: Countdown | Circles"
warte_bis(lambda: oo.durchlaeufe and not oo._laeuft and reihenfolge(szene)[-1:] == [UNO], 15000)
r = reihenfolge(szene)
pruef("Alte Quelle „Rolliregie Countdown“ entfernt", "Rolliregie Countdown" not in r, str(r))
pruef("Uno-Quelle ganz oben (über der Bildschirmaufnahme)", r[-1:] == [UNO] and "Bildschirmaufnahme" in r, str(r))
pruef("Uno-Quelle auch in Szene „Pause“", reihenfolge("Pause") == [UNO], str(reihenfolge("Pause")))
ok, d, _ = frag("GetInputSettings", {"inputName": UNO})
pruef("Uno-Quelle so groß wie das Bild", (d.get("inputSettings") or {}).get("width") == 1280, str(d.get("inputSettings")))
frag("CreateInput", {"sceneName": szene, "inputName": "Kamera", "inputKind": "color_source_v3",
                     "inputSettings": {"color": 0xFF0000AA}, "sceneItemEnabled": True})
pruef("Neue Quelle in OBS → Uno rückt wieder nach oben",
      warte_bis(lambda: reihenfolge(szene)[-1:] == [UNO] and "Kamera" in reihenfolge(szene), 8000), str(reihenfolge(szene)))
ok, d, _ = frag("GetSceneItemList", {"sceneName": szene})
kamera = next(i for i in d["sceneItems"] if i["sourceName"] == "Kamera")
frag("SetSceneItemIndex", {"sceneName": szene, "sceneItemId": kamera["sceneItemId"], "sceneItemIndex": len(d["sceneItems"]) - 1})
pruef("Von Hand darübergeschoben → Uno rückt wieder nach oben",
      warte_bis(lambda: reihenfolge(szene)[-1:] == [UNO], 8000), str(reihenfolge(szene)))
warte(1500)  # OpenRegie prüft nach dem eigenen Verschieben noch genau einmal nach
anzahl = oo.durchlaeufe
warte(2500)
pruef("Kommt zur Ruhe (keine Endlosschleife)", oo.durchlaeufe == anzahl, f"{oo.durchlaeufe - anzahl} weitere Durchläufe")

# OBS stürzt ab → klare Meldung, „OBS starten“ holt es zurück
m._prozess.kill()
pruef("Absturz wird erkannt", warte_bis(lambda: m.zustand is MotorZustand.FEHLER, 5000), m.meldung)
pruef("Verständliche Meldung danach", m.meldung == E.texte.meldung_obs_abgestuerzt, m.meldung)
m.starten()
pruef("„OBS starten“ startet es wieder und verbindet", warte_bis(lambda: v.verbunden, 40000))

# Falsches Passwort
v.beenden()
alt = v._zugang_finden
v._zugang_finden = lambda: zugang.Zugang(port=4466, passwort="falsch")
v.starten()
pruef("Falsches Passwort wird verständlich gemeldet",
      warte_bis(lambda: v.meldung == E.texte.meldung_passwort_falsch, 5000), v.meldung)
v._zugang_finden = alt
v.jetzt_neu_verbinden()
warte_bis(lambda: v.verbunden, 5000)

# Sauber beenden (wie beim Schließen von OpenRegie)
vorschau.anhalten()
v.beenden()
prozess = m._prozess
t0 = time.monotonic()
m.beenden()
pruef("OBS beendet sich sauber beim Schließen", prozess.exitStatus().name == "NormalExit" and m.zustand is MotorZustand.AUS,
      f"nach {time.monotonic()-t0:.1f}s, Code {prozess.exitCode()}, {prozess.exitStatus().name}")
# Hätte OBS es als Absturz gewertet, läge hier eine Sperrdatei
pruef("OBS sieht das Beenden nicht als Absturz", not (K / ".sentinel").exists() or not any((K / ".sentinel").iterdir()))

rtmp.kill()
print()
print(f"{sum(ok for _, ok in ergebnisse)} von {len(ergebnisse)} Prüfungen bestanden")
sys.exit(0 if all(ok for _, ok in ergebnisse) else 1)
