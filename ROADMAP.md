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

### Build 1.2
- [ ] Quellen aus OBS als Kacheln (wie im Entwurf unten)
- [ ] OBS-Quellen als Vorschaubilder anzeigen und umbenennen
- [ ] Overlays direkt bearbeiten: über den Knopf „Bearbeiten“ (einfacher Klick) und zusätzlich per Doppelklick in der Vorschau

### Build 1.7
- [ ] Ordner für Overlays (Bibliothek) und Suche
- [ ] Twitch-Kategorie ändern

## Später
- [ ] Quellen hinzufügen
- [ ] Studio-Modus
- [ ] Stream Dock

## Technik in Kürze
- `openregie/obs/` – Verbindung, Vorschau und der „Motor“ (OBS unsichtbar starten/beenden)
- `openregie/uno/` – Overlays.uno: Befehle an die API-Adresse eines Uno-Projekts
- `openregie/twitch/` – Twitch-Anmeldung (Device Code Flow, nur öffentliche Client-ID) und Titel
- `openregie/geheimspeicher.py` – Zugangsdaten im Passwortspeicher des Systems (`secret-tool`)
- `openregie/oberflaeche/` – das Regiepult
