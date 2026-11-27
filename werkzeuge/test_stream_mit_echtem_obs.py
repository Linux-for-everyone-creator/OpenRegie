"""Build 1.2.3 mit echtem OBS prüfen: „Stream starten / beenden“ – ohne deine OBS-Einstellungen anzufassen.

Startet ein eigenes, unsichtbares Test-OBS (Wegwerf-Ordner, eigener Port 4480) und das echte Regiepult
(unsichtbar). Gestreamt wird NUR an einen kleinen Empfänger auf diesem PC (ffmpeg) – nie an Twitch.
Geprüft wird, jeweils mehrere Runden, durch Anklicken des Knopfs:
  1. Starten (ohne Nachfrage) → wirklich live (Empfänger bekommt Daten) → ON AIR rot → Beenden mit Nachfrage
  2. Nachfrage „Weiter streamen“ → bleibt live, kein StopStream
  3. Start und Stopp direkt in OBS → Knopf und ON AIR folgen
  4. Kein Stream-Key (Twitch ohne Key) → verständliche Meldung, KEIN StartStream an OBS,
     also auch kein Fehlerfenster im unsichtbaren OBS
  5. Server nicht erreichbar → Meldung „konnte nicht starten“
  6. Empfänger bricht mitten im Stream weg → „VERBINDE …“ (nicht rot), Beenden geht trotzdem
  7. OBS wird mitten im Stream beendet → Knopf grau, Meldung; OBS wieder da → „Stream starten“
Zum Schluss: Im OBS-Protokoll darf kein „failed to start“ stehen (das wäre ein OBS-Fehlerfenster).

Aufruf (aus dem OpenRegie-Ordner):  python3 werkzeuge/test_stream_mit_echtem_obs.py [Runden]
"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RUNDEN = int(sys.argv[1]) if len(sys.argv) > 1 else 3
PORT, PASSWORT = 4480, "testpasswort123"
EMPFAENGER = "rtmp://127.0.0.1:19353/live"
NIEMAND = "rtmp://127.0.0.1:19398/live"  # da hört keiner zu

S = tempfile.mkdtemp(prefix="openregie-obs-test123-")
K = Path(S) / "obs-studio"
(K / "plugin_config/obs-websocket").mkdir(parents=True)
(K / "basic/profiles/T").mkdir(parents=True)
(K / "basic/scenes").mkdir(parents=True)
(K / "basic/scenes/T.json").write_text(json.dumps({
    "name": "T", "current_scene": "Szene", "current_program_scene": "Szene",
    "scene_order": [{"name": "Szene"}],
    "sources": [{"id": "scene", "versioned_id": "scene", "name": "Szene", "settings": {"items": []}}]}))
(K / "plugin_config/obs-websocket/config.json").write_text(json.dumps({
    "alerts_enabled": False, "auth_required": True, "first_load": False, "server_enabled": True,
    "server_password": PASSWORT, "server_port": PORT}))
ini = ("[General]\nFirstRun=true\nEnableAutoUpdates=false\nConfirmOnExit=false\n[Basic]\nProfile=T\nProfileDir=T\n"
       "SceneCollection=T\nSceneCollectionFile=T\n[BasicWindow]\nSysTrayEnabled=true\nSysTrayWhenStarted=false\n"
       "WarnBeforeStartingStream=false\nWarnBeforeStoppingStream=false\n")
(K / "global.ini").write_text(ini)
(K / "user.ini").write_text(ini)
(K / "basic/profiles/T/basic.ini").write_text(
    "[General]\nName=T\n[Video]\nBaseCX=640\nBaseCY=360\nOutputCX=640\nOutputCY=360\nFPSCommon=30\n")
(K / "basic/profiles/T/service.json").write_text(json.dumps(
    {"type": "rtmp_custom", "settings": {"server": EMPFAENGER, "key": "test", "use_auth": False}}))

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtWidgets import QApplication  # noqa: E402

from openregie import einstellungen  # noqa: E402
from openregie.geheimspeicher import Arbeitsspeicher  # noqa: E402
from openregie.obs.motor import ObsMotor  # noqa: E402
from openregie.obs.verbindung import ObsVerbindung, Sendung  # noqa: E402
from openregie.obs.vorschau import Vorschau  # noqa: E402
from openregie.obs.zugang import Zugang  # noqa: E402
from openregie.oberflaeche.hauptfenster import Hauptfenster  # noqa: E402
from openregie.twitch.konto import TwitchKonto  # noqa: E402
from openregie.uno.verwaltung import UnoVerwaltung  # noqa: E402
from tests.hilfen import groesste_pause_ms, warte, warte_bis  # noqa: E402

app = QApplication([])
E = einstellungen.lade()
t = E.texte
ergebnisse = []


def pruef(name, ok, info=""):
    ergebnisse.append((name, bool(ok)))
    print(("OK    " if ok else "FEHLER"), name, info, flush=True)


umgebung = dict(os.environ, XDG_CONFIG_HOME=S)
umgebung.pop("QT_QPA_PLATFORM", None)


def obs_starten():
    return subprocess.Popen(["obs", "--multi", "--minimize-to-tray", "--disable-shutdown-check"], env=umgebung,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def empfaenger_starten():
    return subprocess.Popen(["ffmpeg", "-loglevel", "error", "-listen", "1", "-i", EMPFAENGER + "/test",
                             "-f", "null", "-"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


obs = obs_starten()
rtmp = empfaenger_starten()

oe = einstellungen.Bereich("obs", dict(E.obs.als_dict(), adresse="127.0.0.1", neu_verbinden_sekunden=1,
                                       szenensammlung=""))
v = ObsVerbindung(oe, t, zugang_finden=lambda: Zugang(port=PORT, passwort=PASSWORT), obs_laeuft=lambda: True)
m = ObsMotor(oe, t, v, obs_laeuft=lambda: True)
vs = Vorschau(v, E.vorschau)
speicher = Arbeitsspeicher()
uno = UnoVerwaltung(E.uno, t, speicher)  # ohne Uno-Projekt: keine Anfragen an Uno
twitch = TwitchKonto(E.twitch, t, speicher)
f = Hauptfenster(E, v, vs, m, uno, twitch)
f.resize(1920, 1080)
f.show()
knopf, licht = f.knopf_stream, f.on_air

# Jede Anfrage an OBS mitschreiben
gesendet = []
_anfrage = v.anfrage


def mitschreiben(typ, daten=None, rueckruf=None):
    gesendet.append(typ)
    _anfrage(typ, daten, rueckruf)


v.anfrage = mitschreiben
m.starten()
pruef("Test-OBS gestartet und verbunden", warte_bis(lambda: v.verbunden and knopf.isEnabled(), 60000))
if not v.verbunden:
    obs.kill()
    rtmp.kill()
    sys.exit(1)

antworten = {}


def frag(typ, daten=None):
    """Direkt an OBS – so, als würde jemand in OBS selbst klicken."""
    antworten.pop(typ, None)
    _anfrage(typ, daten, lambda ok, d, fe: antworten.__setitem__(typ, (ok, d, fe)))
    warte_bis(lambda: typ in antworten, 8000)
    return antworten.get(typ, (False, {}, "keine Antwort"))


def ziel(art, einstellungen_):
    ok, _, fe = frag("SetStreamServiceSettings", {"streamServiceType": art, "streamServiceSettings": einstellungen_})
    return ok


def klick():
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    QTest.mouseClick(knopf, Qt.MouseButton.LeftButton)


def bytes_gesendet():
    ok, d, _ = frag("GetStreamStatus")
    return int(d.get("outputBytes") or 0)


fragen = []
f.stream_knopf.frage_beenden = lambda: fragen.append("ja") or True
print(f"      OBS {frag('GetVersion')[1].get('obsVersion')} · {RUNDEN} Runden", flush=True)

# --- 1. und 2.: Starten, Nachfrage abbrechen, Beenden ------------------------------------
for runde in range(1, RUNDEN + 1):
    vorher = len(gesendet)
    klick()
    pruef(f"[{runde}] Klick: sofort „Verbinde …“ und gesperrt",
          knopf.text() == t.knopf_stream_verbinde and not knopf.isEnabled())
    pruef(f"[{runde}] live", warte_bis(lambda: v.sendung is Sendung.AN, 15000), v.sendung.value)
    neu = [x for x in gesendet[vorher:] if x not in ("GetStreamStatus", "GetSourceScreenshot",
                                                     "GetCurrentProgramScene")]
    pruef(f"[{runde}] erst Ziel geprüft, dann gestartet – keine Nachfrage beim Starten",
          neu[:2] == ["GetStreamServiceSettings", "StartStream"] and not fragen, neu)
    pruef(f"[{runde}] ON AIR rot, Knopf „Stream beenden“",
          licht.text.text() == t.on_air_an and E.farben.on_air_an in licht.styleSheet()
          and knopf.text() == t.knopf_stream_beenden and knopf.isEnabled())
    warte(1500)
    pruef(f"[{runde}] Empfänger bekommt Daten", bytes_gesendet() > 0)
    f.stream_knopf.frage_beenden = lambda: fragen.append("nein") or False
    klick()
    warte(1500)
    pruef(f"[{runde}] „Weiter streamen“: bleibt live, kein StopStream",
          fragen[-1:] == ["nein"] and frag("GetStreamStatus")[1].get("outputActive") is True
          and "StopStream" not in gesendet[vorher:])
    f.stream_knopf.frage_beenden = lambda: fragen.append("ja") or True
    klick()
    pruef(f"[{runde}] Beenden mit Nachfrage", fragen[-1:] == ["ja"])
    frei = warte_bis(lambda: knopf.text() == t.knopf_stream_starten and knopf.isEnabled(), 10000)
    # Echtes OBS meldet nach „gestoppt“ noch ~130 ms „läuft“: genau da absichtlich nachfragen –
    # ON AIR darf trotzdem nicht wieder rot werden
    wieder_rot = []
    beobachter = lambda s_: wieder_rot.append(s_.value) if s_ is not Sendung.AUS else None  # noqa: E731
    v.sendung_geaendert.connect(beobachter)
    for _ in range(5):
        v.stream_status_pruefen()
        warte(40)
    obs_aus = warte_bis(lambda: frag("GetStreamStatus")[1].get("outputActive") is False, 3000)
    warte(500)
    v.sendung_geaendert.disconnect(beobachter)
    pruef(f"[{runde}] aus, ON AIR „NICHT LIVE“, Knopf „Stream starten“, nicht wieder rot",
          frei and licht.text.text() == t.on_air_aus and obs_aus and not wieder_rot,
          f"Knopf „{knopf.text()}“ frei={knopf.isEnabled()}, Licht „{licht.text.text()}“, OBS aus={obs_aus}, "
          f"danach {wieder_rot}")
    pruef(f"[{runde}] keine Meldung", f.meldungsleiste.isHidden(), f.meldungstext.text())
    fragen.clear()
    rtmp.wait(10)  # ffmpeg hört nach einer Verbindung auf – neu starten
    rtmp = empfaenger_starten()
    warte(800)

# --- 3. Start/Stopp direkt in OBS ----------------------------------------------------------
for runde in range(1, RUNDEN + 1):
    frag("StartStream")
    pruef(f"[{runde}] in OBS gestartet → Knopf „Stream beenden“, ON AIR",
          warte_bis(lambda: knopf.text() == t.knopf_stream_beenden and licht.text.text() == t.on_air_an, 15000))
    warte(800)
    frag("StopStream")
    pruef(f"[{runde}] in OBS gestoppt → Knopf „Stream starten“",
          warte_bis(lambda: knopf.text() == t.knopf_stream_starten and knopf.isEnabled(), 10000))
    rtmp.wait(10)
    rtmp = empfaenger_starten()
    warte(800)

# --- 4. Kein Stream-Key ---------------------------------------------------------------------
ziel("rtmp_common", {"service": "Twitch", "server": "auto", "key": ""})
for runde in range(1, RUNDEN + 1):
    vorher = len(gesendet)
    klick()
    pruef(f"[{runde}] ohne Key: Meldung „Stream-Key fehlt“",
          warte_bis(lambda: f.meldungstext.text() == t.stream_meldung_kein_key and f.meldungsleiste.isVisible()
                    and knopf.isEnabled(), 5000), f.meldungstext.text())
    pruef(f"[{runde}] ohne Key: KEIN StartStream an OBS", "StartStream" not in gesendet[vorher:])
    pruef(f"[{runde}] ohne Key: Knopf wieder frei, nicht live",
          knopf.isEnabled() and knopf.text() == t.knopf_stream_starten and licht.text.text() == t.on_air_aus)
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
QTest.mouseClick(f.knopf_verstanden, Qt.MouseButton.LeftButton)
pruef("„Verstanden“ räumt die Meldung weg", f.meldungsleiste.isHidden())

# --- 5. Server nicht erreichbar ---------------------------------------------------------------
ziel("rtmp_custom", {"server": NIEMAND, "key": "test"})
for runde in range(1, RUNDEN + 1):
    klick()
    pruef(f"[{runde}] Server weg: Meldung „konnte nicht starten“",
          warte_bis(lambda: f.meldungstext.text() == t.stream_meldung_fehlstart and knopf.isEnabled(), 15000),
          f.meldungstext.text())
    pruef(f"[{runde}] Server weg: nie rot gewesen", licht.text.text() == t.on_air_aus)
ziel("rtmp_custom", {"server": EMPFAENGER, "key": "test"})

# --- 6. Empfänger bricht weg ------------------------------------------------------------------
verlauf = []
v.sendung_geaendert.connect(lambda s_: verlauf.append(s_.value))
for runde in range(1, RUNDEN + 1):
    verlauf.clear()
    klick()
    pruef(f"[{runde}] live (für Abbruch)", warte_bis(lambda: v.sendung is Sendung.AN, 15000))
    pruef(f"[{runde}] alte Meldung weg, sobald live", f.meldungsleiste.isHidden())
    warte(800)
    rtmp.kill()
    pruef(f"[{runde}] Empfänger weg → „VERBINDE …“, nicht rot",
          warte_bis(lambda: v.sendung is Sendung.WIEDER, 15000)
          and licht.text.text() == t.on_air_wieder and E.farben.on_air_an not in licht.styleSheet(),
          f"Verlauf {verlauf}")
    pruef(f"[{runde}] beenden geht trotzdem", knopf.isEnabled() and knopf.text() == t.knopf_stream_beenden)
    klick()
    pruef(f"[{runde}] beendet", warte_bis(lambda: knopf.text() == t.knopf_stream_starten and knopf.isEnabled(),
                                          15000))
    rtmp = empfaenger_starten()
    warte(800)

# --- Flüssig? -----------------------------------------------------------------------------------
klick()
pause = groesste_pause_ms(1500)
pruef("Regiepult flüssig beim Starten", pause < 150, f"{pause:.0f} ms")
warte_bis(lambda: v.sendung is Sendung.AN, 15000)

# --- 7. OBS wird mitten im Stream beendet -----------------------------------------------------
pruef("live vor dem Beenden von OBS", v.sendung is Sendung.AN)
obs.terminate()
pruef("OBS weg: Knopf grau", warte_bis(lambda: not knopf.isEnabled(), 15000))
pruef("OBS weg: ON AIR nicht rot", licht.text.text() == t.on_air_aus)
pruef("OBS weg: Meldung zur Verbindung", f.meldungsleiste.isVisible(), f.meldungstext.text())
obs.wait(20)
rtmp.kill()
rtmp = empfaenger_starten()
obs = obs_starten()
pruef("OBS wieder da: Knopf „Stream starten“",
      warte_bis(lambda: knopf.isEnabled() and knopf.text() == t.knopf_stream_starten, 60000), knopf.text())
klick()
pruef("nach Neustart von OBS: starten geht", warte_bis(lambda: v.sendung is Sendung.AN, 15000))
f.stream_knopf.frage_beenden = lambda: True
klick()
warte_bis(lambda: v.sendung is Sendung.AUS, 10000)

# --- OBS-Protokoll: kein Fehlerfenster ----------------------------------------------------------
v.beenden()
obs.terminate()
obs.wait(20)
rtmp.kill()
protokolle = sorted((K / "logs").glob("*.txt"))
text = "\n".join(p.read_text(errors="replace") for p in protokolle)
pruef("OBS-Protokoll: kein „failed to start“ (kein OBS-Fehlerfenster)",
      "failed to start" not in text, f"{text.count('failed to start')}×")

f._schliessen_erlaubt = True
f.close()
gut = sum(ok for _, ok in ergebnisse)
print(f"\n{gut} von {len(ergebnisse)} Prüfungen OK", flush=True)
sys.exit(0 if gut == len(ergebnisse) else 1)
