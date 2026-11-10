"""Lädt einstellungen.toml (alle Farben, Texte, Größen) und die Build-Nummer.

Zugriff im Code z. B. so:  E.farben.hintergrund   oder   E.texte.knopf_start
"""

from __future__ import annotations

import tomllib
from pathlib import Path

PROJEKT_ORDNER = Path(__file__).resolve().parent.parent
EINSTELLUNGSDATEI = PROJEKT_ORDNER / "einstellungen.toml"
VERSIONSDATEI = PROJEKT_ORDNER / "VERSION"


class EinstellungsFehler(Exception):
    """Fehler in einstellungen.toml – die Meldung ist für Menschen geschrieben."""


class Bereich:
    """Ein Abschnitt wie [farben]. Fehlende Einträge geben eine verständliche Meldung."""

    def __init__(self, name: str, werte: dict):
        self._name = name
        self._werte = werte

    def __getattr__(self, schluessel: str):
        if schluessel.startswith("_"):
            raise AttributeError(schluessel)
        try:
            wert = self._werte[schluessel]
        except KeyError:
            raise EinstellungsFehler(
                f"In der Datei einstellungen.toml fehlt im Abschnitt [{self._name}] "
                f"der Eintrag „{schluessel}“."
            ) from None
        if isinstance(wert, dict):
            name = f"{self._name}.{schluessel}" if self._name else schluessel
            return Bereich(name, wert)
        return wert

    def als_dict(self) -> dict:
        return dict(self._werte)


def lade(pfad: Path = EINSTELLUNGSDATEI) -> Bereich:
    try:
        with open(pfad, "rb") as datei:
            daten = tomllib.load(datei)
    except FileNotFoundError:
        raise EinstellungsFehler(f"Die Datei {pfad.name} wurde nicht gefunden.") from None
    except tomllib.TOMLDecodeError as fehler:
        zeile = getattr(fehler, "lineno", None)
        wo = f" in Zeile {zeile}" if zeile else ""
        raise EinstellungsFehler(
            f"Die Datei {pfad.name} hat einen Schreibfehler{wo}. "
            "Oft fehlt ein Anführungszeichen oder ein „=“."
        ) from None
    return Bereich("", daten)


def build_nummer(pfad: Path = VERSIONSDATEI) -> str:
    """Die aktuelle Build-Nummer steht nur in der Datei VERSION."""
    try:
        return pfad.read_text(encoding="utf-8").strip() or "?"
    except OSError:
        return "?"


def build_anzeige(einstellungen: Bereich) -> str:
    return einstellungen.texte.build_anzeige.format(
        programmname=einstellungen.texte.programmname, build=build_nummer()
    )
