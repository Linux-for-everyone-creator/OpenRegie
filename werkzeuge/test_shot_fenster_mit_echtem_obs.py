"""Build 1.2.2 mit echtem OBS prüfen: „Shot hinzufügen“ / „Quelle hinzufügen“ als eigenes Fenster.

Startet ein eigenes, unsichtbares Test-OBS (Wegwerf-Ordner, eigener Port – deine OBS-Einstellungen
bleiben unberührt) und das echte Regiepult (unsichtbar) und prüft je RUNDEN Runden lang:
  - Klick auf „+“ → eigenes Fenster, sperrt das Regiepult, rechts bleibt, was war
  - Abbrechen über Knopf, Esc und Kreuz → nichts angelegt
  - „Bild“ wählen, anlegen → Shot steht in OBS, Fenster geht von selbst zu, Shot ist zum Bearbeiten offen
  - „Quelle hinzufügen“ im Shot → eigenes Fenster → Bild landet in genau diesem Shot
  - das Regiepult bleibt flüssig, solange das Fenster offen ist
Nur „Bild“ – Bildschirm/Spiel/Reactions öffnen das Auswahlfenster des Systems, Kamera schaltet die Kamera ein.

Aufruf (aus dem OpenRegie-Ordner):  python3 werkzeuge/test_shot_fenster_mit_echtem_obs.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RUNDEN = 5

S = tempfile.mkdtemp(prefix="openregie-obs-shotfenster-")
K = Path(S) / "obs-studio"
(K / "plugin_config/obs-websocket").mkdir(parents=True)
(K / "basic/profiles/T").mkdir(parents=True)
(K / "basic/scenes").mkdir(parents=True)
(K / "basic/scenes/T.json").write_text(json.dumps({
    "name": "T", "current_scene": "Szene", "current_program_scene": "Szene",
    "scene_order": [{"name": "Szene"}],
    "sources": [{"id": "color_source_v3", "versioned_id": "color_source_v3", "name": "Farbe",
                 "settings": {"color": 0xFF50B93F, "width": 1280, "height": 720}},
                {"id": "scene", "versioned_id": "scene", "name": "Szene",
                 "settings": {"items": [{"name": "Farbe", "visible": True, "id": 1}], "id_counter": 1}}]}))
(K / "plugin_config/obs-websocket/config.json").write_text(json.dumps({
    "alerts_enabled": False, "auth_required": True, "first_load": False, "server_enabled": True,
    "server_password": "testpasswort12", "server_port": 4479}))
ini = ("[General]\nFirstRun=true\nEnableAutoUpdates=false\nConfirmOnExit=false\n[Basic]\nProfile=T\nProfileDir=T\n"
       "SceneCollection=T\nSceneCollectionFile=T\n[BasicWindow]\nSysTrayEnabled=true\nSysTrayWhenStarted=false\n")
(K / "global.ini").write_text(ini)
(K / "user.ini").write_text(ini)
(K / "basic/profiles/T/basic.ini").write_text(
    "[General]\nName=T\n[Video]\nBaseCX=1280\nBaseCY=720\nOutputCX=1280\nOutputCY=720\nFPSCommon=30\n")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from openregie import einstellungen  # noqa: E402
from openregie.geheimspeicher import Arbeitsspeicher  # noqa: E402
from openregie.obs import vorlagen  # noqa: E402
from openregie.obs.motor import ObsMotor  # noqa: E402
from openregie.obs.verbindung import ObsVerbindung  # noqa: E402
from openregie.obs.vorschau import Vorschau  # noqa: E402
from openregie.obs.zugang import Zugang  # noqa: E402
from openregie.oberflaeche.hauptfenster import Hauptfenster  # noqa: E402
from openregie.twitch.konto import TwitchKonto  # noqa: E402
from openregie.uno.verwaltung import UnoVerwaltung  # noqa: E402
from tests.hilfen import groesste_pause_ms, warte, warte_bis  # noqa: E402
from tests.test_fenster import klick  # noqa: E402

app = QApplication([])
E = einstellungen.lade()
ergebnisse = []


def pruef(name, ok, info=""):
    ergebnisse.append((name, bool(ok)))
    print(("OK    " if ok else "FEHLER"), name, info, flush=True)


bild_datei = str(Path(S) / "testbild.png")
testbild = QImage(640, 360, QImage.Format.Format_RGB32)
testbild.fill(QColor("#e5484d"))
testbild.save(bild_datei)

umgebung = dict(os.environ, XDG_CONFIG_HOME=S)
umgebung.pop("QT_QPA_PLATFORM", None)
obs = subprocess.Popen(["obs", "--multi", "--minimize-to-tray", "--disable-shutdown-check"], env=umgebung,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    oe = einstellungen.Bereich("obs", dict(E.obs.als_dict(), adresse="127.0.0.1", szenensammlung=""))
    v = ObsVerbindung(oe, E.texte, zugang_finden=lambda: Zugang(port=4479, passwort="testpasswort12"),
                      obs_laeuft=lambda: True)
    m = ObsMotor(oe, E.texte, v, obs_laeuft=lambda: True)
    vs = Vorschau(v, E.vorschau)
    uno = UnoVerwaltung(E.uno, E.texte, Arbeitsspeicher())  # ohne Uno-Projekt: kein Verkehr zu Uno
    tw = TwitchKonto(E.twitch, E.texte, Arbeitsspeicher())
    f = Hauptfenster(E, v, vs, m, uno, tw)
    f.resize(1903, 971)  # Kevins Bildschirm
    f.show()
    v.starten()
    pruef("Test-OBS gestartet und verbunden", warte_bis(lambda: v.verbunden and v.szene, 60000))
    if not v.verbunden:
        sys.exit(1)
    l, n, w = f.shot_leiste, f.shot_neu, f.shot_neu_fenster
    n._datei_waehlen = lambda: bild_datei  # statt des Datei-Fensters
    pruef("Shot-Leiste zeigt die Szene", warte_bis(lambda: l.kachel("Szene") is not None and l.plus.isVisible(), 8000))

    def offen(titel):
        return (warte_bis(lambda: w.isVisible(), 3000) and w.isWindow() and w.isModal()
                and QApplication.activeModalWidget() is w and w.windowTitle() == titel)

    def plus():
        """„+“ anklicken – steht es auf einer anderen Seite der Leiste, erst mit ▶ dorthin blättern."""
        for _ in range(10):
            if l.plus.isVisible():
                break
            klick(l.vor)
        klick(l.plus)

    def zu():
        return warte_bis(lambda: not w.isVisible(), 5000) and QApplication.activeModalWidget() is None

    for runde in range(1, RUNDEN + 1):
        # 1) abbrechen auf drei Wegen – nichts wird angelegt
        for weg in ("Abbrechen-Knopf", "Esc", "Kreuz"):
            vorher_rechts, vorher_shots = f.bedienfelder.currentWidget(), [s.name for s in f.quellen.shots]
            plus()
            pruef(f"[{runde}] „+“ → eigenes Fenster, sperrt ({weg})", offen(E.texte.shot_neu_fenster_titel))
            pruef(f"[{runde}]   alle Wahlmöglichkeiten da, auch Reactions",
                  set(n.zweck_knoepfe) == set(vorlagen.ZWECKE) and "reactions" in n.zweck_knoepfe)
            pruef(f"[{runde}]   rechts bleibt, was war", f.bedienfelder.currentWidget() is vorher_rechts)
            klick(n.zweck_knoepfe["bild"])
            if weg == "Abbrechen-Knopf":
                klick(n.zurueck)
            elif weg == "Esc":
                QTest.keyClick(w, Qt.Key.Key_Escape)
            else:
                w.close()
            pruef(f"[{runde}]   zu ({weg})", zu())
            warte(500)
            pruef(f"[{runde}]   nichts angelegt", [s.name for s in f.quellen.shots] == vorher_shots)

        # 2) flüssig, solange offen
        plus()
        offen(E.texte.shot_neu_fenster_titel)
        pause = groesste_pause_ms(1500)
        pruef(f"[{runde}] Regiepult bleibt flüssig, während das Fenster offen ist", pause < 150, f"{pause:.0f} ms")

        # 3) Bild-Shot anlegen
        vorher = {s.name for s in f.quellen.shots}
        klick(n.zweck_knoepfe["bild"])
        klick(n.anlegen)
        pruef(f"[{runde}] Bild-Shot in OBS angelegt",
              warte_bis(lambda: len({s.name for s in f.quellen.shots} - vorher) == 1, 10000))
        neu = ({s.name for s in f.quellen.shots} - vorher or {""}).pop()
        pruef(f"[{runde}]   Fenster geht von selbst zu", zu())
        pruef(f"[{runde}]   neuer Shot rechts zum Bearbeiten",
              warte_bis(lambda: f.bedienfelder.currentWidget() is f.shot_bedienfeld
                        and f.shot_bedienfeld.shot_name == neu, 5000), neu)
        pruef(f"[{runde}]   nicht live geschaltet", v.szene == "Szene", v.szene)

        # 4) Quelle in diesen Shot
        klick(f.shot_bedienfeld.knopf_quelle_neu)
        pruef(f"[{runde}] „Quelle hinzufügen“ → eigenes Fenster", offen(E.texte.quelle_neu_fenster_titel))
        pruef(f"[{runde}]   Auswahl wie bisher", tuple(n.art_knoepfe) == vorlagen.ARTEN_ZUM_HINZUFUEGEN)
        pruef(f"[{runde}]   rechts bleibt der Shot", f.bedienfelder.currentWidget() is f.shot_bedienfeld)
        shot = f.quellen.shot(neu)
        anzahl = len(shot.quellen) if shot else -1
        klick(n.art_knoepfe["bild"])
        klick(n.anlegen)
        pruef(f"[{runde}]   Bild in genau diesem Shot",
              warte_bis(lambda: (s := f.quellen.shot(neu)) is not None and len(s.quellen) == anzahl + 1, 10000))
        pruef(f"[{runde}]   Fenster zu", zu())

        # 5) aufräumen: Bearbeiten beenden
        l.bearbeiten_setzen(False)
        warte(300)

    vs.anhalten()
    uno.beenden()
    tw.beenden()
    v.beenden()
    f._schliessen_erlaubt = True
    f.close()
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
