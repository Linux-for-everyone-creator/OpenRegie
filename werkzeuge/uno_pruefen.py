"""Fragt ein echtes Uno, welche Befehle es versteht – ohne etwas zu verändern.

Die Adresse steht NUR in daten/geheim.toml (wird nicht in Git gespeichert):
    [uno]
    adresse = "https://app.overlays.uno/apiv2/controlapps/…/api"

Aufruf:  python3 werkzeuge/uno_pruefen.py            → nur Lese-Befehle (Get…)
         python3 werkzeuge/uno_pruefen.py --zeigen   → zusätzlich Ein- und wieder Ausblenden

Der geheime Teil der Adresse wird nie ausgegeben. Zwischen den Anfragen wird
eine Sekunde gewartet, damit das Uno-Limit nicht überschritten wird.
"""
import json
import sys
import time
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from openregie.uno.verwaltung import token_aus_text  # noqa: E402

DATEI = Path(__file__).resolve().parent.parent / "daten" / "geheim.toml"
# Nur lesende Befehle. Unbekannte beantwortet Uno mit 400 „Invalid command“ – harmlos.
LESEN = ["GetOverlays", "GetOverlayModels", "GetOverlayContent", "GetOverlay", "GetOverlayState",
         "GetOverlayStatus", "GetStatus", "GetState", "GetControlAppInfo", "GetModel", "GetContent"]


def senden(adresse, token, befehl):
    anfrage = urllib.request.Request(adresse, data=json.dumps(befehl).encode(), method="PUT",
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(anfrage, timeout=15) as antwort:
            code, roh, kopf = antwort.status, antwort.read(), antwort.headers
    except urllib.error.HTTPError as fehler:
        code, roh, kopf = fehler.code, fehler.read(), fehler.headers
    text = roh.decode("utf-8", "replace").replace(token, "<TOKEN>")
    limit = {k: v for k, v in kopf.items() if "ratelimit" in k.lower()}
    return code, text, limit


def main():
    try:
        adresse_text = tomllib.loads(DATEI.read_text(encoding="utf-8"))["uno"]["adresse"]
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        print(f"Bitte die Uno-Adresse in {DATEI} eintragen (siehe Beschreibung oben in dieser Datei).")
        return 1
    token = token_aus_text(adresse_text)
    if not token:
        print("In daten/geheim.toml steht keine gültige Uno-Adresse.")
        return 1
    adresse = f"https://app.overlays.uno/apiv2/controlapps/{token}/api"
    befehle = [{"command": b} for b in LESEN]
    if "--zeigen" in sys.argv:
        befehle += [{"command": "ShowOverlay"}, {"command": "GetOverlayContent"}, {"command": "HideOverlay"}]
    for befehl in befehle:
        code, text, limit = senden(adresse, token, befehl)
        print(f"\n### {json.dumps(befehl)} → HTTP {code}  {limit if limit else ''}")
        try:
            print(json.dumps(json.loads(text), indent=2, ensure_ascii=False)[:6000])
        except ValueError:
            print(text[:2000])
        time.sleep(1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
