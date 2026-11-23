"""Einzel-Unos verstehen (z. B. ein einzelnes „Countdown | Circles“).

Einzel-Unos sind technisch „Control Apps“ von Singular.live (darauf baut Overlays.uno auf).
Die Befehle über „…/api“ (ShowOverlay usw.) nehmen sie zwar an, zeigen aber NICHTS an.
Gesteuert werden sie über die Singular-Schnittstelle derselben Adresse:

  GET   …/controlapps/<token>           → Name, Vorschaubild, Ausgabe-Adresse
  GET   …/controlapps/<token>/model     → Bauplan: Teile („Subkompositionen“) und Felder
  GET   …/controlapps/<token>/control   → aktueller Zustand: pro Teil "state" (In/Out1/Out2) + Werte
  PATCH …/controlapps/<token>/control   → ändern, z. B. [{"subCompositionId": "…", "state": "In"}]

Mit dem echten Uno geprüft (14.11.2026):
  - Der eigentliche Ein/Aus-Schalter ist das Häkchen „ShowOverlay“ (im Teil „Content“).
    Dasselbe setzt auch der Uno-Befehl HideOverlay bzw. der Aus-Schalter in Uno.
    Mit „ShowOverlay“ aus ist NICHTS zu sehen.
  - Der volle Auftritt (Hintergrund + Zahlen) kommt nur, wenn zusätzlich der Hauptteil UND
    alle Teile, die im Bauplan von Haus aus auf „In“ stehen, auf „In“ gehen und das Häkchen
    „Active“ im Hauptteil an ist. Ohne das sieht man nur die Kreise ohne Zahlen.
  - Ausblenden NUR über „ShowOverlay“ aus: dann blendet alles zusammen sanft an Ort und Stelle
    (in der Mitte) aus. Werden stattdessen die Teile auf „Out“ gestellt, verschwindet der
    Hintergrund sofort und die Kreise bleiben stehen (mit Standbildern aus OBS geprüft, 14.11.2026).
  - Zeitgeber („timecontrol“) zählen die ABGELAUFENE Zeit in Millisekunden:
    {"value": abgelaufen_bis_UTC, "UTC": Startzeitpunkt, "isRunning": bool}.
    Steuern mit {"command": "play" | "pause" | "reset" | "start"}.
  - Die Dauer steht in „BeginTime“ in Sekunden (17980 = 04:59:40).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

AKTIV_FELD = "Active"
ZEIGEN_NAMEN = ("showoverlay",)  # Uno-eigener Ein/Aus-Schalter
DAUER_NAMEN = ("begintime", "duration", "dauer", "countdowntime", "starttime")
TEXT_ARTEN = ("text", "textarea")


@dataclass
class Feld:
    """Ein Textfeld, das man in OpenRegie ändern kann."""
    kennung: str  # technischer Name bei Uno, z. B. "Message"
    titel: str  # Anzeigename
    wert: str
    teil: str = ""  # Einzel-Uno: Kennung des Teils (Subkomposition); sonst leer


@dataclass
class Bauplan:
    haupt: str  # Kennung des Hauptteils
    ein_teile: list[str] = field(default_factory=list)  # diese Teile gehen beim Einblenden auf „In“
    aktiv_feld: str | None = None  # Häkchen im Hauptteil, das mit an/aus geht
    zeigen_feld: tuple[str, str] | None = None  # (Teil, Feld) des Uno-eigenen Ein/Aus-Schalters
    timer: tuple[str, str] | None = None  # (Teil, Feld) des Zeitgebers
    dauer: tuple[str, str] | None = None  # (Teil, Feld) der Dauer in Sekunden
    textfelder: list[tuple[str, str, str]] = field(default_factory=list)  # (Teil, Feld, Titel)


def _felder(teil: dict) -> list[dict]:
    return [f for f in (teil.get("model") or []) if isinstance(f, dict) and f.get("id")]


def bauplan_lesen(model) -> Bauplan | None:
    """GET …/model → Bauplan. None, wenn die Antwort nicht passt."""
    if isinstance(model, list):
        model = model[0] if model else None
    if not isinstance(model, dict) or not model.get("id"):
        return None
    plan = Bauplan(haupt=str(model["id"]))
    plan.ein_teile.append(plan.haupt)

    for f in _felder(model):
        if f.get("id") == AKTIV_FELD and f.get("type") == "checkbox":
            plan.aktiv_feld = AKTIV_FELD

    def durchgehen(teil: dict, sichtbar_mit: bool) -> None:
        kennung = str(teil["id"])
        felder = _felder(teil)
        for f in felder:
            art = f.get("type")
            if art == "checkbox" and str(f["id"]).lower() in ZEIGEN_NAMEN and plan.zeigen_feld is None:
                plan.zeigen_feld = (kennung, str(f["id"]))
            elif art == "timecontrol" and plan.timer is None:
                plan.timer = (kennung, str(f["id"]))
            elif art in TEXT_ARTEN:
                plan.textfelder.append((kennung, str(f["id"]), str(f.get("title") or f["id"])))
        if plan.timer and plan.timer[0] == kennung and plan.dauer is None:
            for f in felder:
                if f.get("type") == "number" and str(f["id"]).lower() in DAUER_NAMEN:
                    plan.dauer = (kennung, str(f["id"]))
        for unter in teil.get("subcompositions") or []:
            if not isinstance(unter, dict) or not unter.get("id"):
                continue
            # Teile, die von Haus aus „In“ stehen, gehören zum Einblenden dazu
            mit = sichtbar_mit and str(unter.get("state", "")).lower() == "in"
            if mit:
                plan.ein_teile.append(str(unter["id"]))
            durchgehen(unter, mit)

    durchgehen(model, True)
    return plan


def ein_teile_ergaenzen(plan: Bauplan, control) -> None:
    """Steht im Bauplan KEIN Teil von Haus aus auf „In“ (so meldet es Uno seit Ende November 2026 auch
    beim „Countdown | Circles“), gehören die Teile zum Einblenden, die beim ersten Lesen auf „In“ standen.
    Sonst blendet „Einblenden“ nur den Kreis ohne Zahlen ein."""
    if len(plan.ein_teile) > 1:
        return
    for kennung, teil in teile_lesen(control).items():
        if kennung not in plan.ein_teile and teil["state"].lower() == "in":
            plan.ein_teile.append(kennung)


def teile_lesen(control) -> dict[str, dict]:
    """GET …/control → {Teil-Kennung: {"state": …, "payload": {…}}}."""
    teile = {}
    for t in control if isinstance(control, list) else []:
        if isinstance(t, dict) and t.get("subCompositionId"):
            teile[str(t["subCompositionId"])] = {"state": str(t.get("state") or ""),
                                                 "payload": t.get("payload") or {}}
    return teile


def ist_sichtbar(teile: dict[str, dict], plan: Bauplan) -> bool | None:
    haupt = teile.get(plan.haupt)
    if haupt is None:
        return None
    if plan.zeigen_feld and wert(teile, plan.zeigen_feld) is False:
        return False  # Uno-Schalter aus: nichts zu sehen, egal wie die Teile stehen
    return haupt["state"].lower() == "in"


def wert(teile: dict[str, dict], teil_feld: tuple[str, str] | None):
    if not teil_feld:
        return None
    teil = teile.get(teil_feld[0])
    return None if teil is None else teil["payload"].get(teil_feld[1])


def textfelder_lesen(teile: dict[str, dict], plan: Bauplan) -> list[Feld]:
    felder = []
    for teil, kennung, titel in plan.textfelder:
        w = wert(teile, (teil, kennung))
        felder.append(Feld(kennung, titel, "" if w is None else str(w), teil))
    return felder


def ein_aus_befehl(plan: Bauplan, sichtbar: bool) -> list[dict]:
    """Der PATCH-Inhalt zum Ein- bzw. Ausblenden.

    Einblenden: Teile auf „In“, „Active“ an, Uno-Schalter „ShowOverlay“ an.
    Ausblenden: nur der Uno-Schalter aus – so blendet alles sanft an Ort und Stelle aus.
    (Ohne Uno-Schalter: Teile auf „Out“ und „Active“ aus.)
    """
    if not sichtbar and plan.zeigen_feld:
        teil, feld = plan.zeigen_feld
        return [{"subCompositionId": teil, "payload": {feld: False}}]
    zustand = "In" if sichtbar else "Out"
    befehl = []
    for kennung in plan.ein_teile:
        eintrag = {"subCompositionId": kennung, "state": zustand}
        if kennung == plan.haupt and plan.aktiv_feld:
            eintrag["payload"] = {plan.aktiv_feld: sichtbar}
        befehl.append(eintrag)
    if sichtbar and plan.zeigen_feld:
        teil, feld = plan.zeigen_feld
        eintrag = next((e for e in befehl if e["subCompositionId"] == teil), None)
        if eintrag is None:
            befehl.append({"subCompositionId": teil, "payload": {feld: True}})
        else:
            eintrag.setdefault("payload", {})[feld] = True
    return befehl


def dauer_sekunden(roh) -> int | None:
    try:
        return max(0, int(float(roh)))
    except (TypeError, ValueError):
        return None


def restzeit_ms(timer, dauer_s: int | None, jetzt_ms: float) -> int | None:
    """Wie viel Zeit der Countdown noch hat (Millisekunden)."""
    if dauer_s is None or not isinstance(timer, dict):
        return None
    try:
        abgelaufen = float(timer.get("value") or 0)
        if timer.get("isRunning"):
            abgelaufen += max(0.0, jetzt_ms - float(timer.get("UTC") or jetzt_ms))
    except (TypeError, ValueError):
        return None
    return int(max(0.0, dauer_s * 1000 - abgelaufen))


def hat_gezaehlt(timer) -> bool:
    """Ist der Zeitgeber schon gelaufen (läuft gerade, angehalten oder abgelaufen)?"""
    if not isinstance(timer, dict):
        return False
    if timer.get("isRunning"):
        return True
    try:
        return float(timer.get("value") or 0) > 0
    except (TypeError, ValueError):
        return True  # unklar: lieber zurücksetzen, damit die neue Zeit sicher stimmt


# Warum eine eingetippte Zeit nicht passt (die Oberfläche macht daraus einen Satz für Menschen)
ZEIT_LEER, ZEIT_FORMAT, ZEIT_UEBER_59, ZEIT_NULL, ZEIT_ZU_LANG = "leer", "format", "ueber_59", "null", "zu_lang"
_ZEIT_MUSTER = re.compile(r"^[0-9]{1,4}(?::[0-9]{2}){0,2}$")


def zeit_lesen(text: str, hoechstens_s: int) -> tuple[int | None, str]:
    """Eingetippte Countdown-Zeit → (Sekunden, "") oder (None, Fehlerart).

    Erlaubt:  „5“ (Minuten) · „5:00“ / „12:30“ / „90:00“ (Minuten:Sekunden) · „1:05:00“ (Stunden).
    Statt „:“ gehen auch „.“ und „,“ (z. B. „5.30“). Leerzeichen werden ignoriert.
    """
    roh = "".join(str(text or "").split()).replace(".", ":").replace(",", ":")
    if not roh:
        return None, ZEIT_LEER
    if not _ZEIT_MUSTER.match(roh):
        return None, ZEIT_FORMAT
    teile = [int(t) for t in roh.split(":")]
    if len(teile) == 1:
        sekunden = teile[0] * 60
    elif len(teile) == 2:
        m, s = teile
        if s > 59:
            return None, ZEIT_UEBER_59
        sekunden = m * 60 + s
    else:
        h, m, s = teile
        if m > 59 or s > 59:
            return None, ZEIT_UEBER_59
        sekunden = h * 3600 + m * 60 + s
    if sekunden <= 0:
        return None, ZEIT_NULL
    if sekunden > hoechstens_s:
        return None, ZEIT_ZU_LANG
    return sekunden, ""


def zeit_text(ms: int | None) -> str:
    """Restzeit als „4:59:40“ bzw. „05:00“ (aufgerundet auf ganze Sekunden)."""
    if ms is None:
        return "--:--"
    s = (ms + 999) // 1000
    h, rest = divmod(s, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
