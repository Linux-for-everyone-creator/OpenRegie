"""Alles zu den Uno-Overlays im Fenster (Aussehen nach dem Entwurf „Hauptfenster“).

  Bibliothek        – linke Spalte: Kacheln mit Vorschau. Der farbige Rahmen ist die Lampe:
                      rot = Live (im Stream), grün = Bereit, grau = Aus (Uno nicht erreichbar).
  OverlayBedienfeld – rechte Spalte „AUSGEWÄHLT“: Countdown-Steuerung, Texte und unten
                      die großen Knöpfe „Einblenden“ und „Ausblenden“.
  UnoEinrichtung    – rechte Spalte: Uno-Projekte einfügen und entfernen.

Bedienung nur mit einfachem Klick. Texte werden in große Felder getippt.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (QAbstractButton, QButtonGroup, QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

from ..uno import einzel
from ..uno.verwaltung import Overlay, UnoProjekt, UnoVerwaltung
from .bausteine import Lampe, beschriftung, knopf

LIVE, BEREIT, AUS = "live", "bereit", "aus"


def lampen_zustand(overlay: Overlay) -> str:
    if overlay.sichtbar:
        return LIVE
    if overlay.projekt.erreichbar is False:
        return AUS
    if overlay.projekt.einzeln and overlay.bauplan is None:
        return AUS  # noch nicht von Uno gelesen
    return BEREIT


def lampen_farbe(E, zustand: str) -> str:
    return {LIVE: E.farben.tally_an, BEREIT: E.farben.tally_bereit, AUS: E.farben.tally_aus}[zustand]


def lampen_text(E, zustand: str) -> str:
    return {LIVE: E.texte.lampe_live, BEREIT: E.texte.lampe_bereit, AUS: E.texte.lampe_aus}[zustand]


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


def _neu_zeichnen(w: QWidget, name: str) -> None:
    w.setObjectName(name)
    w.style().unpolish(w)
    w.style().polish(w)


class _Meldung(QLabel):
    """Grüne oder rote Rückmeldung unter einem Knopf."""

    def zeigen(self, text: str, erfolg: bool | None = None) -> None:
        _neu_zeichnen(self, "gut" if erfolg else ("fehler" if erfolg is False else "meldung"))
        self.setText(text)
        self.setVisible(bool(text))


def meldung() -> _Meldung:
    m = _Meldung("")
    m.setWordWrap(True)
    m.setObjectName("meldung")
    m.setVisible(False)
    return m


def _fest(k, breite: int | None = None):
    k.setSizePolicy(QSizePolicy.Policy.Fixed if breite else QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    if breite:
        k.setFixedWidth(breite)
    return k


# ---------------------------------------------------------------------------
#  Kachel in der Bibliothek
# ---------------------------------------------------------------------------
class OverlayKachel(QAbstractButton):
    """Eine Kachel: Vorschau (Bild, Countdown-Zeit oder Platzhalter) mit Lampen-Rahmen, Name darunter."""

    def __init__(self, E, overlay: Overlay, parent=None):
        super().__init__(parent)
        self.E = E
        self.overlay = overlay
        self.bild: QPixmap | None = None
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(int(E.groessen.kachel_hoehe) + int(E.groessen.schrift) + 22)
        self.auffrischen()

    def sizeHint(self) -> QSize:
        return QSize(200, self.height())

    @property
    def zustand(self) -> str:
        return lampen_zustand(self.overlay)

    def auffrischen(self) -> None:
        z = self.zustand
        self.setAccessibleName(f"{self.overlay.name} – {lampen_text(self.E, z)}")
        self.setToolTip(lampen_text(self.E, z))
        self.update()

    def bild_setzen(self, daten: bytes | None) -> None:
        if daten:
            pix = QPixmap()
            if pix.loadFromData(daten):
                self.bild = pix
                self.update()

    def zeit_text(self) -> str:
        return einzel.zeit_text(self.overlay.restzeit_ms())

    def paintEvent(self, _e):
        f, g = self.E.farben, self.E.groessen
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        ring = 4  # Platz für Auswahl-/Zeiger-Ring
        dick = float(g.kachel_rahmen)
        box = QRectF(ring + dick / 2, ring + dick / 2, self.width() - 2 * ring - dick,
                     float(g.kachel_hoehe) - 2 * ring - dick)
        rund = 12.0

        # Ring außen: gelb = Zeiger darüber, blau = ausgewählt bzw. Tastatur-Auswahl
        if self.underMouse() or self.hasFocus() or self.isChecked():
            farbe = f.knopf_hover_rahmen if self.underMouse() else (f.knopf_fokus_rahmen if self.hasFocus()
                                                                  else f.kachel_auswahl)
            p.setPen(QPen(QColor(farbe), 3))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(box.adjusted(-ring + 1, -ring + 1, ring - 1, ring - 1), rund + ring, rund + ring)

        weg = QPainterPath()
        weg.addRoundedRect(box, rund, rund)
        p.fillPath(weg, QColor(f.flaeche_hell if self.isChecked() else f.hintergrund))

        innen = box.adjusted(dick + 4, dick + 4, -dick - 4, -dick - 4)
        if self.overlay.hat_countdown:
            schrift = QFont(self.font())
            schrift.setPixelSize(int(g.schrift_kachel_zeit))
            schrift.setWeight(QFont.Weight.Bold)
            p.setFont(schrift)
            p.setPen(QColor(f.text))
            p.drawText(innen, Qt.AlignmentFlag.AlignCenter, self.zeit_text())
        elif self.bild is not None and not self.bild.isNull():
            ziel = self.bild.size().scaled(innen.size().toSize(), Qt.AspectRatioMode.KeepAspectRatio)
            r = QRectF(innen.center().x() - ziel.width() / 2, innen.center().y() - ziel.height() / 2,
                       ziel.width(), ziel.height())
            p.save()
            p.setClipPath(weg)
            p.drawPixmap(r, self.bild, QRectF(self.bild.rect()))
            p.restore()
        else:
            # Platzhalter im Stil einer Bauchbinde
            h = innen.height()
            p.fillRect(QRectF(innen.left() + 12, innen.top() + h * 0.55, innen.width() * 0.6, h * 0.16),
                       QColor(f.logo))
            p.fillRect(QRectF(innen.left() + 12, innen.top() + h * 0.71, innen.width() * 0.42, h * 0.1),
                       QColor(f.flaeche_hell))

        p.setPen(QPen(QColor(lampen_farbe(self.E, self.zustand)), dick))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(box, rund, rund)

        # Name unter der Kachel
        schrift = QFont(self.font())
        schrift.setPixelSize(int(g.schrift))
        schrift.setWeight(QFont.Weight.Bold if self.isChecked() else QFont.Weight.Medium)
        p.setFont(schrift)
        p.setPen(QColor(f.text))
        text_r = QRectF(ring, float(g.kachel_hoehe), self.width() - 2 * ring, self.height() - float(g.kachel_hoehe))
        name = p.fontMetrics().elidedText(self.overlay.name, Qt.TextElideMode.ElideRight, int(text_r.width()))
        p.drawText(text_r, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)


class Bibliothek(QWidget):
    """Linke Spalte: Überschrift mit [↻] [+], Kacheln in zwei Spalten, Lampen-Erklärung."""

    gewaehlt = Signal(str)  # Schlüssel des Overlays ("" = keins)
    einrichten_geklickt = Signal()

    SPALTEN = 2

    def __init__(self, E, uno: UnoVerwaltung, parent=None):
        super().__init__(parent)
        self.E = E
        self.uno = uno
        t, g, f = E.texte, E.groessen, E.farben
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(g.abstand)

        kopf = QHBoxLayout()
        kopf.addWidget(beschriftung(t.overlays_ueberschrift, "ueberschrift"), 1)
        self.knopf_neu = _fest(knopf(t.knopf_liste_neu, "quadrat"), int(g.knopf_hoehe))
        self.knopf_neu.setAccessibleName(t.knopf_liste_neu_name)
        self.knopf_neu.setToolTip(t.knopf_liste_neu_name)
        self.knopf_neu.clicked.connect(lambda: self.uno.auffrischen())
        kopf.addWidget(self.knopf_neu)
        self.knopf_einrichten = _fest(knopf(t.knopf_uno_einrichten, "quadrat"), int(g.knopf_hoehe))
        self.knopf_einrichten.setAccessibleName(t.knopf_uno_einrichten_name)
        self.knopf_einrichten.setToolTip(t.knopf_uno_einrichten_name)
        self.knopf_einrichten.clicked.connect(self.einrichten_geklickt)
        kopf.addWidget(self.knopf_einrichten)
        lay.addLayout(kopf)

        innen = QWidget()
        self._gitter = QGridLayout(innen)
        self._gitter.setContentsMargins(0, 0, 4, 0)
        self._gitter.setHorizontalSpacing(g.abstand)
        self._gitter.setVerticalSpacing(g.abstand // 2)
        self._gitter.setAlignment(Qt.AlignmentFlag.AlignTop)
        lay.addWidget(_scrollflaeche(innen), 1)

        self.leer = beschriftung(t.overlays_leer, "hinweis_gross")
        self.leer.setWordWrap(True)
        lay.addWidget(self.leer)
        self.meldung = meldung()
        lay.addWidget(self.meldung)

        # Lampen-Erklärung wie im Entwurf
        linie = QFrame()
        linie.setObjectName("trennlinie")
        linie.setFixedHeight(2)
        lay.addWidget(linie)
        lay.addWidget(beschriftung(t.lampen_ueberschrift, "kleinueberschrift"))
        legende = QHBoxLayout()
        legende.setSpacing(10)
        for farbe, text in ((f.tally_an, t.lampe_live), (f.tally_bereit, t.lampe_bereit), (f.tally_aus, t.lampe_aus)):
            legende.addWidget(Lampe(16, farbe))
            legende.addWidget(beschriftung(text))
            legende.addSpacing(12)
        legende.addStretch(1)
        lay.addLayout(legende)

        self._gruppe = QButtonGroup(self)
        self._gruppe.setExclusive(True)
        self.kacheln: dict[str, OverlayKachel] = {}
        self.gewaehlter: str | None = None

        # Countdown-Kacheln zählen sichtbar mit
        self._uhr = QTimer(self)
        self._uhr.setInterval(250)
        self._uhr.timeout.connect(self._zeit_auffrischen)
        self._uhr.start()

        uno.liste_geaendert.connect(self.neu_aufbauen)
        uno.overlay_geaendert.connect(self._overlay_geaendert)
        self.neu_aufbauen()

    def neu_aufbauen(self) -> None:
        for schluessel in list(self.kacheln):
            k = self.kacheln[schluessel]
            if self.uno.overlays.get(schluessel) is not k.overlay:
                del self.kacheln[schluessel]
                self._gruppe.removeButton(k)
                k.hide()
                k.deleteLater()
        for k in self.kacheln.values():
            self._gitter.removeWidget(k)
        for nr, (schluessel, overlay) in enumerate(self.uno.overlays.items()):
            k = self.kacheln.get(schluessel)
            if k is None:
                k = OverlayKachel(self.E, overlay)
                k.clicked.connect(lambda _=False, s=schluessel: self.waehlen(s))
                self._gruppe.addButton(k)
                self.kacheln[schluessel] = k
                if overlay.vorschaubild:
                    self.uno.bild_laden(overlay, k.bild_setzen)
            self._gitter.addWidget(k, nr // self.SPALTEN, nr % self.SPALTEN)
            k.show()
            k.auffrischen()
        self.leer.setVisible(not self.kacheln)
        if self.gewaehlter is not None and self.gewaehlter not in self.kacheln:
            self.gewaehlter = None
            self.gewaehlt.emit("")
        elif self.gewaehlter in self.kacheln:
            self.kacheln[self.gewaehlter].setChecked(True)

    def waehlen(self, schluessel: str) -> None:
        k = self.kacheln.get(schluessel)
        if k is None:
            return
        k.setChecked(True)
        self.gewaehlter = schluessel
        self.gewaehlt.emit(schluessel)

    def auswahl_aufheben(self) -> None:
        self._gruppe.setExclusive(False)
        for k in self.kacheln.values():
            k.setChecked(False)
        self._gruppe.setExclusive(True)
        self.gewaehlter = None

    def _overlay_geaendert(self, overlay: Overlay) -> None:
        k = self.kacheln.get(overlay.schluessel)
        if k is not None:
            k.auffrischen()

    def _zeit_auffrischen(self) -> None:
        for k in self.kacheln.values():
            if k.overlay.hat_countdown:
                k.update()


# ---------------------------------------------------------------------------
#  Rechte Spalte: AUSGEWÄHLT
# ---------------------------------------------------------------------------
class OverlayBedienfeld(QWidget):
    def __init__(self, E, uno: UnoVerwaltung, parent=None):
        super().__init__(parent)
        self.E = E
        self.uno = uno
        self.overlay: Overlay | None = None
        self.eingaben: dict[tuple[str, str], QLineEdit] = {}
        self._felder: dict[tuple[str, str], object] = {}
        self._stand: dict[tuple[str, str], str] = {}  # letzter bekannter Text pro Feld
        t, g = E.texte, E.groessen

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(g.abstand)
        kopf = QVBoxLayout()
        kopf.setSpacing(2)
        kopf.addWidget(beschriftung(t.ausgewaehlt, "kleinueberschrift"))
        self.name = beschriftung("", "ueberschrift")
        self.name.setWordWrap(True)
        kopf.addWidget(self.name)
        lay.addLayout(kopf)

        zustand = QHBoxLayout()
        zustand.setSpacing(10)
        self.tally = Lampe(20, E.farben.tally_aus)
        zustand.addWidget(self.tally)
        self.tally_text = beschriftung("", "tally_text")
        zustand.addWidget(self.tally_text, 1)
        lay.addLayout(zustand)

        # --- Countdown (nur bei Overlays mit Zeitgeber) ---------------------
        self.countdown = QWidget()
        cl = QVBoxLayout(self.countdown)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(g.abstand // 2)
        self.zeit = beschriftung("--:--", "countdown_anzeige")
        self.zeit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(self.zeit)
        self.countdown_zustand = beschriftung("", "gedimmt")
        self.countdown_zustand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(self.countdown_zustand)
        reihe = QHBoxLayout()
        reihe.setSpacing(g.abstand // 2)
        self.start = knopf(t.knopf_countdown_start, "einblenden")
        self.start.clicked.connect(lambda: self._timer("play"))
        self.pause = knopf(t.knopf_countdown_pause, "klein")
        self.pause.clicked.connect(lambda: self._timer("pause"))
        self.zurueck = knopf(t.knopf_countdown_reset, "klein")
        self.zurueck.clicked.connect(lambda: self._timer("reset"))
        for k in (self.start, self.pause, self.zurueck):
            reihe.addWidget(k)
        cl.addLayout(reihe)
        cl.addWidget(beschriftung(t.countdown_dauer, "feldname"))
        dauer = QHBoxLayout()
        dauer.setSpacing(g.abstand // 2)
        self.dauer_knoepfe = {}
        for schritt, text in ((-600, "−10 Min"), (-60, "−1 Min"), (60, "+1 Min"), (600, "+10 Min")):
            k = knopf(text, "klein")
            k.clicked.connect(lambda _=False, s=schritt: self._dauer(s))
            dauer.addWidget(k)
            self.dauer_knoepfe[schritt] = k
        cl.addLayout(dauer)
        lay.addWidget(self.countdown)

        # --- Texte -----------------------------------------------------------
        self.texte_kopf = beschriftung(t.overlay_texte, "kleinueberschrift")
        lay.addWidget(self.texte_kopf)
        innen = QWidget()
        self._felder_lay = QVBoxLayout(innen)
        self._felder_lay.setContentsMargins(0, 0, 8, 0)
        self._felder_lay.setSpacing(6)
        lay.addWidget(_scrollflaeche(innen), 1)
        texte_reihe = QHBoxLayout()
        texte_reihe.setSpacing(g.abstand // 2)
        self.knopf_uebernehmen = knopf(t.knopf_texte_uebernehmen)
        self.knopf_uebernehmen.clicked.connect(self.texte_uebernehmen)
        texte_reihe.addWidget(self.knopf_uebernehmen, 2)
        self.knopf_texte_neu = knopf(t.knopf_texte_neu)
        self.knopf_texte_neu.clicked.connect(self.texte_laden)
        texte_reihe.addWidget(self.knopf_texte_neu, 1)
        lay.addLayout(texte_reihe)
        self.meldung_texte = meldung()
        lay.addWidget(self.meldung_texte)

        # --- Einblenden / Ausblenden (unten, groß) ----------------------------
        self.meldung_schalter = meldung()
        lay.addWidget(self.meldung_schalter)
        unten = QHBoxLayout()
        unten.setSpacing(g.abstand)
        self.einblenden = knopf(t.knopf_einblenden, "einblenden")
        self.einblenden.clicked.connect(lambda: self._sichtbar(True))
        self.ausblenden = knopf(t.knopf_ausblenden, "ausblenden")
        self.ausblenden.clicked.connect(lambda: self._sichtbar(False))
        unten.addWidget(self.einblenden)
        unten.addWidget(self.ausblenden)
        lay.addLayout(unten)

        self._uhr = QTimer(self)
        self._uhr.setInterval(250)
        self._uhr.timeout.connect(self._countdown_zeigen)
        self._uhr.start()
        uno.overlay_geaendert.connect(self._overlay_geaendert)

    # ------------------------------------------------------------------
    def zeigen(self, overlay: Overlay) -> None:
        self.overlay = overlay
        self.meldung_schalter.zeigen("")
        self.meldung_texte.zeigen("")
        self._zustand_zeigen()
        self._felder_aufbauen([], self.E.texte.overlay_texte_laden)
        self.texte_laden()

    def _zustand_zeigen(self) -> None:
        o, t, f = self.overlay, self.E.texte, self.E.farben
        if o is None:
            return
        self.name.setText(o.name)
        z = lampen_zustand(o)
        self.tally.farbe_setzen(lampen_farbe(self.E, z))
        if o.sichtbar:
            self.tally_text.setText(t.overlay_im_stream)
            self.tally_text.setStyleSheet(f"color: {f.tally_an};")
        else:
            self.tally_text.setText(t.overlay_ausgeblendet if o.sichtbar is False else t.overlay_unbekannt)
            self.tally_text.setStyleSheet(f"color: {f.text_gedimmt};")
        self.einblenden.setEnabled(not o.beschaeftigt and o.sichtbar is not True)
        self.ausblenden.setEnabled(not o.beschaeftigt and o.sichtbar is not False)
        self.countdown.setVisible(o.hat_countdown)
        hat_dauer = bool(o.bauplan and o.bauplan.dauer)
        for k in self.dauer_knoepfe.values():
            k.setEnabled(hat_dauer)
        self._countdown_zeigen()

    def _countdown_zeigen(self) -> None:
        o, t = self.overlay, self.E.texte
        if o is None or not o.hat_countdown:
            return
        rest = o.restzeit_ms()
        self.zeit.setText(einzel.zeit_text(rest))
        laeuft = bool(o.timer and o.timer.get("isRunning"))
        if rest == 0:
            zustand = t.countdown_abgelaufen
        elif laeuft:
            zustand = t.countdown_laeuft
        elif o.timer and float(o.timer.get("value") or 0) > 0:
            zustand = t.countdown_pausiert
        else:
            zustand = t.countdown_bereit
        self.countdown_zustand.setText(zustand)
        self.start.setEnabled(not laeuft and rest != 0)
        self.pause.setEnabled(laeuft)

    def _overlay_geaendert(self, overlay: Overlay) -> None:
        if overlay is self.overlay:
            self._zustand_zeigen()

    def _sichtbar(self, sichtbar: bool) -> None:
        if self.overlay is None:
            return
        self.meldung_schalter.zeigen("")

        def fertig(ok, fehler):
            if not ok:
                self.meldung_schalter.zeigen(fehler, False)

        self.uno.sichtbar_setzen(self.overlay, sichtbar, fertig)
        self._zustand_zeigen()

    def _timer(self, befehl: str) -> None:
        if self.overlay is None:
            return
        self.meldung_schalter.zeigen("")
        self.uno.timer_befehl(self.overlay, befehl,
                              lambda ok, fehler: None if ok else self.meldung_schalter.zeigen(fehler, False))

    def _dauer(self, schritt: int) -> None:
        o = self.overlay
        if o is None or o.dauer is None:
            return
        self.uno.dauer_setzen(o, o.dauer + schritt,
                              lambda ok, fehler: None if ok else self.meldung_schalter.zeigen(fehler, False))
        self._countdown_zeigen()

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
            self._zustand_zeigen()

        self.uno.felder_laden(overlay, fertig)

    def _felder_aufbauen(self, felder, leer_text: str) -> None:
        _leeren(self._felder_lay)
        self.eingaben, self._felder, self._stand = {}, {}, {}
        for feld in felder:
            schluessel = (feld.teil, feld.kennung)
            self._felder_lay.addWidget(beschriftung(feld.titel, "feldname"))
            eingabe = QLineEdit(feld.wert)
            eingabe.setAccessibleName(feld.titel)
            eingabe.setCursorPosition(0)
            self._felder_lay.addWidget(eingabe)
            eingabe.show()
            self.eingaben[schluessel] = eingabe
            self._felder[schluessel] = feld
            self._stand[schluessel] = feld.wert
        if not felder and leer_text:
            hinweis = beschriftung(leer_text, "hinweis_gross")
            hinweis.setWordWrap(True)
            self._felder_lay.addWidget(hinweis)
        self._felder_lay.addStretch(1)
        self.knopf_uebernehmen.setEnabled(bool(felder))

    def eingabe(self, kennung: str) -> QLineEdit:
        """Eingabefeld zu einem Feldnamen (z. B. für Tests)."""
        return next(e for (_t, k), e in self.eingaben.items() if k == kennung)

    def texte_uebernehmen(self) -> None:
        overlay = self.overlay
        if overlay is None:
            return
        t = self.E.texte
        geaendert = {s: e.text() for s, e in self.eingaben.items() if e.text() != self._stand.get(s)}
        if not geaendert:
            self.meldung_texte.zeigen(t.meldung_texte_nichts)
            return
        self.knopf_uebernehmen.setEnabled(False)
        self.meldung_texte.zeigen("…")
        offen = {"anzahl": len(geaendert), "fehler": ""}

        def fertig_feld(schluessel, text, ok, fehler):
            offen["anzahl"] -= 1
            if ok:
                self._stand[schluessel] = text
            else:
                offen["fehler"] = fehler
            if offen["anzahl"] == 0 and overlay is self.overlay:
                self.knopf_uebernehmen.setEnabled(True)
                if offen["fehler"]:
                    self.meldung_texte.zeigen(offen["fehler"], False)
                else:
                    self.meldung_texte.zeigen(t.meldung_texte_ok, True)

        for schluessel, text in geaendert.items():
            self.uno.feld_setzen(overlay, self._felder[schluessel], text,
                                 lambda ok, fehler, s=schluessel, x=text: fertig_feld(s, x, ok, fehler))


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
            name.setWordWrap(True)
            reihe.addWidget(name, 1)
            k = knopf(t.knopf_uno_wirklich if projekt is self._wirklich else t.knopf_uno_entfernen,
                      "ausblenden" if projekt is self._wirklich else "")
            _fest(k, 240)
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
