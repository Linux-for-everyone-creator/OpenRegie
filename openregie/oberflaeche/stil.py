"""Das Aussehen (Qt-Stylesheet) – alle Werte kommen aus einstellungen.toml.

Vorbild ist der Entwurf „Hauptfenster“: dunkle Karten mit runden Ecken, gelbes Logo,
runde Status-Schilder, große farbige Knöpfe.
"""

from __future__ import annotations


def stylesheet(E) -> str:
    f, g = E.farben, E.groessen
    return f"""
    QWidget {{
        background-color: transparent;
        color: {f.text};
        font-family: "{g.schriftart}";
        font-size: {g.schrift}px;
    }}
    QMainWindow, QWidget#zentrale {{ background-color: {f.hintergrund}; }}

    /* Karten (Bereiche des Regiepults) */
    QFrame#flaeche {{
        background-color: {f.flaeche};
        border: 2px solid {f.rahmen};
        border-radius: {g.karten_rundung}px;
    }}
    QFrame#kopfleiste {{
        background-color: {f.hintergrund};
        border-bottom: 2px solid {f.rahmen};
    }}
    QFrame#trennlinie {{ background-color: {f.rahmen}; border: none; }}

    QLabel#ueberschrift {{ font-size: {g.schrift_titel}px; font-weight: 700; color: {f.text}; }}
    QLabel#kleinueberschrift {{
        font-size: {g.schrift_klein}px; font-weight: 600; color: {f.text_gedimmt}; letter-spacing: 2px;
    }}
    QLabel#programmname {{ font-size: {g.schrift_titel}px; font-weight: 800; }}
    QLabel#untertitel {{ font-size: {g.schrift_klein}px; color: {f.text_gedimmt}; }}
    QLabel#uhr {{ font-size: {g.schrift_uhr}px; font-weight: 700; color: {f.text}; }}
    QLabel#gedimmt {{ color: {f.text_gedimmt}; font-size: {g.schrift_klein}px; }}
    QLabel#meldung {{ color: {f.text}; font-size: {g.schrift}px; }}
    /* Hinweis beim Drüberfahren (z. B. warum ein Knopf ausgegraut ist): gut lesbar */
    QToolTip {{
        background-color: {f.knopf_hover}; color: {f.knopf_text};
        border: 2px solid {f.knopf_hover_rahmen}; border-radius: 6px;
        padding: 6px 10px; font-size: {g.schrift}px;
    }}
    QLabel#build {{ color: {f.build_text}; font-size: {g.schrift_klein}px; }}
    QLabel#gut {{ color: {f.meldung_gut}; font-size: {g.schrift}px; }}
    QLabel#fehler {{ color: {f.meldung_fehler}; font-size: {g.schrift}px; }}
    QLabel#feldname {{ color: {f.text_gedimmt}; font-size: {g.schrift_klein}px; }}
    QLabel#tally_text {{ font-size: {g.schrift}px; font-weight: 700; }}
    QLabel#hinweis_gross {{ color: {f.text_gedimmt}; font-size: {g.schrift}px; }}
    QLabel#countdown_anzeige {{
        font-size: {g.schrift_countdown}px; font-weight: 800;
        background-color: {f.eingabe_hintergrund};
        border: 2px solid {f.rahmen}; border-radius: {g.knopf_rundung}px;
        padding: 4px 12px;
    }}

    /* Eingabefelder: groß und gut lesbar */
    QLineEdit {{
        background-color: {f.eingabe_hintergrund};
        color: {f.text};
        border: 2px solid {f.rahmen};
        border-radius: {g.knopf_rundung}px;
        min-height: {g.eingabe_hoehe}px;
        padding: 0px 16px;
        font-size: {g.schrift_eingabe}px;
        selection-background-color: {f.auswahl};
    }}
    QLineEdit:hover {{ border-color: {f.knopf_hover_rahmen}; }}
    QLineEdit:focus {{ border-color: {f.knopf_fokus_rahmen}; }}
    /* Countdown-Zeit eintippen: genauso groß wie die Anzeige */
    QLineEdit#countdown_eingabe {{
        font-size: {g.schrift_countdown}px; font-weight: 800;
        padding: 4px 12px;
    }}
    QLabel#countdown_anzeige:hover {{ border-color: {f.knopf_hover_rahmen}; }}
    QLabel#countdown_anzeige:focus {{ border-color: {f.knopf_fokus_rahmen}; }}

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
    QPushButton#klein {{ min-width: 60px; padding: 0px 2px; }}
    QPushButton#quadrat {{ min-width: {g.knopf_hoehe}px; font-size: {g.schrift_titel}px; padding: 0px; }}
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
    QPushButton#einblenden {{ background-color: {f.einblenden}; border-color: {f.einblenden};
                              font-size: {g.schrift_eingabe}px; }}
    QPushButton#ausblenden {{ background-color: {f.ausblenden}; border-color: {f.ausblenden};
                              font-size: {g.schrift_eingabe}px; }}
    QPushButton#twitch {{ background-color: {f.twitch}; border-color: {f.twitch}; }}
    QPushButton#einblenden:focus, QPushButton#ausblenden:focus, QPushButton#twitch:focus {{
        border-color: {f.knopf_fokus_rahmen};
    }}
    QPushButton#einblenden:hover, QPushButton#ausblenden:hover, QPushButton#twitch:hover {{
        border-color: {f.knopf_hover_rahmen};
    }}
    QPushButton#einblenden:disabled, QPushButton#ausblenden:disabled, QPushButton#twitch:disabled {{
        background-color: {f.knopf_aus}; color: {f.knopf_aus_text}; border-color: {f.knopf_aus};
    }}
    /* Countdown-Zeit: Häkchen (übernehmen) und Kreuz (abbrechen) neben dem Eingabefeld */
    QPushButton#zeit_ok, QPushButton#zeit_weg {{
        min-width: 0px; padding: 0px; font-size: {int(g.schrift_titel) + 14}px; font-weight: 800;
    }}
    QPushButton#zeit_ok {{ background-color: {f.einblenden}; border-color: {f.einblenden}; }}
    QPushButton#zeit_weg {{ background-color: {f.ausblenden}; border-color: {f.ausblenden}; }}
    QPushButton#zeit_ok:hover, QPushButton#zeit_weg:hover {{ border-color: {f.knopf_hover_rahmen}; }}
    QPushButton#zeit_ok:pressed, QPushButton#zeit_weg:pressed {{ background-color: {f.knopf_gedrueckt}; }}
    """
