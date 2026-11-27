"""Wiederverwendbare Bausteine: großer Knopf (mit Hinweis, wenn gesperrt), Lampe, Logo, Pillen (OBS-Status,
ON AIR), Vorschaubild."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QEvent, QObject, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QSizePolicy, QToolTip, QWidget

from ..obs.verbindung import Sendung, Status


def knopf(text: str, name: str = "") -> QPushButton:
    """Großer Knopf. Reagiert auf einen einfachen Klick (Loslassen der Taste)."""
    k = QPushButton(text)
    if name:
        k.setObjectName(name)
    k.setCursor(Qt.CursorShape.PointingHandCursor)
    k.setAutoDefault(False)
    # Klick mit Joystick/Maus setzt keinen Tastatur-Rahmen; mit Tab geht es trotzdem.
    k.setFocusPolicy(Qt.FocusPolicy.TabFocus)
    k.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return k


class _GesperrtHinweis(QObject):
    """Ein ausgegrauter Knopf sagt, warum er gerade nicht geht:
    beim Drüberfahren als kleiner Hinweis, beim Anklicken als kurze Meldung (über `melden`).
    Ist der Knopf frei, ändert sich nichts."""

    def __init__(self, k: QPushButton, grund: Callable[[], str], melden: Callable[[str], None]):
        super().__init__(k)
        self.knopf, self.grund, self.melden = k, grund, melden
        k.installEventFilter(self)
        self._zeiger()

    def text(self) -> str:
        return self.grund() or ""

    def _zeiger(self) -> None:
        k = self.knopf
        k.setCursor(Qt.CursorShape.PointingHandCursor if k.isEnabled() else Qt.CursorShape.ForbiddenCursor)

    def eventFilter(self, obj, e) -> bool:
        typ = e.type()
        if typ == QEvent.Type.EnabledChange:
            self._zeiger()
            return False
        if self.knopf.isEnabled():
            return False
        if typ == QEvent.Type.ToolTip:
            text = self.text()
            if text:
                QToolTip.showText(e.globalPos(), text, self.knopf)
            else:
                QToolTip.hideText()
            return True
        if typ in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick):
            return True  # nicht an das Fenster dahinter weiterreichen
        if typ == QEvent.Type.MouseButtonRelease:
            if e.button() == Qt.MouseButton.LeftButton and self.knopf.rect().contains(e.position().toPoint()):
                text = self.text()
                if text:
                    self.melden(text)
            return True
        return False


def gesperrt_hinweis(k: QPushButton, grund: Callable[[], str], melden: Callable[[str], None]) -> QPushButton:
    """Hängt an einen Knopf, was er sagt, wenn er ausgegraut ist. `grund()` liefert den Text passend
    zum gerade aktuellen Zustand, `melden(text)` zeigt ihn nach einem Klick kurz an."""
    k._gesperrt_hinweis = _GesperrtHinweis(k, grund, melden)
    return k


def gesperrt_text(k: QPushButton) -> str:
    """Was ein (gesperrter) Knopf gerade sagen würde – "" ohne Hinweis (z. B. für Tests)."""
    h = getattr(k, "_gesperrt_hinweis", None)
    return h.text() if h else ""


def flaeche(name: str = "flaeche") -> QFrame:
    f = QFrame()
    f.setObjectName(name)
    return f


def beschriftung(text: str, name: str = "") -> QLabel:
    l = QLabel(text)
    if name:
        l.setObjectName(name)
    return l


class Lampe(QWidget):
    """Runder Punkt in einer Farbe (Statuslampe)."""

    def __init__(self, groesse: int, farbe: str, parent=None, glanz: bool = False):
        super().__init__(parent)
        self.setFixedSize(groesse, groesse)
        self._farbe = QColor(farbe)
        self._glanz = glanz

    def farbe_setzen(self, farbe: str) -> None:
        self._farbe = QColor(farbe)
        self.update()

    def farbe(self) -> str:
        return self._farbe.name().upper()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._farbe)
        p.drawEllipse(QRectF(1, 1, self.width() - 2, self.height() - 2))
        if self._glanz:
            p.setBrush(QColor(255, 255, 255, 70))
            d = self.width() / 3
            p.drawEllipse(QRectF(self.width() * 0.22, self.height() * 0.18, d, d * 0.8))


class Logo(QWidget):
    """Gelbes Quadrat mit einem kleinen Bildschirm-Symbol (wie im Entwurf)."""

    def __init__(self, E, parent=None):
        super().__init__(parent)
        g = int(E.groessen.logo)
        self.setFixedSize(g, g)
        self._grund = QColor(E.farben.logo)
        self._symbol = QColor(E.farben.logo_symbol)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._grund)
        p.drawRoundedRect(QRectF(0, 0, w, w), w * 0.22, w * 0.22)
        stift = QPen(self._symbol, max(2.0, w * 0.06))
        stift.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(stift)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(w * 0.26, w * 0.32, w * 0.48, w * 0.36), w * 0.06, w * 0.06)
        p.drawLine(int(w * 0.36), int(w * 0.45), int(w * 0.64), int(w * 0.45))
        p.drawLine(int(w * 0.36), int(w * 0.56), int(w * 0.54), int(w * 0.56))


class Pille(QFrame):
    """Abgerundetes Schild mit Punkt und Text (OBS-Status, ON AIR)."""

    def __init__(self, E, parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QHBoxLayout

        self._E = E
        lay = QHBoxLayout(self)
        lay.setContentsMargins(22, 10, 26, 10)
        lay.setSpacing(12)
        self.punkt = Lampe(16, E.farben.status_getrennt)
        lay.addWidget(self.punkt)
        self.text = QLabel("")
        lay.addWidget(self.text)

    def zeigen(self, text: str, punkt: str, hintergrund: str, rahmen: str, schrift: str, groesse: int,
               fett: int = 600, abstand: int = 0) -> None:
        g = self._E.groessen
        self.text.setText(text)
        self.setAccessibleName(text)
        self.punkt.farbe_setzen(punkt)
        self.setStyleSheet(
            f"Pille {{ background-color: {hintergrund}; border: 2px solid {rahmen};"
            f" border-radius: {g.on_air_hoehe // 2}px; }}"
            f"QLabel {{ color: {schrift}; font-size: {groesse}px; font-weight: {fett};"
            f" letter-spacing: {abstand}px; background: transparent; }}")


class VerbindungsAnzeige(Pille):
    """Pille mit Punkt + Text, z. B. grün „OBS verbunden“."""

    def __init__(self, E, parent=None):
        super().__init__(E, parent)
        self.zeigen_status(Status.GETRENNT)

    def zeigen_status(self, status: Status) -> None:
        f, t, g = self._E.farben, self._E.texte, self._E.groessen
        farbe, text = {
            Status.VERBUNDEN: (f.status_verbunden, t.status_verbunden),
            Status.VERBINDE: (f.status_verbinde, t.status_verbinde),
            Status.GETRENNT: (f.status_getrennt, t.status_getrennt),
        }[status]
        self.zeigen(text, farbe, f.flaeche, f.rahmen, f.text, g.schrift)


class OnAirLicht(Pille):
    """Das rote „● ON AIR“-Schild. Rot leuchtet es nur, wenn OBS wirklich live ist;
    beim Verbinden, Neu-Verbinden und Stoppen ist es orange."""

    def __init__(self, E, parent=None):
        super().__init__(E, parent)
        g, t = E.groessen, E.texte
        self.setFixedHeight(g.on_air_hoehe)
        # Feste Breite für den längsten Text: sonst verrutscht die Kopfleiste beim Umschalten
        schrift = QFont(str(g.schriftart))
        schrift.setPixelSize(int(g.schrift_titel) - 4)
        schrift.setWeight(QFont.Weight.Black)
        schrift.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 3)
        texte = (t.on_air_an, t.on_air_aus, t.on_air_startet, t.on_air_stoppt, t.on_air_wieder)
        laengster = max(QFontMetrics(schrift).horizontalAdvance(x) for x in texte)
        # Ränder (22 + 26), Punkt (16), Abstand (12), Rahmen (2 × 2) und etwas Luft
        self.setFixedWidth(max(int(g.on_air_breite), laengster + 22 + 26 + 16 + 12 + 4 + 2))
        self.zeigen_sendung(Sendung.AUS)

    def zeigen_sendung(self, sendung: Sendung) -> None:
        f, t, g = self._E.farben, self._E.texte, self._E.groessen
        hinter, vorder, text = {
            Sendung.AN: (f.on_air_an, f.on_air_an_text, t.on_air_an),
            Sendung.STARTET: (f.on_air_startet, f.on_air_an_text, t.on_air_startet),
            Sendung.WIEDER: (f.on_air_startet, f.on_air_an_text, t.on_air_wieder),
            Sendung.STOPPT: (f.on_air_startet, f.on_air_an_text, t.on_air_stoppt),
            Sendung.AUS: (f.on_air_aus, f.on_air_aus_text, t.on_air_aus),
        }[sendung]
        self.zeigen(text, vorder, hinter, hinter, vorder, g.schrift_titel - 4, fett=900, abstand=3)
        self.sendung = sendung


class VorschauBild(QWidget):
    """Zeigt das Vorschaubild im Seitenverhältnis 16:9, sonst einen Hinweistext."""

    def __init__(self, E, parent=None):
        super().__init__(parent)
        self._E = E
        self._bild: QPixmap | None = None
        self._text = E.texte.vorschau_keine_verbindung
        self.setMinimumSize(288, 162)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def bild_setzen(self, bild: QImage) -> None:
        self._bild = QPixmap.fromImage(bild)
        self.update()

    def text_setzen(self, text: str) -> None:
        """Bild weg, stattdessen Hinweistext."""
        self._bild = None
        self._text = text
        self.update()

    def hat_bild(self) -> bool:
        return self._bild is not None

    def _rahmen(self) -> QRectF:
        verhaeltnis = 16 / 9
        if self._bild is not None and self._bild.height() > 0:
            verhaeltnis = self._bild.width() / self._bild.height()
        b, h = self.width(), self.height()
        if b / h > verhaeltnis:
            b = h * verhaeltnis
        else:
            h = b / verhaeltnis
        return QRectF((self.width() - b) / 2, (self.height() - h) / 2, b, h)

    def live_setzen(self, live: bool) -> None:
        """Roter Rahmen um das Bild, solange gesendet wird (wie im Entwurf)."""
        self.live = live
        self.update()

    def paintEvent(self, _e):
        f, g = self._E.farben, self._E.groessen
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        dick = 4
        r = self._rahmen().adjusted(dick, dick, -dick, -dick)
        rund = float(g.karten_rundung)
        weg = QPainterPath()
        weg.addRoundedRect(r, rund, rund)
        p.fillPath(weg, QColor(f.flaeche_hell))
        if self._bild is not None:
            p.save()
            p.setClipPath(weg)
            p.drawPixmap(r, self._bild, QRectF(self._bild.rect()))
            p.restore()
        else:
            p.setPen(QColor(f.text_gedimmt))
            schrift = QFont(self.font())
            schrift.setPixelSize(g.schrift)
            p.setFont(schrift)
            p.drawText(r, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self._text)
        live = getattr(self, "live", False)
        p.setPen(QPen(QColor(f.on_air_an if live else f.rahmen), dick if live else 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r, rund, rund)
