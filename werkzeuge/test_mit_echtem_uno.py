"""Test mit dem echten Overlays.uno – prüft OpenRegie gegen ein echtes Einzel-Uno
(gebaut für „Countdown | Circles“).

ACHTUNG: Der Test blendet das Overlay kurz (3 Sekunden) EIN und wieder aus, startet,
hält und setzt den Countdown zurück und ändert die Dauer kurz. Am Ende ist alles wieder
ausgeblendet, die Dauer wie vorher und der Countdown zurückgesetzt.
Nicht während eines Streams laufen lassen!

Die Adresse steht NUR in daten/geheim.toml (wird nicht in Git gespeichert):
    [uno]
    adresse = "https://app.overlays.uno/apiv2/controlapps/…/api"

Aufruf:  python3 werkzeuge/test_mit_echtem_uno.py --ja-schalten
"""
import json, sys, tomllib, urllib.request
from pathlib import Path
ORDNER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ORDNER))
if "--ja-schalten" not in sys.argv:
    print(__doc__)
    sys.exit(1)
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from tests.hilfen import app, warte, warte_bis
from openregie import einstellungen
from openregie.geheimspeicher import Arbeitsspeicher
from openregie.uno.verwaltung import UnoVerwaltung, token_aus_text
from openregie.uno import einzel
app()
adresse = tomllib.load(open(ORDNER / "daten" / "geheim.toml", "rb"))["uno"]["adresse"]
t = token_aus_text(adresse)
E = einstellungen.lade()
u = UnoVerwaltung(E.uno, E.texte, Arbeitsspeicher())
def roh():
    d = json.loads(urllib.request.urlopen(f"https://app.overlays.uno/apiv2/controlapps/{t}/control", timeout=15).read())
    zeigen = next((s["payload"].get("ShowOverlay") for s in d if "ShowOverlay" in s["payload"]), None)
    return (" ".join(f"{s['subCompositionName']}:{s['state']}" for s in d)
            + f" Active={d[0]['payload'].get('Active')} ShowOverlay={zeigen}")
def warten(fn, *a):
    r = []; fn(*a, lambda ok, f: r.append((ok, f))); warte_bis(lambda: r, 15000); return r[0] if r else ("keine Antwort", "")
erg = []
def pruef(name, ok, info=""):
    erg.append(ok); print(("OK    " if ok else "FEHLER"), name, info, flush=True)

r = []; u.projekt_hinzufuegen(adresse, lambda ok, m: r.append((ok, m))); warte_bis(lambda: r, 20000)
pruef("Einfügen", r and r[0][0], r[0][1] if r else "")
o = next(iter(u.overlays.values()))
pruef("Name von Uno", bool(o.name), o.name)
pruef("Bauplan: 3 Teile + Active", len(o.bauplan.ein_teile) == 3 and o.bauplan.aktiv_feld == "Active")
DAUER = o.dauer or 0  # die eingestellte Dauer, wird am Ende wiederhergestellt
pruef("Countdown erkannt", o.hat_countdown and o.dauer is not None, f"Dauer {o.dauer} s = {einzel.zeit_text(DAUER*1000)}")
pruef("Textfelder gelesen", bool(o.felder), str([(f.titel, f.wert) for f in o.felder]))
pruef("Vorschaubild-Adresse", o.vorschaubild.startswith("https://"))
b = []; u.bild_laden(o, b.append); warte_bis(lambda: b, 15000)
pruef("Vorschaubild geladen", bool(b and b[0]), f"{len(b[0]) if b and b[0] else 0} Bytes")
pruef("Zustand gelesen", o.sichtbar is not None, roh())

pruef("Einblenden", warten(u.sichtbar_setzen, o, True)[0] is True)
warte(800); z = roh()
pruef("  Haupt/Content/Countdown In + Active + ShowOverlay", "mainComposition:In" in z and "Content:In" in z
      and "Countdown:In" in z and "Active=True" in z and "ShowOverlay=True" in z, z)
warte(3000)
pruef("Ausblenden", warten(u.sichtbar_setzen, o, False)[0] is True)
warte(800); z = roh()
pruef("  Uno-Schalter ShowOverlay aus (blendet in der Mitte aus)", "ShowOverlay=False" in z, z)

pruef("Countdown zurück", warten(u.timer_befehl, o, "reset")[0] is True, einzel.zeit_text(o.restzeit_ms()))
pruef("Countdown Start", warten(u.timer_befehl, o, "play")[0] is True and o.timer.get("isRunning"))
warte(3000)
rest_lokal = o.restzeit_ms()
pruef("Pause", warten(u.timer_befehl, o, "pause")[0] is True and not o.timer.get("isRunning"),
      f"Restzeit {einzel.zeit_text(o.restzeit_ms())} (lokal vorher {einzel.zeit_text(rest_lokal)})")
pruef("Zählt richtig (ca. 3–5 s weniger)", (DAUER - 5) * 1000 <= o.restzeit_ms() <= (DAUER - 2.5) * 1000,
      str(o.restzeit_ms()))
pruef("Dauer +1 Min", warten(u.dauer_setzen, o, DAUER + 60)[0] is True and o.dauer == DAUER + 60, str(o.dauer))
pruef("Dauer zurück", warten(u.dauer_setzen, o, DAUER)[0] is True and o.dauer == DAUER, str(o.dauer))
pruef("Countdown zurück", warten(u.timer_befehl, o, "reset")[0] is True and o.restzeit_ms() == DAUER * 1000,
      einzel.zeit_text(o.restzeit_ms()))

# --- Build 1.2.2: der gemeldete Fehler (Countdown seit Tagen abgelaufen, 00:00, „Start“ ging nicht) ---
def patch(liste):
    t_ = urllib.request.Request(f"https://app.overlays.uno/apiv2/controlapps/{t}/control", method="PATCH",
                                data=json.dumps(liste).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(t_, timeout=15).read())
teil, feld = o.bauplan.timer
jetzt = int(__import__("time").time() * 1000)
patch([{"subCompositionId": teil, "payload": {feld: {"UTC": jetzt, "isRunning": False, "value": 520_647_486}}}])
r = []; u.felder_laden(o, lambda ok, f: r.append(ok)); warte_bis(lambda: r, 15000)
pruef("Abgelaufen nachgestellt (wie bei Kevin)", o.restzeit_ms() == 0, einzel.zeit_text(o.restzeit_ms()))
pruef("Neu starten", warten(u.timer_befehl, o, "neu")[0] is True and o.timer.get("isRunning"))
pruef("  beginnt von vorn", DAUER * 1000 - 3000 <= o.restzeit_ms() <= DAUER * 1000, einzel.zeit_text(o.restzeit_ms()))
pruef("Pause", warten(u.timer_befehl, o, "pause")[0] is True and not o.timer.get("isRunning"))

# Zwei Änderungen direkt hintereinander: die zweite muss bei Uno gelten (vorher konnte die erste überholen)
for runde in range(3):
    r = []
    u.dauer_setzen(o, DAUER - 60, lambda ok, f: r.append(ok))
    u.countdown_zeit_setzen(o, 330 + runde, lambda ok, f: r.append(ok))
    warte_bis(lambda: len(r) == 2, 20000)
    warte(1500)
    echt = json.loads(urllib.request.urlopen(f"https://app.overlays.uno/apiv2/controlapps/{t}/control",
                                             timeout=15).read())
    begin = next(s_["payload"].get("BeginTime") for s_ in echt if "BeginTime" in s_["payload"])
    pruef(f"Schnell hintereinander, Runde {runde + 1}: zuletzt Getipptes gilt", r == [True, True]
          and begin == 330 + runde and o.dauer == 330 + runde, f"Uno {begin}, OpenRegie {o.dauer}")
pruef("Dauer wieder wie vorher", warten(u.dauer_setzen, o, DAUER)[0] is True and o.dauer == DAUER, str(o.dauer))
pruef("Countdown zurück", warten(u.timer_befehl, o, "reset")[0] is True and o.restzeit_ms() == DAUER * 1000,
      einzel.zeit_text(o.restzeit_ms()))
u.beenden()
print(f"\n{sum(map(bool, erg))} von {len(erg)} Prüfungen bestanden.  Ende: {roh()}")
sys.exit(0 if all(erg) else 1)
