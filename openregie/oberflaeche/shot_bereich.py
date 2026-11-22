"""Shots wie bei Wirecast: große Kacheln unten unter dem Live-Bild.

  ShotLeiste      – unten in der Mitte: eine Kachel pro OBS-Szene mit kleinem Vorschaubild.
                    Ein Klick schaltet den Shot sofort live (roter Rahmen = live).
                    „✎ Bearbeiten“: dann öffnet ein Klick den Shot rechts zum Bearbeiten (geht nicht live).
                    Die „+“-Kachel legt einen neuen Shot an.
  ShotBedienfeld  – rechte Spalte: Shot umbenennen/löschen, seine Quellen als Kacheln (umbenennen,
                    entfernen, hinzufügen).
  ShotNeu         – rechte Spalte: „Shot hinzufügen“ (1. Zweck, 2. Layout) bzw. „Quelle hinzufügen“.

Ressourcen: Vorschaubilder holt OpenRegie nur, solange die Leiste bzw. das Bedienfeld zu sehen ist
(zugeklappt, verdeckt oder Fenster minimiert → keine einzige Anfrage). Mit OBS spricht dieser Teil
nur über die Motor-Schicht (`ObsQuellen`).
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (QAbstractButton, QButtonGroup, QFileDialog, QGridLayout, QHBoxLayout, QLineEdit,
                               QSizePolicy, QVBoxLayout, QWidget)

from ..obs import vorlagen
from ..obs.quellen import ObsQuellen, Shot
from .bausteine import Lampe, beschriftung, gesperrt_hinweis, knopf
from .overlay_bereich import _leeren, _scrollflaeche, meldung


def _fest(k, breite: int | None = None):
    k.setSizePolicy(QSizePolicy.Policy.Fixed if breite else QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    if breite:
        k.setFixedWidth(breite)
    return k


# ---------------------------------------------------------------------------
#  Kacheln
# ---------------------------------------------------------------------------
class BildKachel(QAbstractButton):
    """Kachel mit kleinem Vorschaubild, farbigem Rahmen (rot = live) und Namen darunter."""

    def __init__(self, E, name: str, bild_hoehe: int, parent=None, symbol: str = ""):
        super().__init__(parent)
        self.E = E
        self.name = name
        self.symbol = symbol  # statt Bild (z. B. „+“)
        self.bild: QPixmap | None = None
        self.live = False
        self.bearbeiten = False  # gelber Rahmen: Klick öffnet zum Bearbeiten
        self._bild_hoehe = bild_hoehe
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(bild_hoehe + int(E.groessen.schrift) + 10)
        self.setMinimumWidth(120)
        self.auffrischen()

    def sizeHint(self) -> QSize:
        return QSize(180, self.height())

    def auffrischen(self) -> None:
        t = self.E.texte
        self.setAccessibleName(f"{self.name} – {t.shot_live}" if self.live else self.name)
        self.setToolTip(t.shot_live if self.live else self.name)
        self.update()

    def bild_setzen(self, bild: QImage) -> None:
        self.bild = QPixmap.fromImage(bild)
        self.update()

    def paintEvent(self, _e):
        f, g = self.E.farben, self.E.groessen
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        ring, dick, rund = 4, float(g.kachel_rahmen), 12.0
        box = QRectF(ring + dick / 2, ring + dick / 2, self.width() - 2 * ring - dick,
                     float(self._bild_hoehe) - 2 * ring - dick)
        if self.underMouse() or self.hasFocus() or self.isChecked():
            farbe = f.knopf_hover_rahmen if self.underMouse() else (f.knopf_fokus_rahmen if self.hasFocus()
                                                                  else f.kachel_auswahl)
            p.setPen(QPen(QColor(farbe), 3))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(box.adjusted(-ring + 1, -ring + 1, ring - 1, ring - 1), rund + ring, rund + ring)
        weg = QPainterPath()
        weg.addRoundedRect(box, rund, rund)
        p.fillPath(weg, QColor(f.flaeche_hell if self.isChecked() else f.hintergrund))
        innen = box.adjusted(dick, dick, -dick, -dick)
        if self.symbol:
            schrift = QFont(self.font())
            schrift.setPixelSize(int(g.schrift_titel) + 10)
            schrift.setWeight(QFont.Weight.Bold)
            p.setFont(schrift)
            p.setPen(QColor(f.text))
            p.drawText(innen, Qt.AlignmentFlag.AlignCenter, self.symbol)
        elif self.bild is not None and not self.bild.isNull():
            ziel = self.bild.size().scaled(innen.size().toSize(), Qt.AspectRatioMode.KeepAspectRatio)
            r = QRectF(innen.center().x() - ziel.width() / 2, innen.center().y() - ziel.height() / 2,
                       ziel.width(), ziel.height())
            p.save()
            p.setClipPath(weg)
            p.drawPixmap(r, self.bild, QRectF(self.bild.rect()))
            p.restore()
        rahmen = f.tally_an if self.live else (f.knopf_hover_rahmen if self.bearbeiten else f.tally_aus)
        stift = QPen(QColor(rahmen), dick)
        if self.bearbeiten and not self.live:
            stift.setStyle(Qt.PenStyle.DashLine)
        p.setPen(stift)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(box, rund, rund)
        schrift = QFont(self.font())
        schrift.setPixelSize(int(g.schrift_klein) + 2)
        schrift.setWeight(QFont.Weight.Bold if (self.isChecked() or self.live) else QFont.Weight.Medium)
        p.setFont(schrift)
        p.setPen(QColor(f.text))
        text_r = QRectF(ring, float(self._bild_hoehe), self.width() - 2 * ring, self.height() - float(self._bild_hoehe))
        name = p.fontMetrics().elidedText(self.name, Qt.TextElideMode.ElideRight, int(text_r.width()))
        p.drawText(text_r, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)


class _Sichtbar:
    """Hilfe: Ist dieses Element wirklich zu sehen (nicht verdeckt, Fenster nicht minimiert)?"""

    def _wirklich_sichtbar(self) -> bool:
        fenster = self.window()
        return self.isVisible() and not (fenster is not None and fenster.isMinimized())


# ---------------------------------------------------------------------------
#  Namen eintippen (mit großen Knöpfen ✓ und ✕, Enter/Esc gehen auch)
# ---------------------------------------------------------------------------
class _NamensFeld(QLineEdit):
    abbrechen = Signal()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.abbrechen.emit()
            return
        super().keyPressEvent(e)


class NamensEingabe(QWidget):
    uebernehmen = Signal(str)
    abgebrochen = Signal()

    def __init__(self, E, parent=None):
        super().__init__(parent)
        t, g = E.texte, E.groessen
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(g.abstand // 2)
        self.feld = _NamensFeld()
        self.feld.setMaxLength(80)
        self.feld.returnPressed.connect(lambda: self.uebernehmen.emit(self.feld.text()))
        self.feld.abbrechen.connect(self.abgebrochen)
        lay.addWidget(self.feld, 1)
        self.ok = _fest(knopf(t.knopf_name_ok, "zeit_ok"), int(g.knopf_hoehe))
        self.weg = _fest(knopf(t.knopf_name_weg, "zeit_weg"), int(g.knopf_hoehe))
        for k, name in ((self.ok, t.knopf_zeit_uebernehmen_name), (self.weg, t.knopf_zeit_abbrechen_name)):
            k.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            k.setToolTip(name)
            k.setAccessibleName(name)
            lay.addWidget(k)
        self.ok.clicked.connect(lambda: self.uebernehmen.emit(self.feld.text()))
        self.weg.clicked.connect(self.abgebrochen)

    def oeffnen(self, text: str) -> None:
        self.feld.setText(text)
        self.show()
        self.feld.setFocus(Qt.FocusReason.OtherFocusReason)
        self.feld.selectAll()


# ---------------------------------------------------------------------------
#  Unten: die Shot-Leiste
# ---------------------------------------------------------------------------
class ShotLeiste(QWidget, _Sichtbar):
    bearbeiten_geklickt = Signal(str)  # Name des Shots (im Bearbeiten-Modus)
    hinzufuegen_geklickt = Signal()
    bearbeiten_beendet = Signal()

    def __init__(self, E, quellen: ObsQuellen, parent=None):
        super().__init__(parent)
        self.E = E
        self.quellen = quellen
        self.standbilder = quellen.standbilder()
        self.standbilder.neues_bild.connect(self._bild)
        t, g = E.texte, E.groessen
        self.offen = True
        self.bearbeiten = False
        self.seite = 0
        self.pro_seite = 4  # passt sich der Breite an (resizeEvent)
        self._kachel_breite = int(g.shot_kachel_breite)
        self.kacheln: dict[str, BildKachel] = {}
        self._bilder: dict[str, QImage] = {}
        self._aktiv = False

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(g.abstand)

        # Links untereinander „Bearbeiten“ und „Zuklappen“, daneben die Kacheln (spart Höhe)
        links = QVBoxLayout()
        links.setSpacing(g.abstand // 2)
        self._knopf_breite = int(g.knopf_hoehe)  # quadratisch: ✎ und ▾ (Name beim Drüberfahren)
        self.knopf_bearbeiten = _fest(knopf(t.knopf_shots_bearbeiten, "quadrat"), self._knopf_breite)
        self.knopf_bearbeiten.setToolTip(t.shots_bearbeiten_hinweis)
        self.knopf_bearbeiten.setAccessibleName(t.knopf_shots_bearbeiten_name)
        self.knopf_bearbeiten.clicked.connect(lambda: self.bearbeiten_setzen(not self.bearbeiten))
        links.addWidget(self.knopf_bearbeiten)
        self.knopf_auf_zu = _fest(knopf(t.knopf_shots_zu, "quadrat"), self._knopf_breite)
        self.knopf_auf_zu.setToolTip(t.knopf_shots_zu_name)
        self.knopf_auf_zu.setAccessibleName(t.knopf_shots_zu_name)
        self.knopf_auf_zu.clicked.connect(lambda: self.offen_setzen(not self.offen))
        links.addWidget(self.knopf_auf_zu)
        links.addStretch(1)
        lay.addLayout(links)

        self.koerper = QWidget()
        kl = QVBoxLayout(self.koerper)
        kl.setContentsMargins(0, 0, 0, 0)
        kl.setSpacing(4)
        reihe = QHBoxLayout()
        reihe.setSpacing(g.abstand // 2)
        self.zurueck = _fest(knopf(t.knopf_blaettern_zurueck, "klein"), 64)
        self.zurueck.setAccessibleName(t.knopf_blaettern_zurueck_name)
        self.zurueck.setToolTip(t.knopf_blaettern_zurueck_name)
        self.zurueck.clicked.connect(lambda: self.blaettern(-1))
        reihe.addWidget(self.zurueck)
        self._reihe = QHBoxLayout()
        self._reihe.setSpacing(g.abstand // 2)
        reihe.addLayout(self._reihe, 1)
        self.vor = _fest(knopf(t.knopf_blaettern_vor, "klein"), 64)
        self.vor.setAccessibleName(t.knopf_blaettern_vor_name)
        self.vor.setToolTip(t.knopf_blaettern_vor_name)
        self.vor.clicked.connect(lambda: self.blaettern(1))
        reihe.addWidget(self.vor)
        kl.addLayout(reihe)
        self.leer = beschriftung(t.shots_keine_verbindung, "hinweis_gross")
        self.leer.setWordWrap(True)
        kl.addWidget(self.leer)
        self.meldung = meldung()
        kl.addWidget(self.meldung)
        lay.addWidget(self.koerper, 1)
        self.koerper.installEventFilter(self)

        self.plus = BildKachel(E, t.shot_hinzufuegen, int(g.shot_kachel_hoehe), symbol="+")
        self.plus.setCheckable(False)
        self.plus.clicked.connect(self.hinzufuegen_geklickt)

        self._gruppe = QButtonGroup(self)
        self._gruppe.setExclusive(False)
        quellen.geaendert.connect(self.neu_aufbauen)
        quellen.live_geaendert.connect(lambda _n: self._live_zeigen())
        self.neu_aufbauen()

    # --- Sichtbarkeit: nur dann Bilder holen ---------------------------------
    def showEvent(self, e):
        super().showEvent(e)
        self.aktiv_pruefen()

    def hideEvent(self, e):
        super().hideEvent(e)
        self.aktiv_pruefen()

    def aktiv_pruefen(self) -> None:
        """Bilder und Shot-Liste nur, wenn die Leiste offen und wirklich zu sehen ist."""
        aktiv = self.offen and self._wirklich_sichtbar()
        if aktiv != self._aktiv:
            self._aktiv = aktiv
            if aktiv:
                self.quellen.beobachten(self)
            else:
                self.quellen.loslassen(self)
        self._bilder_beobachten()

    def _bilder_beobachten(self) -> None:
        if self._aktiv:
            self.standbilder.beobachten([n for n in self._namen_auf_seite()])
        else:
            self.standbilder.anhalten()

    def eventFilter(self, obj, e):
        if obj is self.koerper and e.type() == e.Type.Resize:
            self._pro_seite_anpassen()
        return False

    def _pro_seite_anpassen(self) -> None:
        """So viele Kacheln nebeneinander, wie bei Mindestbreite passen (◀ ▶ nur, wenn nötig)."""
        sp = int(self.E.groessen.abstand) // 2
        breite = self.koerper.width()
        n = max(1, (breite + sp) // (self._kachel_breite + sp))
        if len(self._namen()) + 1 > n:
            n = max(1, (breite - 2 * (64 + sp) + sp) // (self._kachel_breite + sp))
        if n != self.pro_seite:
            self.pro_seite = n
            self.neu_aufbauen()

    def offen_setzen(self, offen: bool) -> None:
        t = self.E.texte
        self.offen = offen
        self.koerper.setVisible(offen)
        self.knopf_bearbeiten.setVisible(offen)
        self.knopf_auf_zu.setText(t.knopf_shots_zu if offen else t.knopf_shots_auf)
        self.knopf_auf_zu.setObjectName("quadrat" if offen else "")
        self.knopf_auf_zu.style().unpolish(self.knopf_auf_zu)
        self.knopf_auf_zu.style().polish(self.knopf_auf_zu)
        name = t.knopf_shots_zu_name if offen else t.knopf_shots_auf
        self.knopf_auf_zu.setToolTip(name)
        self.knopf_auf_zu.setAccessibleName(name)
        self.knopf_auf_zu.setFixedWidth(self._knopf_breite if offen else 300)
        if not offen and self.bearbeiten:
            self.bearbeiten_setzen(False)
        self.aktiv_pruefen()

    def bearbeiten_setzen(self, an: bool) -> None:
        t = self.E.texte
        if an == self.bearbeiten:
            return
        self.bearbeiten = an
        self.knopf_bearbeiten.setText(t.knopf_shots_fertig_kurz if an else t.knopf_shots_bearbeiten)
        self.knopf_bearbeiten.setToolTip(t.knopf_shots_fertig if an else t.shots_bearbeiten_hinweis)
        for k in self.kacheln.values():
            k.bearbeiten = an
            if not an:
                k.setChecked(False)
            k.update()
        if not an:
            self.bearbeiten_beendet.emit()

    def gewaehlt_setzen(self, name: str | None) -> None:
        for n, k in self.kacheln.items():
            k.setChecked(self.bearbeiten and n == name)

    # --- Aufbau ----------------------------------------------------------------
    def _namen(self) -> list[str]:
        return [s.name for s in self.quellen.shots]

    def _seiten(self) -> int:
        return max(1, -(-(len(self._namen()) + 1) // self.pro_seite))  # + 1 für die „+“-Kachel

    def _namen_auf_seite(self) -> list[str]:
        alle = self._namen()
        return alle[self.seite * self.pro_seite:(self.seite + 1) * self.pro_seite]

    def blaettern(self, richtung: int) -> None:
        self.seite = (self.seite + richtung) % self._seiten()  # am Ende geht es vorne weiter
        self.neu_aufbauen()

    def neu_aufbauen(self) -> None:
        t, g = self.E.texte, self.E.groessen
        namen = self._namen()
        for name in list(self.kacheln):
            if name not in namen:
                k = self.kacheln.pop(name)
                self._gruppe.removeButton(k)
                k.hide()
                k.deleteLater()
                self._bilder.pop(name, None)
        self.seite = min(self.seite, self._seiten() - 1)
        while self._reihe.count():
            self._reihe.takeAt(0)
        for k in self.kacheln.values():
            k.hide()
        self.plus.hide()
        auf_seite = self._namen_auf_seite()
        for name in auf_seite:
            k = self.kacheln.get(name)
            if k is None:
                k = BildKachel(self.E, name, int(g.shot_kachel_hoehe))
                k.clicked.connect(lambda _=False, n=name: self._geklickt(n))
                self._gruppe.addButton(k)
                self.kacheln[name] = k
                if name in self._bilder:
                    k.bild_setzen(self._bilder[name])
            k.bearbeiten = self.bearbeiten
            self._reihe.addWidget(k, 1)
            k.show()
        verbunden = self.quellen.verbunden and self.quellen.gelesen
        plus_hier = verbunden and len(auf_seite) < self.pro_seite
        if plus_hier:
            self._reihe.addWidget(self.plus, 1)
            self.plus.show()
        # Lücken füllen, damit die Kacheln immer gleich breit sind
        for _ in range(self.pro_seite - len(auf_seite) - (1 if plus_hier else 0)):
            platz = QWidget()
            platz.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            self._reihe.addWidget(platz, 1)
        mehrere = self._seiten() > 1
        self.zurueck.setVisible(mehrere)
        self.vor.setVisible(mehrere)
        self.leer.setVisible(not verbunden)
        self.leer.setText(t.shots_keine_verbindung)
        self._live_zeigen()
        self._bilder_beobachten()

    def _live_zeigen(self) -> None:
        live = self.quellen.live
        for name, k in self.kacheln.items():
            if k.live != (name == live):
                k.live = name == live
                k.auffrischen()

    def _bild(self, name: str, bild: QImage) -> None:
        self._bilder[name] = bild
        k = self.kacheln.get(name)
        if k is not None:
            k.bild_setzen(bild)

    def _geklickt(self, name: str) -> None:
        k = self.kacheln.get(name)
        if self.bearbeiten:
            self.gewaehlt_setzen(name)
            self.bearbeiten_geklickt.emit(name)
            return
        if k is not None:
            k.setChecked(False)
        self.meldung.zeigen("")
        self.quellen.live_schalten(name, lambda ok, text: None if ok else self.meldung.zeigen(text, False))


# ---------------------------------------------------------------------------
#  Rechts: einen Shot bearbeiten
# ---------------------------------------------------------------------------
class ShotBedienfeld(QWidget, _Sichtbar):
    quelle_hinzufuegen = Signal(str)  # Name des Shots
    fertig = Signal()  # „Zurück“

    SPALTEN = 2

    def __init__(self, E, quellen: ObsQuellen, parent=None):
        super().__init__(parent)
        self.E = E
        self.quellen = quellen
        self.standbilder = quellen.standbilder()
        self.standbilder.neues_bild.connect(self._bild)
        self.shot_name: str | None = None
        self.quelle_name: str | None = None
        self.kacheln: dict[str, BildKachel] = {}
        self._arbeitet = False
        self._aktiv = False
        self._loeschen_bestaetigen = False
        self._umbenennen_was = ""  # "shot" oder "quelle"
        t, g = E.texte, E.groessen

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(g.abstand)
        kopf = QHBoxLayout()
        kopf.setSpacing(10)
        kopf.addWidget(beschriftung(t.ausgewaehlt, "kleinueberschrift"), 1)
        self.tally = Lampe(20, E.farben.tally_aus)
        kopf.addWidget(self.tally)
        self.tally_text = beschriftung("", "tally_text")
        kopf.addWidget(self.tally_text)
        lay.addLayout(kopf)
        self.name = beschriftung("", "ueberschrift")
        self.name.setWordWrap(True)
        lay.addWidget(self.name)

        self.eingabe = NamensEingabe(E)
        self.eingabe.hide()
        self.eingabe.uebernehmen.connect(self._umbenennen_uebernehmen)
        self.eingabe.abgebrochen.connect(self._umbenennen_abbrechen)
        lay.addWidget(self.eingabe)

        reihe = QHBoxLayout()
        reihe.setSpacing(g.abstand // 2)
        self.knopf_umbenennen = knopf(t.knopf_umbenennen)
        self.knopf_umbenennen.clicked.connect(lambda: self._umbenennen_oeffnen("shot"))
        reihe.addWidget(self.knopf_umbenennen)
        self.knopf_loeschen = knopf(t.knopf_shot_loeschen, "ausblenden")
        self.knopf_loeschen.clicked.connect(self._loeschen)
        reihe.addWidget(self.knopf_loeschen)
        lay.addLayout(reihe)
        self.meldung = meldung()
        lay.addWidget(self.meldung)

        lay.addWidget(beschriftung(t.shot_quellen, "kleinueberschrift"))
        innen = QWidget()
        self._gitter = QGridLayout(innen)
        self._gitter.setContentsMargins(0, 0, 4, 0)
        self._gitter.setHorizontalSpacing(g.abstand // 2)
        self._gitter.setVerticalSpacing(g.abstand // 2)
        self._gitter.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.flaeche = _scrollflaeche(innen)
        lay.addWidget(self.flaeche, 1)
        self.leer = beschriftung(t.shot_keine_quellen, "hinweis_gross")
        self.leer.setWordWrap(True)
        lay.addWidget(self.leer)

        self.quelle_text = beschriftung("", "gedimmt")
        self.quelle_text.setWordWrap(True)
        lay.addWidget(self.quelle_text)
        reihe = QHBoxLayout()
        reihe.setSpacing(g.abstand // 2)
        self.knopf_quelle_umbenennen = knopf(t.knopf_umbenennen)
        self.knopf_quelle_umbenennen.clicked.connect(lambda: self._umbenennen_oeffnen("quelle"))
        reihe.addWidget(self.knopf_quelle_umbenennen)
        self.knopf_quelle_entfernen = knopf(t.knopf_quelle_entfernen)
        self.knopf_quelle_entfernen.clicked.connect(self._quelle_entfernen)
        reihe.addWidget(self.knopf_quelle_entfernen)
        lay.addLayout(reihe)
        reihe = QHBoxLayout()
        reihe.setSpacing(g.abstand // 2)
        self.knopf_quelle_neu = knopf(t.knopf_quelle_hinzufuegen, "einblenden")
        self.knopf_quelle_neu.clicked.connect(lambda: self.quelle_hinzufuegen.emit(self.shot_name or ""))
        reihe.addWidget(self.knopf_quelle_neu)
        self.knopf_fertig = knopf(t.knopf_shots_fertig)
        self.knopf_fertig.clicked.connect(self.fertig)
        reihe.addWidget(self.knopf_fertig)
        lay.addLayout(reihe)

        melden = self.meldung.kurz_zeigen
        gesperrt_hinweis(self.knopf_umbenennen, self._grund_shot, melden)
        gesperrt_hinweis(self.knopf_loeschen, self._grund_loeschen, melden)
        gesperrt_hinweis(self.knopf_quelle_umbenennen, self._grund_quelle, melden)
        gesperrt_hinweis(self.knopf_quelle_entfernen, self._grund_quelle, melden)
        gesperrt_hinweis(self.knopf_quelle_neu, self._grund_shot, melden)

        quellen.geaendert.connect(self._auffrischen)
        quellen.live_geaendert.connect(lambda _n: self._knoepfe())

    # --- Gründe für ausgegraute Knöpfe -----------------------------------------
    def _grund_shot(self) -> str:
        t = self.E.texte
        if not self.quellen.verbunden:
            return t.gesperrt_shot_obs
        return t.gesperrt_shot_arbeitet if self._arbeitet else ""

    def _grund_loeschen(self) -> str:
        t = self.E.texte
        grund = self._grund_shot()
        if grund:
            return grund
        if len(self.quellen.shots) <= 1:
            return t.gesperrt_shot_letzter
        if self.shot_name == self.quellen.live:
            return t.gesperrt_shot_live
        return ""

    def _grund_quelle(self) -> str:
        return self._grund_shot() or ("" if self.quelle_name else self.E.texte.gesperrt_keine_quelle)

    # --- Sichtbarkeit ----------------------------------------------------------
    def showEvent(self, e):
        super().showEvent(e)
        self.aktiv_pruefen()

    def hideEvent(self, e):
        super().hideEvent(e)
        self.aktiv_pruefen()

    def aktiv_pruefen(self) -> None:
        aktiv = self._wirklich_sichtbar() and self.shot_name is not None
        if aktiv != self._aktiv:
            self._aktiv = aktiv
            if aktiv:
                self.quellen.beobachten(self)
            else:
                self.quellen.loslassen(self)
        self.standbilder.beobachten(list(self.kacheln) if aktiv else [])

    # --- Zeigen ----------------------------------------------------------------
    def zeigen(self, shot_name: str) -> None:
        if shot_name != self.shot_name:
            self.quelle_name = None
            self._loeschen_bestaetigen = False
            self.meldung.zeigen("")
            self._umbenennen_abbrechen()
        self.shot_name = shot_name
        self._auffrischen()
        self.aktiv_pruefen()

    def _shot(self) -> Shot | None:
        return self.quellen.shot(self.shot_name) if self.shot_name else None

    def _auffrischen(self) -> None:
        g = self.E.groessen
        shot = self._shot()
        if shot is not None:
            self.name.setText(shot.name)
        quellen = shot.eigene_quellen() if shot else []
        namen = [q.name for q in quellen]
        for name in list(self.kacheln):
            if name not in namen:
                k = self.kacheln.pop(name)
                k.hide()
                k.deleteLater()
        while self._gitter.count():
            self._gitter.takeAt(0)
        for nr, q in enumerate(quellen):
            k = self.kacheln.get(q.name)
            if k is None:
                k = BildKachel(self.E, q.name, int(g.quelle_kachel_hoehe))
                k.clicked.connect(lambda _=False, n=q.name: self._quelle_waehlen(n))
                self.kacheln[q.name] = k
            k.setChecked(q.name == self.quelle_name)
            self._gitter.addWidget(k, nr // self.SPALTEN, nr % self.SPALTEN)
            k.show()
        if self.quelle_name not in self.kacheln:
            self.quelle_name = None
        self.leer.setVisible(not quellen)
        self._knoepfe()
        if self._aktiv:
            self.standbilder.beobachten(list(self.kacheln))

    def _knoepfe(self) -> None:
        t = self.E.texte
        live = self.shot_name is not None and self.shot_name == self.quellen.live
        self.tally.farbe_setzen(self.E.farben.tally_an if live else self.E.farben.tally_aus)
        self.tally_text.setText(t.shot_live if live else "")
        self.knopf_umbenennen.setEnabled(not self._grund_shot())
        self.knopf_loeschen.setEnabled(not self._grund_loeschen())
        if self._grund_loeschen():
            self._loeschen_bestaetigen = False
        self.knopf_loeschen.setText(t.knopf_wirklich_loeschen if self._loeschen_bestaetigen else t.knopf_shot_loeschen)
        self.knopf_quelle_umbenennen.setEnabled(not self._grund_quelle())
        self.knopf_quelle_entfernen.setEnabled(not self._grund_quelle())
        self.knopf_quelle_neu.setEnabled(not self._grund_shot())
        self.quelle_text.setText(t.quelle_ausgewaehlt.format(name=self.quelle_name) if self.quelle_name else "")
        self.quelle_text.setVisible(bool(self.quelle_name))
        for n, k in self.kacheln.items():
            k.setChecked(n == self.quelle_name)

    def _bild(self, name: str, bild: QImage) -> None:
        k = self.kacheln.get(name)
        if k is not None:
            k.bild_setzen(bild)

    def _quelle_waehlen(self, name: str) -> None:
        self.quelle_name = name
        self._knoepfe()

    # --- Umbenennen ---------------------------------------------------------------
    def _umbenennen_oeffnen(self, was: str) -> None:
        self._umbenennen_was = was
        self.eingabe.oeffnen(self.shot_name if was == "shot" else (self.quelle_name or ""))

    def _umbenennen_abbrechen(self) -> None:
        self.eingabe.hide()
        self._umbenennen_was = ""

    def _umbenennen_uebernehmen(self, neu: str) -> None:
        was = self._umbenennen_was
        alt = self.shot_name if was == "shot" else self.quelle_name
        if not was or not alt or self._arbeitet:
            return
        self._arbeitet = True
        self._knoepfe()

        def fertig(ok, text):
            self._arbeitet = False
            if ok:
                if was == "shot":
                    self.shot_name = text
                    self.name.setText(text)
                else:
                    self.quelle_name = text  # die Kachel kommt mit dem neuen Namen, sobald OBS es meldet
                self._umbenennen_abbrechen()
                self.meldung.zeigen(self.E.texte.meldung_umbenannt.format(name=text), True)
            else:
                self.meldung.zeigen(text, False)
            self._knoepfe()

        if was == "shot":
            self.quellen.shot_umbenennen(alt, neu, fertig)
        else:
            self.quellen.quelle_umbenennen(alt, neu, fertig)

    # --- Löschen ------------------------------------------------------------------
    def _loeschen(self) -> None:
        if not self._loeschen_bestaetigen:
            self._loeschen_bestaetigen = True
            self._knoepfe()
            return
        self._loeschen_bestaetigen = False
        name = self.shot_name
        self._arbeitet = True
        self._knoepfe()

        def fertig(ok, text):
            self._arbeitet = False
            self.meldung.zeigen(text, ok)
            if ok:
                self.shot_name = None
                self.aktiv_pruefen()
                self.fertig.emit()
            self._knoepfe()

        self.quellen.shot_loeschen(name, fertig)

    def _quelle_entfernen(self) -> None:
        shot, quelle = self.shot_name, self.quelle_name
        if not shot or not quelle:
            return
        self._arbeitet = True
        self._knoepfe()

        def fertig(ok, text):
            self._arbeitet = False
            self.meldung.zeigen(text, ok)
            if ok:
                self.quelle_name = None
            self._knoepfe()

        self.quellen.quelle_entfernen(shot, quelle, fertig)


# ---------------------------------------------------------------------------
#  Rechts: Shot hinzufügen (Zweck + Layout) bzw. Quelle hinzufügen (Art)
# ---------------------------------------------------------------------------
class _LayoutBild(QWidget):
    """Kleine Zeichnung eines Layouts: großes Bild grau, Kamera gelb."""

    def __init__(self, E, layout: str, parent=None):
        super().__init__(parent)
        self.E, self.layout = E, layout
        self.setFixedSize(64, 36)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def paintEvent(self, _e):
        f = self.E.farben
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(f.text_gedimmt), 1))
        p.setBrush(QColor(f.hintergrund))
        p.drawRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1))
        for rolle, (x, y, b, h) in vorlagen.LAYOUTS[self.layout].rechtecke.items():
            r = QRectF(x * self.width(), y * self.height(), b * self.width(), h * self.height()).adjusted(2, 2, -2, -2)
            p.setBrush(QColor(f.logo if rolle == vorlagen.KAMERA else f.knopf_hover))
            p.drawRect(r)


class ShotNeu(QWidget):
    fertig = Signal(str)  # Name des Shots, der danach gezeigt werden soll ("" = abgebrochen)

    def __init__(self, E, quellen: ObsQuellen, parent=None):
        super().__init__(parent)
        self.E = E
        self.quellen = quellen
        self.modus = "shot"  # oder "quelle"
        self.fuer_shot = ""
        self.zweck: str | None = None
        self.layout_wahl: str | None = None
        self.art: str | None = None
        self._arbeitet = False
        self._datei_waehlen = self._datei_dialog  # in Tests ersetzbar
        t, g = E.texte, E.groessen

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(g.abstand)
        self.titel = beschriftung(t.shot_hinzufuegen, "ueberschrift")
        lay.addWidget(self.titel)
        innen = QWidget()
        self._innen = QVBoxLayout(innen)
        self._innen.setContentsMargins(0, 0, 4, 0)
        self._innen.setSpacing(g.abstand // 2)
        self._innen.setAlignment(Qt.AlignmentFlag.AlignTop)
        lay.addWidget(_scrollflaeche(innen), 1)
        self.hinweis = beschriftung("", "gedimmt")
        self.hinweis.setWordWrap(True)
        lay.addWidget(self.hinweis)
        self.meldung = meldung()
        lay.addWidget(self.meldung)
        reihe = QHBoxLayout()
        reihe.setSpacing(g.abstand // 2)
        self.anlegen = knopf(t.knopf_shot_anlegen, "einblenden")
        self.anlegen.clicked.connect(self._anlegen)
        reihe.addWidget(self.anlegen)
        self.zurueck = knopf(t.knopf_zurueck)
        self.zurueck.clicked.connect(lambda: self.fertig.emit(""))
        reihe.addWidget(self.zurueck)
        lay.addLayout(reihe)
        gesperrt_hinweis(self.anlegen, self._grund_anlegen, self.meldung.kurz_zeigen)
        self.zweck_knoepfe: dict[str, QAbstractButton] = {}
        self.layout_knoepfe: dict[str, QAbstractButton] = {}
        self.art_knoepfe: dict[str, QAbstractButton] = {}

    def _grund_anlegen(self) -> str:
        t = self.E.texte
        if not self.quellen.verbunden:
            return t.gesperrt_shot_obs
        if self._arbeitet:
            return t.gesperrt_shot_arbeitet
        if self.modus == "shot" and not self.zweck:
            return t.gesperrt_zweck_fehlt
        if self.modus == "quelle" and not self.art:
            return t.gesperrt_zweck_fehlt
        return ""

    def _wahlknopf(self, text: str, gruppe: QButtonGroup, beim_klick) -> QAbstractButton:
        k = knopf(text)
        k.setCheckable(True)
        k.setObjectName("wahl")
        gruppe.addButton(k)
        k.clicked.connect(beim_klick)
        return k

    def shot_zeigen(self) -> None:
        """„+“ in der Shot-Leiste: 1. Zweck, 2. Layout."""
        t = self.E.texte
        self.modus, self.fuer_shot = "shot", ""
        self.zweck, self.layout_wahl, self.art = None, None, None
        self.titel.setText(t.shot_hinzufuegen)
        self.anlegen.setText(t.knopf_shot_anlegen)
        self.meldung.zeigen("")
        self._aufbauen()

    def quelle_zeigen(self, shot: str) -> None:
        t = self.E.texte
        self.modus, self.fuer_shot = "quelle", shot
        self.zweck, self.layout_wahl, self.art = None, None, None
        self.titel.setText(t.knopf_quelle_hinzufuegen.strip("+ ").strip())
        self.anlegen.setText(t.knopf_quelle_anlegen)
        self.meldung.zeigen("")
        self._aufbauen()

    def _aufbauen(self) -> None:
        t, g = self.E.texte, self.E.groessen
        _leeren(self._innen)
        self.zweck_knoepfe, self.layout_knoepfe, self.art_knoepfe = {}, {}, {}
        if self.modus == "shot":
            self._innen.addWidget(beschriftung(t.shot_neu_schritt_zweck, "kleinueberschrift"))
            gitter = QGridLayout()
            gitter.setSpacing(g.abstand // 2)
            self._zweck_gruppe = QButtonGroup(self)
            for nr, (s, z) in enumerate(vorlagen.ZWECKE.items()):
                k = self._wahlknopf(f"{z.symbol}  {getattr(t, 'zweck_' + s)}", self._zweck_gruppe,
                                    lambda _=False, s=s: self._zweck_waehlen(s))
                self.zweck_knoepfe[s] = k
                gitter.addWidget(k, nr // 3, nr % 3)
            self._innen.addLayout(gitter)
            self._layout_titel = beschriftung(t.shot_neu_schritt_layout, "kleinueberschrift")
            self._innen.addWidget(self._layout_titel)
            self._layout_flaeche = QGridLayout()
            self._layout_flaeche.setSpacing(g.abstand // 2)
            self._innen.addLayout(self._layout_flaeche)
            self._layout_titel.hide()
        else:
            self._innen.addWidget(beschriftung(t.shot_neu_quelle_art, "kleinueberschrift"))
            gitter = QGridLayout()
            gitter.setSpacing(g.abstand // 2)
            self._art_gruppe = QButtonGroup(self)
            for nr, s in enumerate(vorlagen.ARTEN_ZUM_HINZUFUEGEN):
                a = vorlagen.QUELLENARTEN[s]
                k = self._wahlknopf(f"{a.symbol}  {getattr(t, 'art_' + s)}", self._art_gruppe,
                                    lambda _=False, s=s: self._art_waehlen(s))
                self.art_knoepfe[s] = k
                gitter.addWidget(k, nr // 2, nr % 2)
            self._innen.addLayout(gitter)
        self._hinweis_setzen()
        self.anlegen.setEnabled(not self._grund_anlegen())

    def _zweck_waehlen(self, zweck: str) -> None:
        t, g = self.E.texte, self.E.groessen
        self.zweck = zweck
        z = vorlagen.ZWECKE[zweck]
        self.layout_wahl = z.layouts[0]  # Vorschlag ist gleich ausgewählt (Layout ist Pflicht)
        _leeren(self._layout_flaeche)
        self.layout_knoepfe = {}
        self._layout_gruppe = QButtonGroup(self)
        for s in z.layouts:
            k = self._wahlknopf(getattr(t, "layout_" + s), self._layout_gruppe,
                                lambda _=False, s=s: self._layout_waehlen(s))
            k.setObjectName("wahl_bild")  # Platz links für die kleine Zeichnung
            bild = _LayoutBild(self.E, s, k)
            bild.move(14, (int(g.knopf_hoehe) - bild.height()) // 2)
            k.setChecked(s == self.layout_wahl)
            nr = len(self.layout_knoepfe)
            self.layout_knoepfe[s] = k
            self._layout_flaeche.addWidget(k, nr // 2, nr % 2)
            k.show()  # sofort anklickbar (Qt zeigt neue Knöpfe sonst erst etwas später)
        self._layout_titel.show()
        self._hinweis_setzen()
        self.anlegen.setEnabled(not self._grund_anlegen())

    def _layout_waehlen(self, layout: str) -> None:
        self.layout_wahl = layout

    def _art_waehlen(self, art: str) -> None:
        self.art = art
        self._hinweis_setzen()
        self.anlegen.setEnabled(not self._grund_anlegen())

    def _haupt_art(self) -> str | None:
        if self.modus == "shot":
            return vorlagen.ZWECKE[self.zweck].haupt if self.zweck else None
        return self.art

    def _hinweis_setzen(self) -> None:
        t = self.E.texte
        art = self._haupt_art()
        text = ""
        if art in ("bildschirm", "spiel", "fenster"):
            text = t.shot_neu_bildschirm_hinweis
        elif art == "bild":
            text = t.shot_neu_bild_hinweis
        self.hinweis.setText(text)
        self.hinweis.setVisible(bool(text))

    def _datei_dialog(self) -> str:
        datei, _ = QFileDialog.getOpenFileName(self, self.E.texte.bild_auswaehlen, "",
                                               "Bilder (*.png *.jpg *.jpeg *.webp *.gif *.bmp)")
        return datei

    def _anlegen(self) -> None:
        if self._grund_anlegen():
            return
        t = self.E.texte
        datei = ""
        if self._haupt_art() == "bild":
            datei = self._datei_waehlen()
            if not datei:
                self.meldung.zeigen(t.meldung_kein_bild, False)
                return
        self._arbeitet = True
        self.anlegen.setEnabled(False)
        self.meldung.zeigen(t.shot_neu_laeuft)

        def fertig(ok, text):
            self._arbeitet = False
            self.anlegen.setEnabled(not self._grund_anlegen())
            if not ok:
                self.meldung.zeigen(text, False)
                return
            if self.modus == "shot":
                name = text if self.quellen.shot(text) is not None or "„" not in text else self._name_aus(text)
                self.meldung.zeigen(t.meldung_shot_angelegt.format(name=name), True)
                self.fertig.emit(name)
            else:
                self.meldung.zeigen(text, True)
                self.fertig.emit(self.fuer_shot)

        if self.modus == "shot":
            self.quellen.shot_anlegen(self.zweck, self.layout_wahl, fertig, datei=datei)
        else:
            self.quellen.quelle_hinzufuegen(self.fuer_shot, self.art, fertig, datei=datei)

    @staticmethod
    def _name_aus(text: str) -> str:
        """Aus „Der Shot „X“ ist da – …“ den Namen X holen (Meldung „ohne Kamera“)."""
        return text.split("„", 1)[1].split("“", 1)[0] if "„" in text else text
