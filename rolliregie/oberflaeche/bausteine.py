"""Wiederverwendbare Bausteine: großer Knopf, Statuslampe, On-Air-Licht, Vorschaubild."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QSizePolicy, QWidget

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
    """Runde Lampe in einer Farbe (für den Verbindungsstatus)."""

    def __init__(self, groesse: int, farbe: str, parent=None):
        super().__init__(parent)
        self.setFixedSize(groesse, groesse)
        self._farbe = QColor(farbe)

    def farbe_setzen(self, farbe: str) -> None:
        self._farbe = QColor(farbe)
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QColor(0, 0, 0, 120))
        p.setBrush(self._farbe)
        p.drawEllipse(QRectF(2, 2, self.width() - 4, self.height() - 4))
        # kleiner Glanzpunkt
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 70))
        d = self.width() / 3
        p.drawEllipse(QRectF(self.width() * 0.22, self.height() * 0.18, d, d * 0.8))


class VerbindungsAnzeige(QWidget):
    """Lampe + Text, z. B. grün „OBS verbunden“."""

    def __init__(self, E, parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QHBoxLayout

        self._E = E
        self.lampe = Lampe(E.groessen.lampe, E.farben.status_getrennt)
        self.text = QLabel(E.texte.status_getrennt)
        self.text.setStyleSheet(f"font-size: {E.groessen.schrift_titel - 4}px; font-weight: 700;")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        lay.addWidget(self.lampe)
        lay.addWidget(self.text)
        self.zeigen(Status.GETRENNT)

    def zeigen(self, status: Status) -> None:
        f, t = self._E.farben, self._E.texte
        farbe, text = {
            Status.VERBUNDEN: (f.status_verbunden, t.status_verbunden),
            Status.VERBINDE: (f.status_verbinde, t.status_verbinde),
            Status.GETRENNT: (f.status_getrennt, t.status_getrennt),
        }[status]
        self.lampe.farbe_setzen(farbe)
        self.text.setText(text)
        self.setAccessibleName(text)


class OnAirLicht(QLabel):
    """Das rote „ON AIR“-Schild."""

    def __init__(self, E, parent=None):
        super().__init__(parent)
        self._E = E
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedSize(E.groessen.on_air_breite, E.groessen.on_air_hoehe)
        self.zeigen(Sendung.AUS)

    def zeigen(self, sendung: Sendung) -> None:
        f, t, g = self._E.farben, self._E.texte, self._E.groessen
        hinter, vorder, text, leuchten = {
            Sendung.AN: (f.on_air_an, f.on_air_an_text, t.on_air_an, True),
            Sendung.STARTET: (f.on_air_startet, f.on_air_an_text, t.on_air_startet, False),
            Sendung.STOPPT: (f.on_air_startet, f.on_air_an_text, t.on_air_stoppt, False),
            Sendung.AUS: (f.on_air_aus, f.on_air_aus_text, t.on_air_aus, False),
        }[sendung]
        rahmen = f.on_air_an_text if leuchten else hinter
        self.setText(text)
        self.setAccessibleName(text)
        self.setStyleSheet(
            f"background-color: {hinter}; color: {vorder}; border: 3px solid {rahmen};"
            f"border-radius: {g.knopf_rundung}px; font-size: {g.schrift_titel}px; font-weight: 900;"
            "letter-spacing: 3px;"
        )
        self.sendung = sendung


class VorschauBild(QWidget):
    """Zeigt das Vorschaubild im Seitenverhältnis 16:9, sonst einen Hinweistext."""

    def __init__(self, E, parent=None):
        super().__init__(parent)
        self._E = E
        self._bild: QPixmap | None = None
        self._text = E.texte.vorschau_keine_verbindung
        self.setMinimumSize(320, 180)
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

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r = self._rahmen()
        p.fillRect(r, QColor("#000000"))
        if self._bild is not None:
            p.drawPixmap(r, self._bild, QRectF(self._bild.rect()))
        else:
            p.setPen(QColor(self._E.farben.text_gedimmt))
            schrift = QFont(self.font())
            schrift.setPixelSize(self._E.groessen.schrift)
            p.setFont(schrift)
            p.drawText(r, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self._text)
        p.setPen(QColor(self._E.farben.rahmen))
        p.drawRect(r.adjusted(0, 0, -1, -1))
