"""Zeitplan: an welchen Tagen und um wie viel Uhr Kevin sicher live geht (ohne Qt, leicht zu prüfen)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

TAGE_KURZ = ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")


@dataclass(frozen=True, order=True)
class Termin:
    tag: int  # 0 = Montag … 6 = Sonntag
    stunde: int
    minute: int

    @property
    def zeit(self) -> str:
        return f"{self.stunde:02d}:{self.minute:02d}"

    def text(self, tage=TAGE_KURZ) -> str:
        return f"{tage[self.tag]} {self.zeit}"

    def als_dict(self) -> dict:
        return {"tag": self.tag, "zeit": self.zeit}

    @staticmethod
    def aus_dict(d: dict) -> "Termin | None":
        try:
            tag = int(d["tag"])
            stunde, minute = (int(x) for x in str(d["zeit"]).split(":"))
        except (KeyError, TypeError, ValueError):
            return None
        if not (0 <= tag <= 6 and 0 <= stunde <= 23 and 0 <= minute <= 59):
            return None
        return Termin(tag, stunde, minute)


def naechster(termine, jetzt: datetime | None = None) -> datetime | None:
    """Der nächste Termin nach `jetzt` (genau jetzt zählt nicht mehr)."""
    jetzt = jetzt or datetime.now()
    beste = None
    for t in termine:
        tage = (t.tag - jetzt.weekday()) % 7
        zeitpunkt = (jetzt + timedelta(days=tage)).replace(hour=t.stunde, minute=t.minute, second=0, microsecond=0)
        if zeitpunkt <= jetzt:
            zeitpunkt += timedelta(days=7)
        if beste is None or zeitpunkt < beste:
            beste = zeitpunkt
    return beste
