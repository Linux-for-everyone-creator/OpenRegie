"""Findet Port und Passwort von OBS automatisch und prüft, ob OBS läuft.

OBS speichert die WebSocket-Einstellungen in einer Datei. OpenRegie liest sie,
damit niemand das Passwort abtippen muss.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

STANDARD_PORT = 4455


def _config_ordner() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")


KANDIDATEN = [
    # normale Installation
    lambda: _config_ordner() / "obs-studio/plugin_config/obs-websocket/config.json",
    # Flatpak-Installation
    lambda: Path.home() / ".var/app/com.obsproject.Studio/config/obs-studio/plugin_config/obs-websocket/config.json",
]


@dataclass
class Zugang:
    port: int = STANDARD_PORT
    passwort: str = ""
    passwort_noetig: bool = False
    server_an: bool | None = None  # None = unbekannt (keine Datei gefunden)


def aus_obs_lesen(pfade: list[Path] | None = None) -> Zugang:
    pfade = pfade if pfade is not None else [k() for k in KANDIDATEN]
    for pfad in pfade:
        try:
            daten = json.loads(Path(pfad).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(daten, dict):
            continue
        port = daten.get("server_port", STANDARD_PORT)
        return Zugang(
            port=int(port) if str(port).isdigit() else STANDARD_PORT,
            passwort=str(daten.get("server_password") or ""),
            passwort_noetig=bool(daten.get("auth_required", False)),
            server_an=bool(daten.get("server_enabled", False)),
        )
    return Zugang()


def ermitteln(obs_einstellungen) -> Zugang:
    """Werte aus einstellungen.toml haben Vorrang, sonst die aus OBS."""
    zugang = aus_obs_lesen()
    if int(obs_einstellungen.port) > 0:
        zugang.port = int(obs_einstellungen.port)
    if str(obs_einstellungen.passwort):
        zugang.passwort = str(obs_einstellungen.passwort)
    return zugang


def obs_laeuft(proc: Path = Path("/proc")) -> bool:
    """Schaut, ob ein Programm namens „obs“ läuft."""
    try:
        eintraege = list(proc.iterdir())
    except OSError:
        return False
    for eintrag in eintraege:
        if not eintrag.name.isdigit():
            continue
        try:
            if (eintrag / "comm").read_text().strip() == "obs":
                return True
        except OSError:
            continue
    return False
