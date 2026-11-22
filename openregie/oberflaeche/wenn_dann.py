"""Das Wenn-dann-Fenster (angelehnt an vMix): Regeln anlegen, bearbeiten, speichern – und der Zeitplan.

  ┌───────────────────────────────────────────────┐
  │ [ Regeln ] [ Zeitplan ]                        │
  │  ● An  Wenn Stream startet → dann …  [✎] [🗑] │
  │  [ + Neue Regel ]                              │
  ├───────────────────────────────────────────────┤
  │ WENN ……………………… ▾        DANN ……………………… ▾    │  Auswahllisten in Gruppen
  │ (z. B. welcher Shot ▾)   (z. B. welches …  ▾) │  (Stream, Szenen, Overlays, Ton, Zeitplan)
  │ [ Speichern ]  [ Abbrechen ]                   │
  └───────────────────────────────────────────────┘

Ganz ohne Tippen bedienbar: alles wird ausgewählt (große Listen, einfacher Klick).
Solange das Fenster zu ist, tut es nichts. Ob Regeln laufen, entscheidet allein die Automatik.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTime
from PySide6.QtGui import QColor, QFont, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QDialog, QHBoxLayout, QListView,
                               QSizePolicy, QStackedWidget, QVBoxLayout, QWidget)

from ..automatik import register
from ..automatik.motor import Automatik, Regel
from ..automatik.zeitplan import TAGE_KURZ, Termin
from .bausteine import beschriftung, flaeche, gesperrt_hinweis, knopf
from .overlay_bereich import _leeren, _scrollflaeche, meldung
from .stil import stylesheet


def _fest(k, breite: int):
    k.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    k.setFixedWidth(breite)
    return k


class GruppenAuswahl(QComboBox):
    """Große Auswahlliste mit Gruppen-Überschriften (die man nicht auswählen kann)."""

    def __init__(self, E, parent=None):
        super().__init__(parent)
        self.E = E
        self.setModel(QStandardItemModel(self))
        ansicht = QListView()
        ansicht.setObjectName("grosse_liste")
        ansicht.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.setView(ansicht)
        self.setMaxVisibleItems(12)  # große Scrollfläche
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def leeren(self, platzhalter: str) -> None:
        self.model().clear()
        item = QStandardItem(platzhalter)
        item.setData(None, Qt.ItemDataRole.UserRole)
        item.setForeground(QColor(self.E.farben.text_gedimmt))
        self.model().appendRow(item)

    def gruppe(self, text: str) -> None:
        item = QStandardItem(text.upper())
        item.setFlags(Qt.ItemFlag.NoItemFlags)  # Überschrift: nicht auswählbar
        schrift = QFont(self.font())
        schrift.setBold(True)
        schrift.setPixelSize(int(self.E.groessen.schrift_klein))
        item.setFont(schrift)
        item.setForeground(QColor(self.E.farben.logo))
        self.model().appendRow(item)

    def eintrag(self, text: str, wert) -> None:
        item = QStandardItem("    " + text)
        item.setData(wert, Qt.ItemDataRole.UserRole)
        self.model().appendRow(item)

    def wert(self):
        return self.currentData(Qt.ItemDataRole.UserRole)

    def waehlen(self, wert) -> bool:
        for i in range(self.count()):
            if wert is not None and self.itemData(i, Qt.ItemDataRole.UserRole) == wert:
                self.setCurrentIndex(i)
                return True
        self.setCurrentIndex(0)
        return False

    def werte(self) -> list:
        return [self.itemData(i, Qt.ItemDataRole.UserRole) for i in range(self.count())
                if self.itemData(i, Qt.ItemDataRole.UserRole) is not None]


def wenn_text(t, schluessel: str) -> str:
    return getattr(t, f"wenn_{schluessel}", schluessel)


def dann_text(t, schluessel: str) -> str:
    return getattr(t, f"dann_{schluessel}", schluessel)


class _RegelZeile(QWidget):
    def __init__(self, fenster: "WennDannFenster", regel: Regel):
        super().__init__()
        self.regel = regel
        E, t, g = fenster.E, fenster.E.texte, fenster.E.groessen
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(g.abstand // 2)
        self.schalter = _fest(knopf(t.regel_an if regel.aktiv else t.regel_aus,
                                    "einblenden" if regel.aktiv else ""), 130)
        self.schalter.setToolTip(t.regel_schalter_hinweis)
        self.schalter.clicked.connect(lambda: fenster.automatik.regel_aktiv(regel.kennung, not regel.aktiv))
        lay.addWidget(self.schalter)
        self.text = beschriftung(fenster.beschreibung(regel), "meldung")
        self.text.setWordWrap(True)
        if not regel.gueltig:
            self.text.setText(self.text.text() + "  " + t.regel_unvollstaendig)
        lay.addWidget(self.text, 1)
        self.bearbeiten = _fest(knopf(t.knopf_regel_bearbeiten), 170)
        self.bearbeiten.clicked.connect(lambda: fenster.bearbeiten(regel))
        lay.addWidget(self.bearbeiten)
        self.loeschen = _fest(knopf(t.knopf_regel_loeschen, "ausblenden"), 190)
        self.loeschen.clicked.connect(lambda: fenster.loeschen_geklickt(self))
        lay.addWidget(self.loeschen)
        self.bestaetigen = False


class WennDannFenster(QDialog):
    def __init__(self, E, automatik: Automatik, parent=None):
        super().__init__(parent)
        self.E = E
        self.automatik = automatik
        t, g = E.texte, E.groessen
        self.setWindowTitle(t.wenn_dann_titel)
        self.setStyleSheet(stylesheet(E) + f"QDialog {{ background-color: {E.farben.hintergrund}; }}")
        self.resize(1100, 760)
        self.setModal(False)
        self.regel_in_arbeit: Regel | None = None
        self._zeilen: list[_RegelZeile] = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(g.abstand, g.abstand, g.abstand, g.abstand)
        lay.setSpacing(g.abstand)
        reiter = QHBoxLayout()
        reiter.setSpacing(g.abstand // 2)
        self._reiter = QButtonGroup(self)
        self.reiter_regeln = knopf(t.reiter_regeln)
        self.reiter_zeitplan = knopf(t.reiter_zeitplan)
        for k in (self.reiter_regeln, self.reiter_zeitplan):
            k.setCheckable(True)
            k.setObjectName("wahl")
            self._reiter.addButton(k)
            reiter.addWidget(k)
        self.reiter_regeln.clicked.connect(lambda: self._seite(self.seite_regeln))
        self.reiter_zeitplan.clicked.connect(lambda: self._seite(self.seite_zeitplan))
        self.schliessen = _fest(knopf(t.knopf_schliessen), 200)
        self.schliessen.clicked.connect(self.close)
        reiter.addWidget(self.schliessen)
        lay.addLayout(reiter)

        self.seiten = QStackedWidget()
        lay.addWidget(self.seiten, 1)
        self.seite_regeln = self._regeln_bauen()
        self.seite_editor = self._editor_bauen()
        self.seite_zeitplan = self._zeitplan_bauen()
        for s in (self.seite_regeln, self.seite_editor, self.seite_zeitplan):
            self.seiten.addWidget(s)

        automatik.geaendert.connect(self._auffrischen)
        automatik.meldung.connect(lambda text, fehler: self.meldung.zeigen(text, not fehler))
        self._seite(self.seite_regeln)

    # ------------------------------------------------------------------
    def _seite(self, seite: QWidget) -> None:
        self.seiten.setCurrentWidget(seite)
        self.reiter_regeln.setChecked(seite is not self.seite_zeitplan)
        self.reiter_zeitplan.setChecked(seite is self.seite_zeitplan)
        if seite is self.seite_regeln:
            self._regeln_zeigen()
        elif seite is self.seite_zeitplan:
            self._zeitplan_zeigen()

    def _auffrischen(self) -> None:
        if not self.isVisible():
            return  # zu: nichts tun (beim Öffnen wird neu aufgebaut)
        if self.seiten.currentWidget() is self.seite_regeln:
            self._regeln_zeigen()
        elif self.seiten.currentWidget() is self.seite_zeitplan:
            self._zeitplan_zeigen()

    def showEvent(self, e):
        super().showEvent(e)
        if self.seiten.currentWidget() is not self.seite_editor:
            self._seite(self.seiten.currentWidget())

    def beschreibung(self, r: Regel) -> str:
        t = self.E.texte
        wenn = wenn_text(t, r.wenn) + (f" „{self._wert_name(r.wenn_wert)}“" if r.wenn_wert else "")
        dann = dann_text(t, r.dann) + (f" „{self._wert_name(r.dann_wert)}“" if r.dann_wert else "")
        return t.regel_beschreibung.format(wenn=wenn, dann=dann)

    def _wert_name(self, wert: str) -> str:
        overlay = self.automatik._uno.overlays.get(wert) if hasattr(self.automatik._uno, "overlays") else None
        return overlay.name if overlay is not None else str(wert)

    # --- Seite: Regeln ------------------------------------------------------
    def _regeln_bauen(self) -> QWidget:
        t, g = self.E.texte, self.E.groessen
        seite = QWidget()
        lay = QVBoxLayout(seite)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(g.abstand)
        self.zustand = beschriftung("", "gedimmt")
        lay.addWidget(self.zustand)
        innen = QWidget()
        self._liste = QVBoxLayout(innen)
        self._liste.setContentsMargins(0, 0, 4, 0)
        self._liste.setSpacing(g.abstand // 2)
        self._liste.setAlignment(Qt.AlignmentFlag.AlignTop)
        lay.addWidget(_scrollflaeche(innen), 1)
        self.leer = beschriftung(t.regeln_leer, "hinweis_gross")
        self.leer.setWordWrap(True)
        lay.addWidget(self.leer)
        self.meldung = meldung()
        lay.addWidget(self.meldung)
        self.neue_regel = knopf(t.knopf_neue_regel, "einblenden")
        self.neue_regel.clicked.connect(lambda: self.bearbeiten(None))
        lay.addWidget(self.neue_regel)
        return seite

    def _regeln_zeigen(self) -> None:
        t = self.E.texte
        _leeren(self._liste)
        self._zeilen = []
        for r in self.automatik.regeln:
            z = _RegelZeile(self, r)
            self._zeilen.append(z)
            self._liste.addWidget(z)
            z.show()
        self.leer.setVisible(not self.automatik.regeln)
        n = len(self.automatik.aktive_regeln())
        self.zustand.setText(t.automatik_laeuft.format(anzahl=n) if n else t.automatik_ruht)

    def loeschen_geklickt(self, zeile: _RegelZeile) -> None:
        if not zeile.bestaetigen:
            zeile.bestaetigen = True
            zeile.loeschen.setText(self.E.texte.knopf_wirklich_loeschen)
            return
        self.automatik.regel_loeschen(zeile.regel.kennung)

    # --- Seite: Regel bearbeiten ---------------------------------------------
    def _editor_bauen(self) -> QWidget:
        t, g = self.E.texte, self.E.groessen
        seite = QWidget()
        lay = QVBoxLayout(seite)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(g.abstand)
        self.editor_titel = beschriftung("", "ueberschrift")
        lay.addWidget(self.editor_titel)
        spalten = QHBoxLayout()
        spalten.setSpacing(g.abstand)
        self.wenn_liste, self.wenn_wahl, self.wenn_wahl_text = self._spalte(spalten, t.wenn_ueberschrift)
        pfeil = beschriftung("→", "ueberschrift")
        pfeil.setAlignment(Qt.AlignmentFlag.AlignTop)
        spalten.addWidget(pfeil)
        self.dann_liste, self.dann_wahl, self.dann_wahl_text = self._spalte(spalten, t.dann_ueberschrift)
        lay.addLayout(spalten)
        self.vorschau = beschriftung("", "meldung")
        self.vorschau.setWordWrap(True)
        lay.addWidget(self.vorschau)
        lay.addStretch(1)
        self.editor_meldung = meldung()
        lay.addWidget(self.editor_meldung)
        reihe = QHBoxLayout()
        reihe.setSpacing(g.abstand // 2)
        self.speichern = knopf(t.knopf_regel_speichern, "einblenden")
        self.speichern.clicked.connect(self._speichern)
        reihe.addWidget(self.speichern)
        self.abbrechen = knopf(t.knopf_abbrechen)
        self.abbrechen.clicked.connect(lambda: self._seite(self.seite_regeln))
        reihe.addWidget(self.abbrechen)
        lay.addLayout(reihe)
        gesperrt_hinweis(self.speichern, self._grund_speichern, self.editor_meldung.kurz_zeigen)

        self.wenn_liste.currentIndexChanged.connect(lambda _i: self._art_gewaehlt("wenn"))
        self.dann_liste.currentIndexChanged.connect(lambda _i: self._art_gewaehlt("dann"))
        self.wenn_wahl.currentIndexChanged.connect(lambda _i: self._pruefen())
        self.dann_wahl.currentIndexChanged.connect(lambda _i: self._pruefen())
        return seite

    def _spalte(self, eltern: QHBoxLayout, titel: str):
        g = self.E.groessen
        f = flaeche()
        lay = QVBoxLayout(f)
        lay.setContentsMargins(g.abstand, g.abstand, g.abstand, g.abstand)
        lay.setSpacing(g.abstand // 2)
        lay.addWidget(beschriftung(titel, "ueberschrift"))
        liste = GruppenAuswahl(self.E)
        lay.addWidget(liste)
        wahl_text = beschriftung("", "feldname")
        lay.addWidget(wahl_text)
        wahl = GruppenAuswahl(self.E)
        lay.addWidget(wahl)
        lay.addStretch(1)
        eltern.addWidget(f, 1)
        return liste, wahl, wahl_text

    def bearbeiten(self, regel: Regel | None) -> None:
        """None = neue Regel."""
        t = self.E.texte
        self.regel_in_arbeit = regel
        self.editor_titel.setText(t.regel_neu_titel if regel is None else t.regel_bearbeiten_titel)
        self.editor_meldung.zeigen("")
        for liste, eintraege, text in ((self.wenn_liste, register.AUSLOESER, wenn_text),
                                       (self.dann_liste, register.AKTIONEN, dann_text)):
            liste.blockSignals(True)
            liste.leeren(t.auswahl_bitte)
            for gruppe, alle in register.nach_gruppen(eintraege):
                liste.gruppe(getattr(t, f"gruppe_{gruppe}", gruppe))
                for e in alle:
                    liste.eintrag(text(t, e.schluessel), e.schluessel)
            liste.blockSignals(False)
        self.wenn_liste.waehlen(regel.wenn if regel else None)
        self.dann_liste.waehlen(regel.dann if regel else None)
        self._art_gewaehlt("wenn", regel.wenn_wert if regel else None)
        self._art_gewaehlt("dann", regel.dann_wert if regel else None)
        self._seite(self.seite_editor)

    def _art_gewaehlt(self, seite: str, vorwahl=None) -> None:
        t = self.E.texte
        liste, wahl, wahl_text = ((self.wenn_liste, self.wenn_wahl, self.wenn_wahl_text) if seite == "wenn"
                                  else (self.dann_liste, self.dann_wahl, self.dann_wahl_text))
        schluessel = liste.wert()
        eintrag = (register.AUSLOESER if seite == "wenn" else register.AKTIONEN).get(schluessel)
        art = eintrag.wahl if eintrag else register.KEINE
        wahl.blockSignals(True)
        wahl.leeren(t.auswahl_laedt if art else t.auswahl_bitte)
        wahl.blockSignals(False)
        wahl.setVisible(bool(art))
        wahl_text.setVisible(bool(art))
        wahl_text.setText(getattr(t, f"wahl_{art}", "") if art else "")
        self._pruefen()
        if not art:
            return

        def fertig(moeglichkeiten):
            if liste.wert() != schluessel:
                return  # inzwischen etwas anderes gewählt
            wahl.blockSignals(True)
            wahl.leeren(t.auswahl_bitte if moeglichkeiten else getattr(t, f"wahl_{art}_leer"))
            for wert, text in moeglichkeiten:
                wahl.eintrag(text, wert)
            if vorwahl is not None and not wahl.waehlen(vorwahl):
                wahl.eintrag(vorwahl, vorwahl)  # gibt es nicht mehr – trotzdem anzeigen
                wahl.waehlen(vorwahl)
            wahl.blockSignals(False)
            self._pruefen()

        self.automatik.wahl_moeglichkeiten(art, fertig)

    def _regel_aus_auswahl(self) -> Regel | None:
        wenn, dann = self.wenn_liste.wert(), self.dann_liste.wert()
        if not wenn or not dann:
            return None
        a, b = register.AUSLOESER[wenn], register.AKTIONEN[dann]
        r = Regel(wenn=wenn, dann=dann, wenn_wert=self.wenn_wahl.wert() if a.wahl else None,
                  dann_wert=self.dann_wahl.wert() if b.wahl else None)
        if self.regel_in_arbeit is not None:
            r.kennung, r.aktiv = self.regel_in_arbeit.kennung, self.regel_in_arbeit.aktiv
        return r

    def _grund_speichern(self) -> str:
        t = self.E.texte
        if not self.wenn_liste.wert():
            return t.gesperrt_regel_wenn
        if not self.dann_liste.wert():
            return t.gesperrt_regel_dann
        r = self._regel_aus_auswahl()
        if r is None or not r.gueltig:
            return t.gesperrt_regel_wahl
        return ""

    def _pruefen(self) -> None:
        self.speichern.setEnabled(not self._grund_speichern())
        r = self._regel_aus_auswahl()
        self.vorschau.setText(self.beschreibung(r) if r is not None and r.gueltig else "")

    def _speichern(self) -> None:
        r = self._regel_aus_auswahl()
        if r is None or not r.gueltig:
            return
        self.automatik.regel_speichern(r)
        self._seite(self.seite_regeln)
        self.meldung.zeigen(self.E.texte.meldung_regel_gespeichert, True)

    # --- Seite: Zeitplan -------------------------------------------------------
    def _zeitplan_bauen(self) -> QWidget:
        t, g = self.E.texte, self.E.groessen
        seite = QWidget()
        lay = QVBoxLayout(seite)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(g.abstand)
        self.naechster = beschriftung("", "ueberschrift")
        lay.addWidget(self.naechster)
        innen = QWidget()
        self._termine = QVBoxLayout(innen)
        self._termine.setContentsMargins(0, 0, 4, 0)
        self._termine.setSpacing(g.abstand // 2)
        self._termine.setAlignment(Qt.AlignmentFlag.AlignTop)
        lay.addWidget(_scrollflaeche(innen), 1)
        self.termine_leer = beschriftung(t.zeitplan_leer, "hinweis_gross")
        self.termine_leer.setWordWrap(True)
        lay.addWidget(self.termine_leer)

        neu = flaeche()
        nl = QVBoxLayout(neu)
        nl.setContentsMargins(g.abstand, g.abstand, g.abstand, g.abstand)
        nl.setSpacing(g.abstand // 2)
        nl.addWidget(beschriftung(t.zeitplan_neu, "kleinueberschrift"))
        tage = QHBoxLayout()
        tage.setSpacing(g.abstand // 2)
        self._tag_gruppe = QButtonGroup(self)
        self.tag_knoepfe = []
        for nr, name in enumerate(TAGE_KURZ):
            k = knopf(name, "wahl")
            k.setCheckable(True)
            k.setMinimumWidth(70)
            self._tag_gruppe.addButton(k, nr)
            self.tag_knoepfe.append(k)
            tage.addWidget(k)
        self._tag_gruppe.idClicked.connect(lambda _n: self._termin_pruefen())
        nl.addLayout(tage)
        zeit = QHBoxLayout()
        zeit.setSpacing(g.abstand // 2)
        self.neue_zeit = QTime(19, 0)
        self.zeit_knoepfe = {}
        for text, minuten in ((t.knopf_stunde_weniger, -60), (t.knopf_minuten_weniger, -15)):
            k = knopf(text, "klein")
            k.clicked.connect(lambda _=False, m=minuten: self._zeit_aendern(m))
            self.zeit_knoepfe[minuten] = k
            zeit.addWidget(k)
        self.zeit_anzeige = beschriftung("19:00", "countdown_anzeige")
        self.zeit_anzeige.setAlignment(Qt.AlignmentFlag.AlignCenter)
        zeit.addWidget(self.zeit_anzeige, 1)
        for text, minuten in ((t.knopf_minuten_mehr, 15), (t.knopf_stunde_mehr, 60)):
            k = knopf(text, "klein")
            k.clicked.connect(lambda _=False, m=minuten: self._zeit_aendern(m))
            self.zeit_knoepfe[minuten] = k
            zeit.addWidget(k)
        nl.addLayout(zeit)
        self.termin_eintragen = knopf(t.knopf_termin_eintragen, "einblenden")
        self.termin_eintragen.clicked.connect(self._termin_eintragen)
        nl.addWidget(self.termin_eintragen)
        self.zeitplan_meldung = meldung()
        nl.addWidget(self.zeitplan_meldung)
        gesperrt_hinweis(self.termin_eintragen, self._grund_termin, self.zeitplan_meldung.kurz_zeigen)
        lay.addWidget(neu)
        return seite

    def _zeit_aendern(self, minuten: int) -> None:
        self.neue_zeit = self.neue_zeit.addSecs(minuten * 60)
        self.zeit_anzeige.setText(self.neue_zeit.toString("HH:mm"))
        self._termin_pruefen()

    def _neuer_termin(self) -> Termin | None:
        tag = self._tag_gruppe.checkedId()
        if tag < 0:
            return None
        return Termin(tag, self.neue_zeit.hour(), self.neue_zeit.minute())

    def _grund_termin(self) -> str:
        t = self.E.texte
        termin = self._neuer_termin()
        if termin is None:
            return t.gesperrt_termin_tag
        if termin in self.automatik.zeitplan:
            return t.gesperrt_termin_da
        return ""

    def _termin_pruefen(self) -> None:
        self.termin_eintragen.setEnabled(not self._grund_termin())

    def _termin_eintragen(self) -> None:
        termin = self._neuer_termin()
        if termin is None or termin in self.automatik.zeitplan:
            return
        self.automatik.zeitplan_setzen([*self.automatik.zeitplan, termin])
        self.zeitplan_meldung.zeigen(self.E.texte.meldung_termin_ok.format(termin=termin.text()), True)
        self._termin_pruefen()

    def _zeitplan_zeigen(self) -> None:
        t, g = self.E.texte, self.E.groessen
        _leeren(self._termine)
        self.termin_zeilen = []
        for termin in self.automatik.zeitplan:
            zeile = QWidget()
            zl = QHBoxLayout(zeile)
            zl.setContentsMargins(0, 0, 0, 0)
            text = beschriftung(t.zeitplan_eintrag.format(tag=t.tage_lang.split(",")[termin.tag].strip(),
                                                          zeit=termin.zeit), "meldung")
            zl.addWidget(text, 1)
            weg = _fest(knopf(t.knopf_termin_entfernen, "ausblenden"), 200)
            weg.clicked.connect(lambda _=False, tm=termin: self.automatik.zeitplan_setzen(
                [x for x in self.automatik.zeitplan if x != tm]))
            zl.addWidget(weg)
            self._termine.addWidget(zeile)
            zeile.show()
            self.termin_zeilen.append((termin, weg))
        self.termine_leer.setVisible(not self.automatik.zeitplan)
        self.naechster.setText(naechster_text(self.E, self.automatik) or t.zeitplan_kein_termin)
        self._termin_pruefen()


def naechster_text(E, automatik: Automatik) -> str:
    """„Nächster Stream: Fr 19:00“ – leer, wenn kein Termin eingetragen ist."""
    zeitpunkt = automatik.naechster_termin()
    if zeitpunkt is None:
        return ""
    return E.texte.zeitplan_naechster.format(tag=TAGE_KURZ[zeitpunkt.weekday()], zeit=zeitpunkt.strftime("%H:%M"))


class WennDannKnopf:
    """Hilfe für die Kopfleiste: Beschriftung „⚡ Wenn-dann“ mit Zahl der aktiven Regeln."""

    @staticmethod
    def text(E, automatik: Automatik) -> str:
        n = len(automatik.aktive_regeln())
        return E.texte.knopf_wenn_dann_aktiv.format(anzahl=n) if n else E.texte.knopf_wenn_dann

