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
    QLabel#countdown_anzeige {{
        font-size: {g.schrift_countdown}px; font-weight: 800;
        background-color: {f.hintergrund};
        border: 2px solid {f.rahmen}; border-radius: {g.knopf_rundung}px;
        padding: 4px 12px;
    }}
    QLabel#countdown_zustand {{ font-size: {g.schrift}px; color: {f.text_gedimmt}; }}

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
    QPushButton#start {{ background-color: {f.start}; }}
    QPushButton#pause {{ background-color: {f.pause}; }}
    QPushButton#stopp {{ background-color: {f.stopp}; }}
    QPushButton#start:focus, QPushButton#pause:focus, QPushButton#stopp:focus {{
        border-color: {f.knopf_fokus_rahmen};
    }}
    QPushButton#start:hover, QPushButton#pause:hover, QPushButton#stopp:hover {{
        border-color: {f.knopf_hover_rahmen};
    }}
    QPushButton#start:disabled, QPushButton#pause:disabled, QPushButton#stopp:disabled {{
        background-color: {f.knopf_aus}; color: {f.knopf_aus_text}; border-color: {f.knopf_aus};
    }}

    /* Titelliste */
    QPushButton#titel {{
        text-align: left; padding-left: 20px;
        min-height: {g.titelliste_zeilenhoehe}px;
    }}
    QPushButton#titel:checked {{
        background-color: {f.auswahl};
        border-color: {f.auswahl};
    }}
    QPushButton#titel:checked:focus {{ border-color: {f.knopf_fokus_rahmen}; }}
    QPushButton#titel:checked:hover {{ border-color: {f.knopf_hover_rahmen}; }}
    """
