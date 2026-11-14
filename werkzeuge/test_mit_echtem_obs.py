"""Test mit echtem OBS – ohne deine OBS-Einstellungen anzufassen.

Startet ein eigenes Test-OBS mit leeren Einstellungen in einem Wegwerf-Ordner,
einen kleinen Test-Streamempfänger (ffmpeg) auf diesem PC und prüft:
Verbindung, Passwort, Countdown einrichten, Vorschau, On Air, Abbruch und Neustart.

Aufruf (aus dem OpenRegie-Ordner):  python3 werkzeuge/test_mit_echtem_obs.py
Vorher OpenRegie schließen (der Test braucht die Countdown-Seite für sich).
"""
import os, sys, time, subprocess, signal, tempfile, json, shutil
from pathlib import Path

S = tempfile.mkdtemp(prefix="openregie-obs-test-")
K = Path(S) / "obs-test" / "obs-studio"
(K / "plugin_config/obs-websocket").mkdir(parents=True)
(K / "basic/profiles/OpenRegie_Test").mkdir(parents=True)
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
SysTrayWhenStarted=true
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
from openregie.obs.verbindung import ObsVerbindung, Sendung, Status
from openregie.obs.vorschau import Vorschau
from openregie.obs.einrichten import CountdownEinrichten
from openregie.obs import zugang
from openregie.titel.countdown import Countdown
from openregie.web.server import LokaleWebseite
from tests.hilfen import warte, warte_bis

app = QApplication([])
E = einstellungen.lade()
ergebnisse = []
def pruef(name, ok, info=""):
    ergebnisse.append((name, ok))
    print(("OK    " if ok else "FEHLER"), name, info, flush=True)

obs_env = dict(os.environ); obs_env.pop("QT_QPA_PLATFORM")
def obs_start():
    return subprocess.Popen(["obs", "--multi", "--minimize-to-tray", "--disable-shutdown-check"], env=obs_env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=S)

z = zugang.ermitteln(E.obs)
pruef("Port/Passwort automatisch gelesen", z.port == 4466 and z.passwort == "testpasswort123", f"port={z.port}")

v = ObsVerbindung(E.obs, E.texte)
stati, sendungen = [], []
v.status_geaendert.connect(lambda s, m: stati.append((s.value, m)))
v.sendung_geaendert.connect(lambda s: sendungen.append(s.value))
v.starten()
warte_bis(lambda: v.status is Status.GETRENNT and v.meldung, 3000)
pruef("Meldung ohne OBS", v.meldung == E.texte.meldung_obs_nicht_offen, v.meldung)

rtmp = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-listen", "1", "-i", "rtmp://127.0.0.1:19350/live/test",
                         "-f", "null", "-"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
obs = obs_start()
t0 = time.monotonic()
pruef("Verbindet automatisch, sobald OBS da ist", warte_bis(lambda: v.verbunden, 40000),
      f"nach {time.monotonic()-t0:.1f}s, Szene={v.szene!r}")
warte_bis(lambda: v.szene, 3000)

antworten = {}
def frag(typ, daten=None):
    antworten.pop(typ, None)
    v.anfrage(typ, daten, lambda ok, d, f: antworten.__setitem__(typ, (ok, d, f)))
    warte_bis(lambda: typ in antworten, 5000)
    return antworten.get(typ, (False, {}, "keine Antwort"))
ok, d, _ = frag("GetVersion")
print("      OBS", d.get("obsVersion"), "WebSocket", d.get("obsWebSocketVersion"))

# Etwas Farbe in die Szene, damit die Vorschau Inhalt hat
frag("CreateInput", {"sceneName": v.szene, "inputName": "Testfarbe", "inputKind": "color_source_v3",
                     "inputSettings": {"color": 0xFF6F4A2B, "width": 1280, "height": 720}, "sceneItemEnabled": True})

cd = Countdown("Countdown", 125, 5999)
web = LokaleWebseite(int(E.countdown.webseiten_port), cd, E.countdown); web.starten()
erg = []
CountdownEinrichten(v, E.countdown.obs_quellenname, web.countdown_adresse, E.texte, lambda o, m: erg.append((o, m))).los()
warte_bis(lambda: erg, 8000)
pruef("Countdown in OBS einrichten", bool(erg) and erg[0][0], erg[0][1] if erg else "keine Antwort")
erg.clear()
CountdownEinrichten(v, E.countdown.obs_quellenname, web.countdown_adresse, E.texte, lambda o, m: erg.append((o, m))).los()
warte_bis(lambda: erg, 8000)
ok, d, _ = frag("GetSceneItemList", {"sceneName": v.szene})
namen = [i["sourceName"] for i in d.get("sceneItems", [])]
pruef("Zweites Einrichten: kein Doppel", bool(erg) and erg[0][0] and namen.count(E.countdown.obs_quellenname) == 1, str(namen))

# Vorschau
vorschau = Vorschau(v, E.vorschau)
bilder = []
vorschau.neues_bild.connect(bilder.append)
warte(4000)  # Browserquelle laden lassen
cd.start()
bilder.clear()
obs_pid = obs.pid
def cpu(pid):
    f = open(f"/proc/{pid}/stat").read().rsplit(")", 1)[1].split()
    return (int(f[11]) + int(f[12])) / os.sysconf("SC_CLK_TCK")
c_obs0, c_wir0, t0 = cpu(obs_pid), time.process_time(), time.monotonic()
warte(5000)
dauer = time.monotonic() - t0
c_obs = (cpu(obs_pid) - c_obs0) / dauer * 100
c_wir = (time.process_time() - c_wir0) / dauer * 100
fps = len(bilder) / dauer
pruef("Vorschau liefert Bilder", fps >= 5, f"{fps:.1f} Bilder/s (Ziel {E.vorschau.bilder_pro_sekunde}), "
      f"Rechenlast: OBS {c_obs:.0f}% eines Kerns, OpenRegie {c_wir:.0f}%")
if bilder:
    bilder[-1].save(f"{S}/vorschau.png")
    print("      Vorschaubild gespeichert:", f"{S}/vorschau.png")
    print("      Bild", bilder[-1].width(), "x", bilder[-1].height())

# On Air
sendungen.clear()
frag("StartStream")
pruef("On Air leuchtet beim Streamen", warte_bis(lambda: v.sendung is Sendung.AN, 15000), str(sendungen))
warte(2000)
frag("StopStream")
pruef("On Air geht aus nach Stopp", warte_bis(lambda: v.sendung is Sendung.AUS, 15000), str(sendungen))

# OBS bricht weg und kommt wieder
obs.send_signal(signal.SIGKILL); obs.wait()
pruef("Erkennt, dass OBS weg ist", warte_bis(lambda: v.status is Status.GETRENNT, 5000), v.meldung)
warte(4000)
pruef("Verständliche Meldung danach", v.meldung in (E.texte.meldung_obs_nicht_offen, E.texte.meldung_verbindung_weg), v.meldung)
obs = obs_start()
pruef("Verbindet sich nach OBS-Neustart von selbst", warte_bis(lambda: v.verbunden, 40000))

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

# Aufräumen (der Test-Ordner gehört nur diesem Test)
vorschau.anhalten(); v.beenden(); web.beenden()
obs.terminate()
try: obs.wait(10)
except subprocess.TimeoutExpired: obs.kill()
rtmp.kill()
print()
print(f"{sum(ok for _, ok in ergebnisse)} von {len(ergebnisse)} Prüfungen bestanden")
sys.exit(0 if all(ok for _, ok in ergebnisse) else 1)
