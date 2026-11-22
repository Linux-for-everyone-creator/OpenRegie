"""Shots und Quellen in OBS – Teil der Motor-Schicht (die Oberfläche spricht nur hiermit, nie direkt mit OBS).

Ein **Shot** ist eine OBS-Szene (wie bei Wirecast eine fertige Bildaufteilung). Darin liegen **Quellen**
(Kamera, Spiel, Bildschirm, Bild …).

Sparsam mit Ressourcen:
  - Die Liste der Shots wird nur gelesen, solange jemand sie anschaut (`beobachten`/`loslassen`).
    Schaut niemand hin, schickt diese Klasse keine einzige Anfrage an OBS – Änderungen in OBS
    merkt sie sich nur als „veraltet“ und liest beim nächsten Hinschauen einmal neu.
  - Gelesen wird nur nach Ereignissen von OBS (z. B. „Szene umbenannt“), nie in einem Takt.
  - Vorschaubilder holt `Standbilder` – auch nur, solange eine Ansicht offen ist.
  - Beim Löschen werden Quellen, die danach in keinem Shot mehr vorkommen, in OBS ganz entfernt
    (gibt Kamera, Bildschirmaufnahme usw. frei).

Alle Abläufe sind Folgen von Anfragen (Generator: yield (Anfrage, Daten) → bekommt (ok, Antwort, Fehler)).
Nichts davon hält die Oberfläche an.
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass, field
from typing import Callable

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QImage

from . import vorlagen
from .verbindung import ObsVerbindung, Status

log = logging.getLogger("openregie.quellen")

# Ereignisse von OBS, nach denen die Shot-Liste nicht mehr stimmt
_AENDERUNGEN = {
    "SceneCreated", "SceneRemoved", "SceneNameChanged", "SceneListChanged",
    "InputCreated", "InputRemoved", "InputNameChanged",
    "SceneItemCreated", "SceneItemRemoved", "SceneItemListReindexed", "SceneItemEnableStateChanged",
    "CurrentSceneCollectionChanged",
}
CODE_NAME_VERGEBEN = 601
# Quellentypen mit Ton (Linux: PulseAudio/PipeWire, ALSA, JACK; Windows/Mac der Vollständigkeit halber)
_TON_ARTEN = ("pulse_", "alsa_", "jack_", "audio", "wasapi", "coreaudio", "pipewire-audio")

Fertig = Callable[[bool, str], None]  # (erfolgreich, Meldung für Menschen bzw. neuer Name)


@dataclass
class Quelle:
    name: str
    art: str  # OBS-Quellentyp, z. B. "v4l2_input"
    kennung: int  # sceneItemId im Shot
    an: bool = True
    ist_uno: bool = False
    ist_szene: bool = False  # eine Szene in der Szene (Gruppe/verschachtelt) – wird nicht gelöscht


@dataclass
class Shot:
    name: str
    quellen: list[Quelle] = field(default_factory=list)

    def eigene_quellen(self) -> list[Quelle]:
        """Was Kevin in OpenRegie sieht: ohne Uno-Overlays (die stehen in der Bibliothek)."""
        return [q for q in self.quellen if not q.ist_uno]


def bild_aus_daten(bilddaten: str) -> QImage | None:
    if not bilddaten:
        return None
    _, _, roh = bilddaten.partition(",")
    try:
        inhalt = base64.b64decode(roh or bilddaten, validate=False)
    except (ValueError, TypeError):
        return None
    bild = QImage()
    return bild if bild.loadFromData(inhalt) else None


class _Ablauf:
    """Führt einen Generator von OBS-Anfragen nacheinander aus."""

    def __init__(self, verbindung: ObsVerbindung, schritte, ende: Callable[[], None]):
        self.v, self.schritte, self.ende = verbindung, schritte, ende
        self._weiter(None)

    def _weiter(self, ergebnis):
        try:
            typ, daten = self.schritte.send(ergebnis)
        except StopIteration:
            self.ende()
            return
        except Exception:
            log.exception("Fehler im Ablauf mit OBS")
            self.ende()
            return
        self.v.anfrage(typ, daten, lambda ok, antwort, fehler: self._weiter((ok, antwort, fehler)))


class ObsQuellen(QObject):
    geaendert = Signal()  # die Liste der Shots/Quellen ist neu
    live_geaendert = Signal(str)  # Name des Shots, der gerade gesendet wird

    def __init__(self, verbindung: ObsVerbindung, texte, quellen_einstellungen, parent=None,
                 uno_namen: Callable[[], set] | None = None):
        super().__init__(parent)
        self.v = verbindung
        self.t = texte
        self._E = quellen_einstellungen
        self._uno_namen = uno_namen or (lambda: set())
        self.shots: list[Shot] = []
        self.gelesen = False  # wurde die Liste schon einmal gelesen?
        self._wer_schaut: set = set()
        self._veraltet = True
        self._liest = False
        self._nochmal = False
        self.lesungen = 0  # für Tests: wie oft die Liste gelesen wurde
        self._beschaeftigt = 0  # laufende Änderungen (anlegen, löschen …)

        self._sammeln = QTimer(self)  # viele Ereignisse kurz hintereinander → einmal lesen
        self._sammeln.setSingleShot(True)
        self._sammeln.setInterval(250)
        self._sammeln.timeout.connect(self._lesen)

        verbindung.status_geaendert.connect(self._status)
        verbindung.ereignis.connect(self._ereignis)
        verbindung.szene_geaendert.connect(self.live_geaendert)

    # ------------------------------------------------------------------
    #  Wer schaut hin?
    # ------------------------------------------------------------------
    @property
    def wird_beobachtet(self) -> bool:
        return bool(self._wer_schaut)

    def beobachten(self, wer) -> None:
        """Eine Ansicht ist offen. Beim ersten Hinschauen wird (falls nötig) einmal gelesen."""
        neu = not self._wer_schaut
        self._wer_schaut.add(wer)
        if neu and self._veraltet:
            self._anstossen()

    def loslassen(self, wer) -> None:
        self._wer_schaut.discard(wer)
        if not self._wer_schaut:
            self._sammeln.stop()

    @property
    def live(self) -> str:
        return self.v.szene

    def shot(self, name: str) -> Shot | None:
        return next((s for s in self.shots if s.name == name), None)

    @property
    def verbunden(self) -> bool:
        return self.v.verbunden

    def standbilder(self) -> "Standbilder":
        return Standbilder(self.v, self._E, self)

    # ------------------------------------------------------------------
    def _status(self, status: Status, _meldung: str) -> None:
        self._veraltet = True
        if status is Status.VERBUNDEN:
            if self._wer_schaut:
                self._anstossen()
        elif self.shots:
            self.shots = []
            self.gelesen = False
            self.geaendert.emit()

    def _ereignis(self, typ: str, _daten: dict) -> None:
        if typ in _AENDERUNGEN:
            self._veraltet = True
            if self._wer_schaut:
                self._anstossen()

    def _anstossen(self) -> None:
        if self.v.verbunden:
            self._sammeln.start()

    def neu_lesen(self) -> None:
        self._veraltet = True
        self._anstossen()

    def _lesen(self) -> None:
        if not self._wer_schaut or not self.v.verbunden:
            return
        if self._liest:
            self._nochmal = True
            return
        self._liest = True
        self._veraltet = False
        self.lesungen += 1
        _Ablauf(self.v, self._lese_schritte(), self._gelesen)

    def _gelesen(self) -> None:
        self._liest = False
        if self._nochmal:
            self._nochmal = False
            self._anstossen()

    def _lese_schritte(self):
        ok, d, _ = yield ("GetSceneList", None)
        if not ok:
            self._veraltet = True
            return
        # OBS zählt von unten: die oberste Szene in der OBS-Liste hat die höchste Nummer
        szenen = sorted(d.get("scenes", []), key=lambda s: -int(s.get("sceneIndex", 0)))
        uno = set(self._uno_namen())
        shots = []
        szenennamen = {s.get("sceneName") for s in szenen}
        for s in szenen:
            name = s.get("sceneName")
            if not name:
                continue
            ok, liste, _ = yield ("GetSceneItemList", {"sceneName": name})
            quellen = []
            if ok:
                for e in sorted(liste.get("sceneItems", []), key=lambda e: -int(e.get("sceneItemIndex", 0))):
                    qn = e.get("sourceName", "")
                    quellen.append(Quelle(
                        name=qn, art=e.get("inputKind") or "", kennung=int(e.get("sceneItemId", 0)),
                        an=bool(e.get("sceneItemEnabled", True)), ist_uno=qn in uno or qn.startswith("Uno: "),
                        ist_szene=bool(e.get("isGroup")) or qn in szenennamen or e.get("sourceType") == "OBS_SOURCE_TYPE_SCENE"))
            shots.append(Shot(name, quellen))
        self.shots = shots
        self.gelesen = True
        self.geaendert.emit()

    # ------------------------------------------------------------------
    #  Bedienung
    # ------------------------------------------------------------------
    def live_schalten(self, name: str, fertig: Fertig | None = None) -> None:
        """Ein Klick auf einen Shot: sofort live."""
        def antwort(ok, _d, fehler):
            if not ok:
                log.warning("Shot „%s“ nicht live geschaltet: %s", name, fehler)
            if fertig:
                fertig(ok, "" if ok else self._meldung(fehler))
        self.v.anfrage("SetCurrentProgramScene", {"sceneName": name}, antwort)

    def _alle_namen(self) -> set[str]:
        namen = set()
        for s in self.shots:
            namen.add(s.name)
            namen |= {q.name for q in s.quellen}
        return namen

    def _name_pruefen(self, alt: str, neu: str) -> str | None:
        """Fehlermeldung oder None."""
        if not neu:
            return self.t.meldung_name_leer
        if neu != alt and neu in self._alle_namen():
            return self.t.meldung_name_vergeben
        return None

    def shot_umbenennen(self, alt: str, neu: str, fertig: Fertig) -> None:
        self._umbenennen("SetSceneName", {"sceneName": alt, "newSceneName": neu.strip()}, alt, neu.strip(), fertig)

    def quelle_umbenennen(self, alt: str, neu: str, fertig: Fertig) -> None:
        self._umbenennen("SetInputName", {"inputName": alt, "newInputName": neu.strip()}, alt, neu.strip(), fertig)

    def _umbenennen(self, anfrage, daten, alt, neu, fertig: Fertig) -> None:
        fehler = self._name_pruefen(alt, neu)
        if fehler:
            QTimer.singleShot(0, lambda: fertig(False, fehler))
            return
        if neu == alt:
            QTimer.singleShot(0, lambda: fertig(True, neu))
            return

        def antwort(ok, _d, f):
            if ok:
                log.info("Umbenannt: „%s“ → „%s“", alt, neu)
                self.neu_lesen()
                fertig(True, neu)
            else:
                fertig(False, self._meldung(f))
        self.v.anfrage(anfrage, daten, antwort)

    def _meldung(self, fehler: str) -> str:
        if fehler == self.t.meldung_nicht_verbunden:
            return fehler
        if "already exists" in (fehler or ""):
            return self.t.meldung_name_vergeben
        return self.t.meldung_obs_abgelehnt

    # --- Für die Automatik (Wenn-dann) --------------------------------------
    def shot_namen(self, fertig: Callable[[list[str]], None]) -> None:
        """Namen aller Shots, einmal gefragt (z. B. für die Auswahlliste im Wenn-dann-Fenster)."""
        def antwort(ok, d, _f):
            szenen = sorted(d.get("scenes", []), key=lambda s: -int(s.get("sceneIndex", 0))) if ok else []
            fertig([s.get("sceneName") for s in szenen if s.get("sceneName")])
        self.v.anfrage("GetSceneList", None, antwort)

    def tonquellen(self, fertig: Callable[[list[str]], None]) -> None:
        """Namen der Quellen mit Ton (Mikrofon, Desktop-Ton …), einmal gefragt."""
        def antwort(ok, d, _f):
            namen = [e.get("inputName") for e in (d.get("inputs", []) if ok else [])
                     if e.get("inputName") and any(w in str(e.get("inputKind", "")) for w in _TON_ARTEN)]
            fertig(namen)
        self.v.anfrage("GetInputList", None, antwort)

    def ton_stumm(self, name: str, stumm: bool, fertig: Fertig | None = None) -> None:
        def antwort(ok, _d, f):
            if not ok:
                log.warning("Ton „%s“ nicht %s: %s", name, "stumm geschaltet" if stumm else "angeschaltet", f)
            if fertig:
                fertig(ok, "" if ok else self._meldung(f))
        self.v.anfrage("SetInputMute", {"inputName": name, "inputMuted": stumm}, antwort)

    # --- Löschen (gibt Ressourcen frei) ----------------------------------
    def shot_loeschen(self, name: str, fertig: Fertig) -> None:
        if len(self.shots) <= 1:
            QTimer.singleShot(0, lambda: fertig(False, self.t.meldung_letzter_shot))
            return
        self._los(self._shot_loeschen(name), fertig)

    def quelle_entfernen(self, shot: str, quelle: str, fertig: Fertig) -> None:
        self._los(self._quelle_entfernen(shot, quelle), fertig)

    def _los(self, schritte, fertig: Fertig) -> None:
        ergebnis = {"ok": False, "text": self.t.meldung_obs_abgelehnt}
        self._beschaeftigt += 1

        def huelle():
            erg = yield from schritte
            if isinstance(erg, tuple):
                ergebnis["ok"], ergebnis["text"] = erg

        def ende():
            self._beschaeftigt -= 1
            self.neu_lesen()
            fertig(ergebnis["ok"], ergebnis["text"])

        if not self.v.verbunden:
            self._beschaeftigt -= 1
            QTimer.singleShot(0, lambda: fertig(False, self.t.meldung_nicht_verbunden))
            return
        _Ablauf(self.v, huelle(), ende)

    def _benutzte_quellen(self):
        """Namen aller Quellen, die noch in irgendeinem Shot liegen."""
        ok, d, _ = yield ("GetSceneList", None)
        if not ok:
            return None
        benutzt = set()
        for s in d.get("scenes", []):
            ok, liste, _ = yield ("GetSceneItemList", {"sceneName": s.get("sceneName")})
            if not ok:
                return None
            benutzt |= {e.get("sourceName") for e in liste.get("sceneItems", [])}
        return benutzt

    def _aufraeumen(self, kandidaten: set[str]):
        """Quellen, die in keinem Shot mehr vorkommen, ganz aus OBS entfernen (Kamera wird frei usw.)."""
        if not kandidaten:
            return
        benutzt = yield from self._benutzte_quellen()
        if benutzt is None:
            return
        for name in sorted(kandidaten - benutzt):
            ok, _, fehler = yield ("RemoveInput", {"inputName": name})
            log.info("Quelle „%s“ ganz entfernt (in keinem Shot mehr): %s", name, "ok" if ok else fehler)

    def _shot_loeschen(self, name: str):
        ok, liste, fehler = yield ("GetSceneItemList", {"sceneName": name})
        if not ok:
            return False, self._meldung(fehler)
        uno = set(self._uno_namen())
        szenen = {s.name for s in self.shots}
        kandidaten = {e.get("sourceName") for e in liste.get("sceneItems", [])
                      if e.get("sourceName") not in uno and e.get("sourceName") not in szenen
                      and not e.get("isGroup") and not str(e.get("sourceName", "")).startswith("Uno: ")}
        ok, _, fehler = yield ("RemoveScene", {"sceneName": name})
        if not ok:
            return False, self._meldung(fehler)
        log.info("Shot „%s“ gelöscht", name)
        yield from self._aufraeumen(kandidaten)
        return True, self.t.meldung_shot_geloescht

    def _quelle_entfernen(self, shot: str, quelle: str):
        ok, d, fehler = yield ("GetSceneItemId", {"sceneName": shot, "sourceName": quelle})
        if not ok:
            return False, self._meldung(fehler)
        ok, _, fehler = yield ("RemoveSceneItem", {"sceneName": shot, "sceneItemId": d.get("sceneItemId")})
        if not ok:
            return False, self._meldung(fehler)
        log.info("Quelle „%s“ aus Shot „%s“ entfernt", quelle, shot)
        if quelle not in {s.name for s in self.shots}:
            yield from self._aufraeumen({quelle})
        return True, self.t.meldung_quelle_entfernt

    # --- Anlegen -----------------------------------------------------------
    def shot_anlegen(self, zweck: str, layout: str, fertig: Fertig, datei: str = "") -> None:
        """Neuer Shot nach Zweck und Layout, z. B. Reactions: Video groß, Kamera klein unten rechts."""
        self._los(self._shot_anlegen(zweck, layout, datei), fertig)

    def quelle_hinzufuegen(self, shot: str, art: str, fertig: Fertig, datei: str = "") -> None:
        """Eine Quelle in einen bestehenden Shot: Kamera klein in die Ecke, alles andere als Hintergrund."""
        self._los(self._quelle_hinzufuegen(shot, art, datei), fertig)

    def _grundlagen(self):
        """Was OBS kann und wie groß das Bild ist."""
        ok, d, fehler = yield ("GetInputKindList", {"unversioned": True})
        if not ok:
            return None
        arten = set(d.get("inputKinds", []))
        breite, hoehe = 1920, 1080
        ok, video, _ = yield ("GetVideoSettings", None)
        if ok:
            breite, hoehe = int(video.get("baseWidth") or breite), int(video.get("baseHeight") or hoehe)
        ok, d, _ = yield ("GetInputList", None)
        eingaenge = {e.get("inputName"): e.get("inputKind") for e in (d.get("inputs", []) if ok else [])}
        ok, d, _ = yield ("GetSceneList", None)
        szenen = [s.get("sceneName") for s in (d.get("scenes", []) if ok else [])]
        return arten, breite, hoehe, eingaenge, szenen

    def _art_text(self, art: str) -> str:
        return getattr(self.t, f"art_{art}")

    def _quelle_einsetzen(self, szene: str, art_name: str, arten: set, eingaenge: dict, datei: str,
                          neu_angelegt: list):
        """Legt eine Quelle der Art an (oder nimmt die vorhandene Kamera). → sceneItemId oder Fehlermeldung."""
        art = vorlagen.QUELLENARTEN[art_name]
        obs_art = next((a for a in art.obs_arten if a in arten), None)
        if obs_art is None:
            return self.t.meldung_art_fehlt.format(art=self._art_text(art_name))
        if art.wiederverwenden:
            vorhanden = next((n for n, k in eingaenge.items() if k in art.obs_arten), None)
            if vorhanden:
                ok, d, fehler = yield ("CreateSceneItem", {"sceneName": szene, "sourceName": vorhanden,
                                                           "sceneItemEnabled": True})
                return int(d.get("sceneItemId")) if ok else self._meldung(fehler)
        name = vorlagen.freier_name(getattr(self.t, f"quelle_name_{art_name}"),
                                    set(eingaenge) | set(self._alle_namen()) | {szene})
        einstellungen = dict(art.einstellungen)
        if art.braucht_datei:
            einstellungen["file"] = datei
        ok, d, fehler = yield ("CreateInput", {"sceneName": szene, "inputName": name, "inputKind": obs_art,
                                               "inputSettings": einstellungen, "sceneItemEnabled": True})
        if not ok:
            return self._meldung(fehler)
        eingaenge[name] = obs_art
        neu_angelegt.append(name)
        kennung = d.get("sceneItemId")
        log.info("Quelle „%s“ (%s) in „%s“ angelegt", name, obs_art, szene)
        if obs_art == "v4l2_input":
            # Erste Kamera auswählen (OBS wählt über die Fernsteuerung keine von selbst)
            ok, d, _ = yield ("GetInputPropertiesListPropertyItems", {"inputName": name, "propertyName": "device_id"})
            geraete = [i for i in (d.get("propertyItems", []) if ok else []) if i.get("itemEnabled", True)
                       and i.get("itemValue")]
            if geraete:
                yield ("SetInputSettings", {"inputName": name, "inputSettings": {"device_id": geraete[0]["itemValue"]}})
        if kennung is None:
            ok, d, fehler = yield ("GetSceneItemId", {"sceneName": szene, "sourceName": name})
            return int(d.get("sceneItemId")) if ok else self._meldung(fehler)
        return int(kennung)

    def _rueckgaengig(self, szene: str | None, neu_angelegt: list):
        """Ging etwas schief: alles wieder weg, damit nichts halb Fertiges Leistung kostet."""
        if szene:
            yield ("RemoveScene", {"sceneName": szene})
        for name in neu_angelegt:
            yield ("RemoveInput", {"inputName": name})

    def _shot_anlegen(self, zweck_name: str, layout: str, datei: str):
        zweck = vorlagen.ZWECKE[zweck_name]
        if layout not in zweck.layouts:
            layout = zweck.layouts[0]
        g = yield from self._grundlagen()
        if g is None:
            return False, self.t.meldung_obs_abgelehnt
        arten, breite, hoehe, eingaenge, szenen = g
        haupt = vorlagen.QUELLENARTEN[zweck.haupt]
        if not any(a in arten for a in haupt.obs_arten):
            return False, self.t.meldung_art_fehlt.format(art=self._art_text(zweck.haupt))
        shot = vorlagen.freier_name(getattr(self.t, f"zweck_{zweck_name}"), set(szenen) | set(eingaenge))
        ok, _, fehler = yield ("CreateScene", {"sceneName": shot})
        if not ok:
            return False, self._meldung(fehler)
        log.info("Shot „%s“ angelegt (Zweck %s, Layout %s)", shot, zweck_name, layout)
        neu: list[str] = []
        kennung = yield from self._quelle_einsetzen(shot, zweck.haupt, arten, eingaenge, datei, neu)
        if isinstance(kennung, str):
            yield from self._rueckgaengig(shot, neu)
            return False, kennung
        yield ("SetSceneItemTransform", {"sceneName": shot, "sceneItemId": kennung,
                                         "sceneItemTransform": vorlagen.transform(layout, vorlagen.HAUPT, breite, hoehe)})
        if zweck.mit_kamera and vorlagen.KAMERA in vorlagen.layout_rollen(layout):
            kennung = yield from self._quelle_einsetzen(shot, "kamera", arten, eingaenge, "", neu)
            if isinstance(kennung, str):
                # Ohne Kamera geht der Shot trotzdem – nur melden
                log.warning("Kamera nicht eingefügt: %s", kennung)
                return True, self.t.meldung_shot_ohne_kamera.format(name=shot)
            yield ("SetSceneItemTransform", {"sceneName": shot, "sceneItemId": kennung,
                                             "sceneItemTransform": vorlagen.transform(layout, vorlagen.KAMERA,
                                                                                      breite, hoehe)})
        return True, shot

    def _quelle_hinzufuegen(self, shot: str, art_name: str, datei: str):
        g = yield from self._grundlagen()
        if g is None:
            return False, self.t.meldung_obs_abgelehnt
        arten, breite, hoehe, eingaenge, _ = g
        neu: list[str] = []
        kennung = yield from self._quelle_einsetzen(shot, art_name, arten, eingaenge, datei, neu)
        if isinstance(kennung, str):
            yield from self._rueckgaengig(None, neu)
            return False, kennung
        if art_name == "kamera":
            t = vorlagen.transform("kamera_rechts_unten", vorlagen.KAMERA, breite, hoehe)
        else:
            t = vorlagen.transform("voll", vorlagen.HAUPT, breite, hoehe)
        yield ("SetSceneItemTransform", {"sceneName": shot, "sceneItemId": kennung, "sceneItemTransform": t})
        if art_name != "kamera":
            # großes Bild nach ganz unten, damit es Kamera und Overlays nicht verdeckt
            yield ("SetSceneItemIndex", {"sceneName": shot, "sceneItemId": kennung, "sceneItemIndex": 0})
        return True, self.t.meldung_quelle_hinzugefuegt


class Standbilder(QObject):
    """Kleine Vorschaubilder für Kacheln. Läuft NUR, solange eine Ansicht Namen beobachtet.

    Alle `vorschau_sekunden` wird jede beobachtete Quelle einmal geholt – nacheinander, immer nur
    eine Anfrage unterwegs. `beobachten([])` hält alles an: kein Takt, keine Anfrage.
    """

    neues_bild = Signal(str, QImage)

    def __init__(self, verbindung: ObsVerbindung, quellen_einstellungen, parent=None):
        super().__init__(parent)
        self.v = verbindung
        self._breite = int(quellen_einstellungen.vorschau_breite)
        self._qualitaet = max(1, min(100, int(quellen_einstellungen.vorschau_qualitaet)))
        self._namen: list[str] = []
        self._warteschlange: list[str] = []
        self._wartet = False
        self.anfragen = 0  # für Tests
        self._takt = QTimer(self)
        self._takt.setInterval(int(float(quellen_einstellungen.vorschau_sekunden) * 1000))
        self._takt.timeout.connect(self._runde)

    @property
    def laeuft(self) -> bool:
        return self._takt.isActive()

    def beobachten(self, namen: list[str]) -> None:
        neu = [n for n in namen if n not in self._namen]
        self._namen = list(dict.fromkeys(namen))
        self._warteschlange = [n for n in self._warteschlange if n in self._namen]
        if not self._namen:
            self._takt.stop()
            return
        if not self._takt.isActive():
            self._takt.start()
            neu = self._namen
        if neu:  # neue Kacheln sofort füllen, nicht erst beim nächsten Takt
            self._warteschlange += [n for n in neu if n not in self._warteschlange]
            self._naechstes()

    def anhalten(self) -> None:
        self.beobachten([])

    def _runde(self) -> None:
        self._warteschlange += [n for n in self._namen if n not in self._warteschlange]
        self._naechstes()

    def _naechstes(self) -> None:
        if self._wartet or not self._warteschlange or not self.v.verbunden:
            if not self.v.verbunden:
                self._warteschlange.clear()
            return
        name = self._warteschlange.pop(0)
        self._wartet = True
        self.anfragen += 1
        self.v.anfrage("GetSourceScreenshot", {"sourceName": name, "imageFormat": "jpg",
                                               "imageWidth": self._breite,
                                               "imageCompressionQuality": self._qualitaet},
                       lambda ok, d, _f, n=name: self._antwort(n, ok, d))

    def _antwort(self, name: str, ok: bool, daten: dict) -> None:
        self._wartet = False
        if ok and name in self._namen:
            bild = bild_aus_daten(daten.get("imageData", ""))
            if bild is not None:
                self.neues_bild.emit(name, bild)
        self._naechstes()
