"""Register der Auslöser („Wenn …“) und Aktionen („… dann“) für das Wenn-dann-Fenster.

Erweitern (z. B. in Build 1.3 der Lautstärke-Auslöser): eine Funktion schreiben und mit
`ausloeser_eintragen(...)` bzw. `aktion_eintragen(...)` eintragen – das Fenster zeigt sie dann
automatisch in der passenden Gruppe an. Die Beschriftung kommt aus einstellungen.toml
([texte] wenn_<schluessel> bzw. dann_<schluessel>, Gruppen: gruppe_<name>).

Ein Auslöser bekommt beim Einrichten (`einrichten(umgebung, wert, ausloesen)`) die Funktion `ausloesen`
und gibt eine Funktion zurück, die alles wieder abbaut. Eingerichtet wird NUR, solange eine aktive Regel
den Auslöser benutzt – ohne aktive Regel hängt nichts an OBS: keine Pegelmessung, kein Takt, keine Abfrage.
Ein neuer Auslöser muss sich daran halten: alles, was Leistung kostet, gehört in `einrichten`, und die
zurückgegebene Funktion muss es vollständig beenden.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

# Was man zu einem Auslöser/einer Aktion auswählen muss (zweite Auswahlliste)
KEINE, SHOT, OVERLAY, TON = "", "shot", "overlay", "ton"

Abbauen = Callable[[], None]


@dataclass(frozen=True)
class Ausloeser:
    schluessel: str
    gruppe: str  # z. B. "stream", "szenen", "ton", "zeitplan"
    wahl: str  # KEINE, SHOT, OVERLAY, TON
    einrichten: Callable[["object", str | None, Callable[[], None]], Abbauen]


@dataclass(frozen=True)
class Aktion:
    schluessel: str
    gruppe: str
    wahl: str
    ausfuehren: Callable[["object", str | None], None]


AUSLOESER: dict[str, Ausloeser] = {}
AKTIONEN: dict[str, Aktion] = {}
# Reihenfolge der Gruppen in den Auswahllisten
GRUPPEN = ["stream", "szenen", "overlays", "ton", "zeitplan"]


def ausloeser_eintragen(a: Ausloeser) -> Ausloeser:
    AUSLOESER[a.schluessel] = a
    if a.gruppe not in GRUPPEN:
        GRUPPEN.append(a.gruppe)
    return a


def aktion_eintragen(a: Aktion) -> Aktion:
    AKTIONEN[a.schluessel] = a
    if a.gruppe not in GRUPPEN:
        GRUPPEN.append(a.gruppe)
    return a


def nach_gruppen(eintraege: dict) -> list[tuple[str, list]]:
    """[(gruppe, [eintrag, …]), …] in der festen Gruppen-Reihenfolge."""
    return [(g, [e for e in eintraege.values() if e.gruppe == g]) for g in GRUPPEN
            if any(e.gruppe == g for e in eintraege.values())]


# ---------------------------------------------------------------------------
#  Auslöser in Build 1.2: alle kostenlos – OBS meldet sie ohnehin von selbst.
# ---------------------------------------------------------------------------
def _signal(signal, pruefen):
    """Hilfe: auf ein Signal hören, solange die Regel aktiv ist."""
    def einrichten(_u, wert, ausloesen):
        def bei(*args):
            if pruefen(wert, *args):
                ausloesen()
        signal_obj = signal(_u)
        signal_obj.connect(bei)

        def abbauen():
            try:
                signal_obj.disconnect(bei)
            except (RuntimeError, TypeError):
                pass
        return abbauen
    return einrichten


def _sendung_ist(name):
    def pruefen(_wert, sendung):
        return getattr(sendung, "value", sendung) == name
    return pruefen


ausloeser_eintragen(Ausloeser("stream_startet", "stream", KEINE,
                              _signal(lambda u: u.sendung_geaendert, _sendung_ist("an"))))
ausloeser_eintragen(Ausloeser("stream_endet", "stream", KEINE,
                              _signal(lambda u: u.sendung_geaendert, _sendung_ist("aus"))))
ausloeser_eintragen(Ausloeser("shot_live", "szenen", SHOT,
                              _signal(lambda u: u.szene_geaendert, lambda wert, name: bool(wert) and name == wert)))


def _zeitplan_einrichten(u, _wert, ausloesen):
    """Zur Startzeit laut Zeitplan: EIN Wecker auf den nächsten Termin (kein Takt, keine Abfrage)."""
    return u.zeitplan_wecker(ausloesen)


ausloeser_eintragen(Ausloeser("zeitplan_start", "zeitplan", KEINE, _zeitplan_einrichten))


# ---------------------------------------------------------------------------
#  Aktionen
# ---------------------------------------------------------------------------
aktion_eintragen(Aktion("shot_live", "szenen", SHOT, lambda u, wert: u.shot_live(wert)))
aktion_eintragen(Aktion("overlay_ein", "overlays", OVERLAY, lambda u, wert: u.overlay_sichtbar(wert, True)))
aktion_eintragen(Aktion("overlay_aus", "overlays", OVERLAY, lambda u, wert: u.overlay_sichtbar(wert, False)))
aktion_eintragen(Aktion("ton_aus", "ton", TON, lambda u, wert: u.ton_stumm(wert, True)))
aktion_eintragen(Aktion("ton_an", "ton", TON, lambda u, wert: u.ton_stumm(wert, False)))
