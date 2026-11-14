"""Alles zu den Uno-Overlays im Fenster.

  OverlayListe      – linke Spalte: ein Eintrag pro Overlay mit Tally-Licht,
                      Name (zum Auswählen) und Knopf „Ein“/„Aus“.
  OverlayBedienfeld – rechte Spalte: großer Ein-/Ausblenden-Knopf und die Texte.
  UnoEinrichtung    – rechte Spalte: Uno-Projekte einfügen und entfernen.

Bedienung nur mit einfachem Klick. Texte werden in große Felder getippt.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QButtonGroup, QHBoxLayout, QLabel, QLineEdit, QScrollArea, QSizePolicy,
                               QVBoxLayout, QWidget)

from ..uno.verwaltung import Overlay, UnoProjekt, UnoVerwaltung
from .bausteine import Lampe, beschriftung, knopf


def tally_farbe(E, sichtbar: bool | None) -> str:
    if sichtbar is None:
        return E.farben.tally_unbekannt
    return E.farben.tally_an if sichtbar else E.farben.tally_aus


def _leeren(layout) -> None:
    while layout.count():
        eintrag = layout.takeAt(0)
        w = eintrag.widget()
        if w is not None:
            w.hide()
            w.deleteLater()
        elif eintrag.layout() is not None:
            _leeren(eintrag.layout())


def _scrollflaeche(innen: QWidget) -> QScrollArea:
    s = QScrollArea()
    s.setWidgetResizable(True)
    s.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    s.setFrameShape(QScrollArea.Shape.NoFrame)
    s.setWidget(innen)
    return s


class _Meldung(QLabel):
    """Grüne oder rote Rückmeldung unter einem Knopf."""

    def zeigen(self, text: str, erfolg: bool | None = None) -> None:
        self.setObjectName("gut" if erfolg else ("fehler" if erfolg is False else "meldung"))
        self.style().unpolish(self)
        self.style().polish(self)
        self.setText(text)


def meldung() -> _Meldung:
    m = _Meldung("")
    m.setWordWrap(True)
    m.setObjectName("meldung")
    return m


# ---------------------------------------------------------------------------
class OverlayZeile(QWidget):
    def __init__(self, E, overlay: Overlay, gruppe: QButtonGroup, parent=None):
        super().__init__(parent)
        self.E = E
        self.overlay = overlay
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(E.groessen.abstand // 2)
        self.tally = Lampe(E.groessen.tally, tally_farbe(E, overlay.sichtbar))
        lay.addWidget(self.tally)
        self.name = knopf(overlay.name, "overlay")
        self.name.setCheckable(True)
        gruppe.addButton(self.name)
        lay.addWidget(self.name, 1)
        self.schalter = knopf("")
        self.schalter.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.schalter.setFixedWidth(int(E.groessen.knopf_breite_min))
        lay.addWidget(self.schalter)
        self.auffrischen()

    def auffrischen(self) -> None:
        o, t = self.overlay, self.E.texte
        self.name.setText(o.name)
        self.tally.farbe_setzen(tally_farbe(self.E, o.sichtbar))
        zustand = t.overlay_im_stream if o.sichtbar else (t.overlay_ausgeblendet if o.sichtbar is False
                                                          else t.overlay_unbekannt)
        self.tally.setToolTip(zustand)
        self.name.setAccessibleName(f"{o.name} – {zustand}")
        an = bool(o.sichtbar)
        self.schalter.setText(t.knopf_aus if an else t.knopf_ein)
        self.schalter.setObjectName("ausblenden" if an else "einblenden")
        self.schalter.setAccessibleName(f"{o.name} {t.knopf_ausblenden if an else t.knopf_einblenden}")
        self.schalter.style().unpolish(self.schalter)
        self.schalter.style().polish(self.schalter)
        self.schalter.setEnabled(not o.beschaeftigt)


class OverlayListe(QWidget):
    gewaehlt = Signal(str)  # Schlüssel des Overlays
    einrichten_geklickt = Signal()

    def __init__(self, E, uno: UnoVerwaltung, parent=None):
        super().__init__(parent)
        self.E = E
        self.uno = uno
        t, g = E.texte, E.groessen
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(g.abstand // 2)
        lay.addWidget(beschriftung(t.overlays_ueberschrift, "ueberschrift"))

        innen = QWidget()
        self._zeilen_lay = QVBoxLayout(innen)
        self._zeilen_lay.setContentsMargins(0, 0, 0, 0)
        self._zeilen_lay.setSpacing(g.abstand // 2)
        self._zeilen_lay.addStretch(1)
        lay.addWidget(_scrollflaeche(innen), 1)

        self.leer = beschriftung(t.overlays_leer, "hinweis_gross")
        self.leer.setWordWrap(True)
        lay.addWidget(self.leer)

        self.knopf_neu = knopf(t.knopf_liste_neu)
        self.knopf_neu.clicked.connect(lambda: self.uno.auffrischen())
        lay.addWidget(self.knopf_neu)
        self.knopf_einrichten = knopf(t.knopf_uno_einrichten)
        self.knopf_einrichten.clicked.connect(self.einrichten_geklickt)
        lay.addWidget(self.knopf_einrichten)

        self._gruppe = QButtonGroup(self)
        self._gruppe.setExclusive(True)
        self.zeilen: dict[str, OverlayZeile] = {}
        self.gewaehlter: str | None = None

        uno.liste_geaendert.connect(self.neu_aufbauen)
        uno.overlay_geaendert.connect(self._overlay_geaendert)
        self.neu_aufbauen()

    def neu_aufbauen(self) -> None:
        for schluessel in list(self.zeilen):
            if schluessel not in self.uno.overlays:
                zeile = self.zeilen.pop(schluessel)
                self._gruppe.removeButton(zeile.name)
                zeile.hide()
                zeile.deleteLater()
        # Reihenfolge wie bei Uno: erst alle Zeilen aus dem Layout nehmen, dann neu einreihen
        for zeile in self.zeilen.values():
            self._zeilen_lay.removeWidget(zeile)
        for nr,(schluessel, overlay) in enumerate(self.uno.overlays.items()):
            zeile = self.zeilen.get(schluessel)
            if zeile is None or zeile.overlay is not overlay:
                if zeile is not None:
                    self._gruppe.removeButton(zeile.name)
                    zeile.deleteLater()
                zeile = OverlayZeile(self.E, overlay, self._gruppe)
                zeile.name.clicked.connect(lambda _=False, s=schluessel: self.waehlen(s))
                zeile.schalter.clicked.connect(lambda _=False, o=overlay: self.uno.umschalten(o))
                self.zeilen[schluessel] = zeile
            self._zeilen_lay.insertWidget(nr, zeile)
            zeile.show()  # sofort sichtbar (Qt würde es sonst erst später zeigen)
            zeile.auffrischen()
        self.leer.setVisible(not self.zeilen)
        if self.gewaehlter is not None and self.gewaehlter not in self.zeilen:
            self.gewaehlter = None
            self.gewaehlt.emit("")
        elif self.gewaehlter in self.zeilen:
            self.zeilen[self.gewaehlter].name.setChecked(True)

    def waehlen(self, schluessel: str) -> None:
        zeile = self.zeilen.get(schluessel)
        if zeile is None:
            return
        zeile.name.setChecked(True)
        self.gewaehlter = schluessel
        self.gewaehlt.emit(schluessel)

    def auswahl_aufheben(self) -> None:
        self._gruppe.setExclusive(False)
        for zeile in self.zeilen.values():
            zeile.name.setChecked(False)
        self._gruppe.setExclusive(True)
        self.gewaehlter = None

    def _overlay_geaendert(self, overlay: Overlay) -> None:
        zeile = self.zeilen.get(overlay.schluessel)
        if zeile is not None:
            zeile.auffrischen()


# ---------------------------------------------------------------------------
class OverlayBedienfeld(QWidget):
    def __init__(self, E, uno: UnoVerwaltung, parent=None):
        super().__init__(parent)
        self.E = E
        self.uno = uno
        self.overlay: Overlay | None = None
        self.eingaben: dict[str, QLineEdit] = {}
        self._stand: dict[str, str] = {}  # letzter bekannter Text pro Feld
        t, g = E.texte, E.groessen

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(g.abstand)
        self.name = beschriftung("", "ueberschrift")
        self.name.setWordWrap(True)
        lay.addWidget(self.name)

        tally_reihe = QHBoxLayout()
        tally_reihe.setSpacing(12)
        self.tally = Lampe(g.lampe, E.farben.tally_unbekannt)
        tally_reihe.addWidget(self.tally)
        self.tally_text = beschriftung("", "tally_text")
        tally_reihe.addWidget(self.tally_text, 1)
        lay.addLayout(tally_reihe)

        self.schalter = knopf(t.knopf_einblenden, "einblenden")
        self.schalter.clicked.connect(self._umschalten)
        lay.addWidget(self.schalter)
        self.meldung_schalter = meldung()
        lay.addWidget(self.meldung_schalter)

        lay.addWidget(beschriftung(t.overlay_texte, "ueberschrift"))
        innen = QWidget()
        self._felder_lay = QVBoxLayout(innen)
        self._felder_lay.setContentsMargins(0, 0, 8, 0)
        self._felder_lay.setSpacing(6)
        self._felder_lay.addStretch(1)
        lay.addWidget(_scrollflaeche(innen), 1)

        self.knopf_uebernehmen = knopf(t.knopf_texte_uebernehmen)
        self.knopf_uebernehmen.clicked.connect(self.texte_uebernehmen)
        lay.addWidget(self.knopf_uebernehmen)
        self.knopf_texte_neu = knopf(t.knopf_texte_neu)
        self.knopf_texte_neu.clicked.connect(self.texte_laden)
        lay.addWidget(self.knopf_texte_neu)
        self.meldung_texte = meldung()
        lay.addWidget(self.meldung_texte)

        uno.overlay_geaendert.connect(self._overlay_geaendert)

    def zeigen(self, overlay: Overlay) -> None:
        self.overlay = overlay
        self.meldung_schalter.zeigen("")
        self.meldung_texte.zeigen("")
        self._zustand_zeigen()
        self._felder_aufbauen([], self.E.texte.overlay_texte_laden)
        self.texte_laden()

    def _zustand_zeigen(self) -> None:
        o, t = self.overlay, self.E.texte
        if o is None:
            return
        self.name.setText(o.name)
        self.tally.farbe_setzen(tally_farbe(self.E, o.sichtbar))
        if o.sichtbar:
            self.tally_text.setText(t.overlay_im_stream)
            self.tally_text.setStyleSheet(f"color: {self.E.farben.tally_an};")
        else:
            self.tally_text.setText(t.overlay_ausgeblendet if o.sichtbar is False else t.overlay_unbekannt)
            self.tally_text.setStyleSheet(f"color: {self.E.farben.text_gedimmt};")
        an = bool(o.sichtbar)
        self.schalter.setText(t.knopf_ausblenden if an else t.knopf_einblenden)
        self.schalter.setObjectName("ausblenden" if an else "einblenden")
        self.schalter.style().unpolish(self.schalter)
        self.schalter.style().polish(self.schalter)
        self.schalter.setEnabled(not o.beschaeftigt)

    def _overlay_geaendert(self, overlay: Overlay) -> None:
        if overlay is self.overlay:
            self._zustand_zeigen()

    def _umschalten(self) -> None:
        if self.overlay is None:
            return
        self.meldung_schalter.zeigen("")

        def fertig(ok, fehler):
            if not ok:
                self.meldung_schalter.zeigen(fehler, False)

        self.uno.umschalten(self.overlay, fertig)

    # --- Texte ------------------------------------------------------------
    def texte_laden(self) -> None:
        overlay = self.overlay
        if overlay is None:
            return
        self.knopf_texte_neu.setEnabled(False)

        def fertig(ok, fehler):
            if overlay is not self.overlay:
                return  # inzwischen anderes Overlay gewählt
            self.knopf_texte_neu.setEnabled(True)
            if ok:
                self._felder_aufbauen(overlay.felder, self.E.texte.overlay_keine_texte)
            else:
                self._felder_aufbauen([], "")
                self.meldung_texte.zeigen(fehler, False)

        self.uno.felder_laden(overlay, fertig)

    def _felder_aufbauen(self, felder: list[tuple[str, str]], leer_text: str) -> None:
        _leeren(self._felder_lay)
        self.eingaben, self._stand = {}, {}
        for feld, wert in felder:
            self._felder_lay.addWidget(beschriftung(feld, "feldname"))
            eingabe = QLineEdit(wert)
            eingabe.setAccessibleName(feld)
            eingabe.setCursorPosition(0)
            self._felder_lay.addWidget(eingabe)
            self.eingaben[feld] = eingabe
            self._stand[feld] = wert
            eingabe.show()
        if not felder and leer_text:
            hinweis = beschriftung(leer_text, "hinweis_gross")
            hinweis.setWordWrap(True)
            self._felder_lay.addWidget(hinweis)
        self._felder_lay.addStretch(1)
        self.knopf_uebernehmen.setEnabled(bool(felder))

    def texte_uebernehmen(self) -> None:
        overlay = self.overlay
        if overlay is None:
            return
        t = self.E.texte
        geaendert = {f: e.text() for f, e in self.eingaben.items() if e.text() != self._stand.get(f)}
        if not geaendert:
            self.meldung_texte.zeigen(t.meldung_texte_nichts)
            return
        self.knopf_uebernehmen.setEnabled(False)
        self.meldung_texte.zeigen("…")
        offen = {"anzahl": len(geaendert), "fehler": ""}

        def fertig_feld(feld, text, ok, fehler):
            offen["anzahl"] -= 1
            if ok:
                self._stand[feld] = text
            else:
                offen["fehler"] = fehler
            if offen["anzahl"] == 0 and overlay is self.overlay:
                self.knopf_uebernehmen.setEnabled(True)
                if offen["fehler"]:
                    self.meldung_texte.zeigen(offen["fehler"], False)
                else:
                    self.meldung_texte.zeigen(t.meldung_texte_ok, True)

        for feld, text in geaendert.items():
            self.uno.feld_setzen(overlay, feld, text,
                                 lambda ok, fehler, f=feld, x=text: fertig_feld(f, x, ok, fehler))


# ---------------------------------------------------------------------------
class UnoEinrichtung(QWidget):
    zurueck_geklickt = Signal()

    def __init__(self, E, uno: UnoVerwaltung, parent=None, zwischenablage=None):
        super().__init__(parent)
        self.E = E
        self.uno = uno
        self._zwischenablage = zwischenablage or (lambda: QGuiApplication.clipboard().text())
        t, g = E.texte, E.groessen

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(g.abstand)
        lay.addWidget(beschriftung(t.uno_ueberschrift, "ueberschrift"))
        erklaerung = beschriftung(t.uno_erklaerung, "hinweis_gross")
        erklaerung.setWordWrap(True)
        lay.addWidget(erklaerung)
        self.einfuegen = knopf(t.knopf_uno_einfuegen, "einblenden")
        self.einfuegen.clicked.connect(self._einfuegen)
        lay.addWidget(self.einfuegen)
        self.meldung = meldung()
        lay.addWidget(self.meldung)

        innen = QWidget()
        self._projekte_lay = QVBoxLayout(innen)
        self._projekte_lay.setContentsMargins(0, 0, 8, 0)
        self._projekte_lay.setSpacing(g.abstand // 2)
        lay.addWidget(_scrollflaeche(innen), 1)

        self.zurueck = knopf(t.knopf_zurueck)
        self.zurueck.clicked.connect(self.zurueck_geklickt)
        lay.addWidget(self.zurueck)

        self._wirklich: UnoProjekt | None = None
        self._wirklich_uhr = QTimer(self)
        self._wirklich_uhr.setSingleShot(True)
        self._wirklich_uhr.timeout.connect(self._wirklich_zuruecksetzen)
        self.entfernen_knoepfe: dict[str, object] = {}
        uno.liste_geaendert.connect(self.projekte_zeigen)
        self.projekte_zeigen()

    def projekte_zeigen(self) -> None:
        _leeren(self._projekte_lay)
        self.entfernen_knoepfe = {}
        t = self.E.texte
        if not self.uno.projekte:
            self._projekte_lay.addWidget(beschriftung(t.uno_keine_projekte, "hinweis_gross"))
        for projekt in self.uno.projekte:
            reihe = QHBoxLayout()
            anzahl = sum(1 for o in self.uno.overlays.values() if o.projekt is projekt)
            name = beschriftung(f"{projekt.name}\n{anzahl} Overlay(s)")
            reihe.addWidget(name, 1)
            k = knopf(t.knopf_uno_wirklich if projekt is self._wirklich else t.knopf_uno_entfernen,
                      "ausblenden" if projekt is self._wirklich else "")
            k.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            k.setFixedWidth(240)
            k.clicked.connect(lambda _=False, p=projekt: self._entfernen(p))
            reihe.addWidget(k)
            self.entfernen_knoepfe[projekt.token] = k
            self._projekte_lay.addLayout(reihe)
            name.show()
            k.show()
        self._projekte_lay.addStretch(1)

    def _einfuegen(self) -> None:
        self.einfuegen.setEnabled(False)
        self.meldung.zeigen("…")

        def fertig(ok, text):
            self.einfuegen.setEnabled(True)
            self.meldung.zeigen(text, ok)
            self.projekte_zeigen()

        self.uno.projekt_hinzufuegen(self._zwischenablage(), fertig)

    def _entfernen(self, projekt: UnoProjekt) -> None:
        """Erster Klick: „Wirklich entfernen?“ – zweiter Klick (innerhalb 5 s): weg."""
        if self._wirklich is projekt:
            self._wirklich = None
            self._wirklich_uhr.stop()
            self.uno.projekt_entfernen(projekt)
            self.meldung.zeigen("")
        else:
            self._wirklich = projekt
            self._wirklich_uhr.start(5000)
        self.projekte_zeigen()

    def _wirklich_zuruecksetzen(self) -> None:
        self._wirklich = None
        self.projekte_zeigen()
