"""Das Aussehen (Qt-Stylesheet) – alle Werte kommen aus einstellungen.toml."""

from __future__ import annotations


def stylesheet(E) -> str:
    f, g = E.farben, E.groessen
    return f"""
    QWidget {{
        background-color: transparent;
        color: {f.text};
        font-size: {g.schrift}px;
    }}
    QMainWindow, QWidget#zentrale {{ background-color: {f.hintergrund}; }}

    /* Flächen (Bereiche des Regiepults) */
    QFrame#flaeche {{
        background-color: {f.flaeche};
        border: 2px solid {f.rahmen};
        border-radius: {g.knopf_rundung}px;
    }}
    QFrame#kopfleiste {{
        background-color: {f.flaeche};
        border-bottom: 2px solid {f.rahmen};
    }}

    QLabel#ueberschrift {{
        font-size: {g.schrift_titel}px; font-weight: 700; color: {f.text};
    }}
    QLabel#programmname {{ font-size: {g.schrift_titel}px; font-weight: 800; }}
    QLabel#untertitel {{ font-size: {g.schrift_klein}px; color: {f.text_gedimmt}; }}
    QLabel#gedimmt {{ color: {f.text_gedimmt}; font-size: {g.schrift_klein}px; }}
    QLabel#meldung {{ color: {f.text}; font-size: {g.schrift}px; }}
    QLabel#build {{ color: {f.build_text}; font-size: {g.schrift_klein}px; }}
    QLabel#gut {{ color: {f.meldung_gut}; font-size: {g.schrift}px; }}
    QLabel#fehler {{ color: {f.meldung_fehler}; font-size: {g.schrift}px; }}
    QLabel#feldname {{ color: {f.text_gedimmt}; font-size: {g.schrift_klein}px; }}
    QLabel#tally_text {{ font-size: {g.schrift_titel}px; font-weight: 900; letter-spacing: 2px; }}
    QLabel#hinweis_gross {{ color: {f.text_gedimmt}; font-size: {g.schrift}px; }}

    /* Eingabefelder: groß und gut lesbar */
    QLineEdit {{
        background-color: {f.eingabe_hintergrund};
        color: {f.text};
        border: 2px solid {f.rahmen};
        border-radius: {g.knopf_rundung}px;
        min-height: {g.eingabe_hoehe}px;
        padding: 0px 12px;
        font-size: {g.schrift_eingabe}px;
        selection-background-color: {f.auswahl};
    }}
    QLineEdit:hover {{ border-color: {f.knopf_hover_rahmen}; }}
    QLineEdit:focus {{ border-color: {f.knopf_fokus_rahmen}; }}

    QScrollArea {{ border: none; }}
    QScrollBar:vertical {{
        background: {f.flaeche}; width: 28px; margin: 0px;
    }}
    QScrollBar::handle:vertical {{
        background: {f.knopf_hover}; min-height: 60px; border-radius: 10px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}

    /* Knöpfe: groß, deutlicher Rahmen, wenn der Zeiger darüber ist */
    QPushButton {{
        background-color: {f.knopf};
        color: {f.knopf_text};
        border: {g.rahmen_dick}px solid {f.rahmen};
        border-radius: {g.knopf_rundung}px;
        min-height: {g.knopf_hoehe}px;
        min-width: {g.knopf_breite_min}px;
        padding: 0px 8px;
        font-size: {g.schrift}px;
        font-weight: 700;
    }}
    /* Tastatur-Auswahl (Tab): eigener, blauer Rahmen */
    QPushButton:focus {{ border-color: {f.knopf_fokus_rahmen}; }}
    /* Zeiger über dem Knopf: hell + gelber Rahmen */
    QPushButton:hover {{
        background-color: {f.knopf_hover};
        border-color: {f.knopf_hover_rahmen};
    }}
    QPushButton:pressed {{ background-color: {f.knopf_gedrueckt}; }}
    QPushButton:disabled {{
        background-color: {f.knopf_aus};
        color: {f.knopf_aus_text};
        border-color: {f.knopf_aus};
    }}
    QPushButton#einblenden {{ background-color: {f.einblenden}; }}
    QPushButton#ausblenden {{ background-color: {f.ausblenden}; }}
    QPushButton#twitch {{ background-color: {f.twitch}; }}
    QPushButton#einblenden:focus, QPushButton#ausblenden:focus, QPushButton#twitch:focus {{
        border-color: {f.knopf_fokus_rahmen};
    }}
    QPushButton#einblenden:hover, QPushButton#ausblenden:hover, QPushButton#twitch:hover {{
        border-color: {f.knopf_hover_rahmen};
    }}
    QPushButton#einblenden:disabled, QPushButton#ausblenden:disabled, QPushButton#twitch:disabled {{
        background-color: {f.knopf_aus}; color: {f.knopf_aus_text}; border-color: {f.knopf_aus};
    }}

    /* Overlay-Liste */
    QPushButton#overlay {{
        text-align: left; padding-left: 16px;
        min-height: {g.overlay_zeilenhoehe}px;
    }}
    QPushButton#overlay:checked {{
        background-color: {f.auswahl};
        border-color: {f.auswahl};
    }}
    QPushButton#overlay:checked:focus {{ border-color: {f.knopf_fokus_rahmen}; }}
    QPushButton#overlay:checked:hover {{ border-color: {f.knopf_hover_rahmen}; }}
    """
