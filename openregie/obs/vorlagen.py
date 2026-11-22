"""Zwecke, Quellen-Arten und Layouts für „Shot hinzufügen“ (ohne Qt, ohne OBS – reine Beschreibung).

Ein **Shot** ist eine OBS-Szene, wie bei Wirecast eine fertige Bildaufteilung, z. B. „Reactions“:
das Video groß, Kevins Kamera klein in der Ecke.

Erweitern: Neue Quellen-Arten oder Zwecke einfach unten in QUELLENARTEN bzw. ZWECKE eintragen.
Die Texte (Knopf-Beschriftung) stehen in einstellungen.toml unter [texte] (zweck_…, art_…, layout_…).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Rollen im Layout
HAUPT, KAMERA = "haupt", "kamera"


@dataclass(frozen=True)
class QuellenArt:
    schluessel: str
    # OBS-Quellentypen in der Reihenfolge, in der sie bevorzugt werden (der erste, den OBS kennt, gewinnt)
    obs_arten: tuple[str, ...]
    symbol: str
    # Gibt es so eine Quelle schon (z. B. die Kamera), wird sie wiederverwendet statt neu angelegt.
    # Eine Kamera kann OBS nur einmal öffnen – eine zweite Kamera-Quelle bliebe schwarz.
    wiederverwenden: bool = False
    braucht_datei: bool = False
    einstellungen: dict = field(default_factory=dict)


QUELLENARTEN: dict[str, QuellenArt] = {a.schluessel: a for a in (
    QuellenArt("kamera", ("v4l2_input",), "📷", wiederverwenden=True),
    # Spiel: obs-vkcapture (falls installiert), sonst ein Fenster aufnehmen, sonst den Bildschirm
    QuellenArt("spiel", ("vkcapture-source", "pipewire-window-capture-source", "pipewire-screen-capture-source",
                         "xcomposite_input"), "🎮"),
    QuellenArt("fenster", ("pipewire-window-capture-source", "pipewire-screen-capture-source",
                           "xcomposite_input"), "🪟"),
    QuellenArt("bildschirm", ("pipewire-screen-capture-source", "xshm_input"), "💻"),
    # „unload: false“: Das Bild bleibt geladen, damit die Vorschau-Kachel es auch zeigt, wenn der Shot
    # nicht live ist. Ein Bild kostet praktisch keine Rechenleistung.
    QuellenArt("bild", ("image_source",), "🖼", braucht_datei=True, einstellungen={"unload": False}),
)}

# Arten, die man in einen bestehenden Shot einfügen kann („Quelle hinzufügen“)
ARTEN_ZUM_HINZUFUEGEN = ("kamera", "spiel", "bildschirm", "bild")


@dataclass(frozen=True)
class Layout:
    schluessel: str
    # Rolle → (x, y, breite, höhe) als Anteil der Bildfläche (0 … 1)
    rechtecke: dict[str, tuple[float, float, float, float]]


_KLEIN = 0.28  # Kamera klein in der Ecke: 28 % der Bildbreite
_RAND = 0.025

LAYOUTS: dict[str, Layout] = {l.schluessel: l for l in (
    Layout("voll", {HAUPT: (0, 0, 1, 1)}),
    Layout("kamera_rechts_unten", {HAUPT: (0, 0, 1, 1),
                                   KAMERA: (1 - _KLEIN - _RAND, 1 - _KLEIN - _RAND * 16 / 9, _KLEIN, _KLEIN)}),
    Layout("kamera_links_unten", {HAUPT: (0, 0, 1, 1),
                                  KAMERA: (_RAND, 1 - _KLEIN - _RAND * 16 / 9, _KLEIN, _KLEIN)}),
    Layout("kamera_rechts_oben", {HAUPT: (0, 0, 1, 1),
                                  KAMERA: (1 - _KLEIN - _RAND, _RAND * 16 / 9, _KLEIN, _KLEIN)}),
    Layout("nebeneinander", {HAUPT: (0, 0.1667, 0.6667, 0.6667), KAMERA: (0.6667, 0.1667, 0.3333, 0.6667)}),
)}


@dataclass(frozen=True)
class Zweck:
    schluessel: str
    symbol: str
    haupt: str  # Quellen-Art für das große Bild
    mit_kamera: bool  # kommt die Kamera klein dazu?
    layouts: tuple[str, ...]  # Auswahl; das erste ist der Vorschlag


ZWECKE: dict[str, Zweck] = {z.schluessel: z for z in (
    Zweck("kamera", "📷", "kamera", False, ("voll",)),
    Zweck("spiel", "🎮", "spiel", True, ("kamera_rechts_unten", "kamera_links_unten", "kamera_rechts_oben", "voll")),
    Zweck("reactions", "🎬", "fenster", True, ("kamera_rechts_unten", "kamera_links_unten", "nebeneinander")),
    Zweck("bildschirm", "💻", "bildschirm", True, ("kamera_rechts_unten", "kamera_links_unten", "voll")),
    Zweck("bild", "🖼", "bild", False, ("voll",)),
)}


def obs_art_waehlen(art: QuellenArt, vorhanden) -> str | None:
    """Der erste OBS-Typ der Art, den OBS kennt – so, wie OBS ihn nennt (mit Versionsnummer,
    z. B. „color_source“ → „color_source_v3“). Beim Anlegen braucht OBS genau diesen Namen."""
    vorhanden = list(vorhanden)
    for wunsch in art.obs_arten:
        for k in vorhanden:
            if k == wunsch or re.fullmatch(re.escape(wunsch) + r"_v\d+", k):
                return k
    return None


def layout_rollen(layout: str) -> set[str]:
    return set(LAYOUTS[layout].rechtecke)


def transform(layout: str, rolle: str, breite: int, hoehe: int) -> dict:
    """OBS-Transform für eine Rolle: das Bild passt (mit Seitenverhältnis) in den Rahmen."""
    x, y, b, h = LAYOUTS[layout].rechtecke[rolle]
    return {
        "positionX": round(x * breite, 1), "positionY": round(y * hoehe, 1),
        "alignment": 5,  # oben links
        "boundsType": "OBS_BOUNDS_SCALE_INNER", "boundsAlignment": 0,
        "boundsWidth": max(1.0, round(b * breite, 1)), "boundsHeight": max(1.0, round(h * hoehe, 1)),
        "rotation": 0.0, "cropLeft": 0, "cropRight": 0, "cropTop": 0, "cropBottom": 0,
    }


def freier_name(wunsch: str, vorhanden) -> str:
    name, nr = wunsch, 2
    while name in vorhanden:
        name, nr = f"{wunsch} ({nr})", nr + 1
    return name
