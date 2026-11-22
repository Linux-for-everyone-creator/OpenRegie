# OpenRegie – Roadmap

*Profi-Regie für alle. Einfach live.* Eigene Sendezentrale für CachyOS. OBS läuft unsichtbar als Motor
im Hintergrund und wird über den OBS-WebSocket gesteuert. Alle Grafiken im Stream kommen von Overlays.uno.

Grundregeln für alle Builds: große Knöpfe, einfacher Klick, kein Ziehen, kein Rechtsklick,
keine Tastenkombination als einziger Weg, wenig Tippen, alle Texte auf Deutsch.
**Ein Regiepult friert nie ein:** nichts, was warten kann, läuft im Haupt-Thread der Oberfläche.
OpenRegie wird Open Source: keine Geheimnisse im Code, Zugangsdaten nur im Passwortspeicher des Systems.

## Version 1

### Build 1.0 – Motortest (intern) · *fertig (10.11.2026)*
- [x] Eigenes Programmfenster im Regiepult-Look
- [x] Verbindung zu OBS über WebSocket mit gut sichtbarer Statusanzeige
- [x] Live-Vorschau des Sendebilds (Einzelbilder über den WebSocket statt virtueller Kamera)
- [x] Rotes „On Air“-Licht, wenn OBS live streamt
- [x] Countdown als eigene lokale Seite *(in Build 1.1 wieder entfernt – Countdown kommt jetzt von Uno)*
- [x] Build-Anzeige unten links (liest die Nummer automatisch aus der Datei `VERSION`)
- [x] Startmenü-Eintrag

### Build 1.1 – erste Version zum Streamen · *fertig (14.11.2026), Test-Streams stehen aus*
- [x] Umbenennung in **OpenRegie** mit Untertitel „Profi-Regie für alle. Einfach live.“
- [x] Ladebildschirm beim Start
- [x] Build-Anzeige als dezentes Wasserzeichen unten links („Vorabversion · Build 1.1“)
- [x] OBS startet unsichtbar mit (nur Symbol in der Taskleiste), verbindet sich von selbst,
      lädt die richtige Szenensammlung und wird beim Schließen mit beendet (Nachfrage, wenn live)
- [x] Klare Meldungen, wenn OBS nicht startet, abstürzt oder sich nicht meldet
- [x] Overlays.uno-Anbindung: Uno-Projekt per Zwischenablage einfügen (sicher gespeichert)
  - [x] Einfache Liste aller Uno-Overlays mit Tally-Licht
  - [x] Ein- und Ausblenden per Klick
  - [x] Texte direkt ändern (z. B. Bauchbinde, News-Ticker)
  - [x] Neue Uno-Overlays erscheinen mit „Liste neu laden“
- [x] Eigener Countdown entfernt – Uhr und Countdown sind normale Uno-Overlays
- [x] „Mit Twitch anmelden“ (offizielle Anmeldung ohne geheimen Schlüssel) und Streamtitel ändern
- [x] Rotes On-Air-Licht (aus Build 1.0)
- [ ] Ein bis zwei Test-Streams durch Kevin
- [x] Einzel-Unos (z. B. „Countdown | Circles“) einfügen – Korrektur nach erstem Test
- [ ] Prüfung mit einem echten Uno-Projekt mit mehreren Overlays (bisher nur Einzel-Uno echt geprüft)
- [x] Einzel-Uno: Steuerung mit echter Adresse geklärt und eingebaut (Ein/Aus, Tally, Countdown, Dauer, Texte)
- [x] Neues Aussehen nach dem Entwurf „Hauptfenster“ (Bibliothek mit Kacheln, Lampen, Live-Bild, Ausgewählt)
- [x] Neustart mit eingefügtem Einzel-Uno repariert, Meldungen sauber getrennt
- [x] Grundregel „Ein Regiepult friert nie ein“: Zeitlimit für Uno, Passwortspeicher im Hintergrund
- [x] Uno-Quellen automatisch in jeder OBS-Szene und immer ganz oben; alte Countdown-Quelle entfernt
- [x] Ausblenden über den Uno-Schalter „ShowOverlay“: Countdown verschwindet sanft in der Mitte
- [x] Countdown-Zeit direkt eintippen: Klick auf die große Zeit, z. B. „5:00“ tippen, Enter übernimmt,
      Esc bricht ab. Gesperrt, solange der Countdown im Stream ist (kurzer Hinweis, der von selbst
      verschwindet). Falsche Eingaben bekommen einen verständlichen Hinweis. Die Knöpfe „±1/±10 Min“
      bleiben und rechnen mit derselben Zeit weiter. *(16.11.2026)*
- [x] Countdown-Zeit eintippen mit dem echten Uno geprüft (13 von 13, 16.11.2026)
- [x] Countdown-Zeit ohne Enter/Esc: große Knöpfe ✓ „Übernehmen“ und ✕ „Abbrechen“ neben dem Feld.
      Ein Klick darauf bricht nicht ab, falsche Eingaben werden wie bei Enter abgefangen, Enter und Esc
      gehen weiter. Mit dem echten Uno geprüft (20 von 20). *(16.11.2026)*
- [ ] Twitch-App anlegen und Client-ID eintragen

### Build 1.2 – Shots & Wenn-dann · *fertig (22.11.2026)*
Vorbild für die Shots: Telestream Wirecast. Ab diesem Build streamt Kevin regulär.

**Teil A – Shots und Quellen**
- [x] Alle Szenen aus OBS als große Kacheln mit kleinem Vorschaubild unten unter dem Live-Bild (wie Wirecast)
- [x] Ein Klick auf einen Shot schaltet ihn sofort live (roter Rahmen = live)
- [x] „✎“ (Bearbeiten): Klick öffnet den Shot rechts zum Bearbeiten, ohne ihn live zu schalten
- [x] Quellen eines Shots als Kacheln mit Vorschaubild; Shots und Quellen umbenennen
- [x] „+ Shot hinzufügen“: Zweck wählen (Kamera, Spiel, Reactions, Bildschirm, Bild), passendes Layout
      kommt gleich mit (z. B. Reactions: Video groß, Kamera klein rechts unten) – Zweck und Layout sind Pflicht
- [x] „+ Quelle hinzufügen“ in einen Shot (Kamera, Spiel, Bildschirm, Bild) – OBS muss nie geöffnet werden
- [x] Es gibt nur eine Kamera-Quelle für alle Shots (eine Kamera lässt sich nur einmal öffnen)
- [x] Löschen gibt alles in OBS frei: Quellen, die in keinem Shot mehr vorkommen, werden ganz entfernt
- [x] Vorschaubilder nur, solange die Shot-Leiste (bzw. das Bearbeiten) zu sehen ist, alle 5 Sekunden,
      immer nur ein Bild gleichzeitig; zugeklappt (▾) oder Fenster minimiert: keine einzige Anfrage
- [x] Die Oberfläche spricht nur über die Motor-Schicht mit OBS (ein Test wacht darüber)

**Teil B – Wenn-dann-Fenster**
- [x] Knopf „⚡ Wenn-dann“ oben öffnet ein kleines Fenster: links „Wenn …“, rechts „… dann“
- [x] Große Auswahllisten mit Gruppen (Stream, Szenen, Overlays, Ton, Zeitplan), ganz ohne Tippen
- [x] Regeln anlegen, bearbeiten, an-/ausschalten, löschen; gespeichert in ~/.local/share/openregie/
- [x] Register für Auslöser und Aktionen – neue (Build 1.3) lassen sich einfach eintragen
- [x] Auslöser: Stream startet, Stream endet, Shot geht live, Startzeit laut Zeitplan
- [x] Aktionen: Shot live schalten, Overlay ein-/ausblenden, Ton stumm/an
- [x] Automatik läuft nur mit mindestens einer aktiven Regel – sonst keine Pegelmessung, kein Takt, keine Abfrage
- [x] Schutz vor Endlosschleifen (eine Regel löst höchstens alle 2 Sekunden aus)
- [x] Zeitplan: Tage und Uhrzeiten mit großen Knöpfen eintragen; „Nächster Stream: Fr 19:00“ oben im Regiepult
- [ ] Test mit echtem OBS (`werkzeuge/test_build_1_2_mit_echtem_obs.py`) – wartet auf das OBS-Update

### Build 1.3
- [ ] Lautstärke-Auslöser: Spricht Kevin (Pegel über Schwelle), schaltet OpenRegie auf die Kamera um;
      Schwellwert einstellbar. Pegelmessung nur, solange so eine Regel aktiv ist.
- [ ] Spiel-Erkennung: Bei aktivem Spiel-Shot die Kamera klein einblenden statt umzuschalten
- [ ] Performance-Test mit aktiver Lautstärke-Regel (Rechenlast vorher und nachher)
- [ ] Kamera auswählen, wenn mehrere angeschlossen sind (jetzt: die erste)
- [ ] Overlays direkt bearbeiten: über den Knopf „Bearbeiten“ (einfacher Klick) und zusätzlich per
      Doppelklick in der Vorschau *(war für 1.2 geplant, verschoben)*

### Build 1.7
- [ ] Ordner für Overlays (Bibliothek) und Suche
- [ ] Twitch-Kategorie ändern

## Später
- [ ] Studio-Modus: Vorschau-Bild neben dem Live-Bild mit Knopf „Los“ (wie Wirecast)
- [ ] Stream Dock

## Technik in Kürze
- `openregie/obs/` – die Motor-Schicht: Verbindung, Vorschau, OBS unsichtbar starten/beenden,
  Shots und Quellen (`quellen.py`), Zwecke und Layouts (`vorlagen.py`)
- `openregie/automatik/` – Wenn-dann-Regeln, Register der Auslöser/Aktionen, Zeitplan
- `openregie/uno/` – Overlays.uno: Befehle an die API-Adresse eines Uno-Projekts
- `openregie/twitch/` – Twitch-Anmeldung (Device Code Flow, nur öffentliche Client-ID) und Titel
- `openregie/geheimspeicher.py` – Zugangsdaten im Passwortspeicher des Systems (`secret-tool`)
- `openregie/oberflaeche/` – das Regiepult
