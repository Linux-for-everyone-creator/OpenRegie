"""Einzel-Unos verstehen (z. B. ein einzelnes „Countdown | Circles“).

Einzel-Unos sind technisch „Control Apps“ von Singular.live (darauf baut Overlays.uno auf).
Die Befehle über „…/api“ (ShowOverlay usw.) nehmen sie zwar an, zeigen aber NICHTS an.
Gesteuert werden sie über die Singular-Schnittstelle derselben Adresse:

  GET   …/controlapps/<token>           → Name, Vorschaubild, Ausgabe-Adresse
  GET   …/controlapps/<token>/model     → Bauplan: Teile („Subkompositionen“) und Felder
  GET   …/controlapps/<token>/control   → aktueller Zustand: pro Teil "state" (In/Out1/Out2) + Werte
  PATCH …/controlapps/<token>/control   → ändern, z. B. [{"subCompositionId": "…", "state": "In"}]

Mit dem echten Uno geprüft (14.11.2026):
  - Komplett sichtbar wird es nur, wenn der Hauptteil UND alle Teile, die im Bauplan
    von Haus aus auf „In“ stehen, auf „In“ gehen – und das Häkchen „Active“ im Hauptteil
    an ist. Ohne „Active“ erscheint nur der Kreis ohne Zahlen.
  - Zeitgeber („timecontrol“) zählen die ABGELAUFENE Zeit in Millisekunden:
    {"value": abgelaufen_bis_UTC, "UTC": Startzeitpunkt, "isRunning": bool}.
    Steuern mit {"command": "play" | "pause" | "reset" | "start"}.
  - Die Dauer steht in „BeginTime“ in Sekunden (17980 = 04:59:40).
"""

from __future__ import annotations

from dataclasses import dataclass, field

AKTIV_FELD = "Active"
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
            if art == "timecontrol" and plan.timer is None:
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
    """Der PATCH-Inhalt zum Ein- bzw. Ausblenden."""
    zustand = "In" if sichtbar else "Out"
    befehl = []
    for kennung in plan.ein_teile:
        eintrag = {"subCompositionId": kennung, "state": zustand}
        if kennung == plan.haupt and plan.aktiv_feld:
            eintrag["payload"] = {plan.aktiv_feld: sichtbar}
        befehl.append(eintrag)
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


def zeit_text(ms: int | None) -> str:
    """Restzeit als „4:59:40“ bzw. „05:00“ (aufgerundet auf ganze Sekunden)."""
    if ms is None:
        return "--:--"
    s = (ms + 999) // 1000
    h, rest = divmod(s, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
