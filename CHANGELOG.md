# Änderungsprotokoll

Hier steht, was sich in jedem Build geändert hat. Neueste Einträge oben.

## Build 1.1 – Korrektur: Einzel-Unos · 14.11.2026

**Behoben**
- Ein einzelnes Uno-Overlay (z. B. „Countdown | Circles“) ließ sich nicht einfügen: Es kam immer
  „Uno kennt diese Adresse nicht“, obwohl die Adresse stimmte.
  Ursache: OpenRegie prüfte die Adresse mit dem Befehl „GetOverlays“ und wertete *jede* Ablehnung als
  „Adresse unbekannt“. Einzel-Unos kennen „GetOverlays“ nicht und antworten mit
  HTTP 400 „Invalid command: GetOverlays“ – die Adresse ist dabei gültig.
- Jetzt gilt:
  - „Invalid command“ = Adresse gültig. Das Uno wird als **Einzel-Uno** erkannt und erscheint als ein
    Overlay („Uno-Overlay 1“) in der Liste. Befehle an Einzel-Unos gehen ohne Overlay-Kennung.
  - Nur ein echtes „nicht gefunden“ (HTTP 404) bzw. ein ungültiger Schlüssel (401/403) zeigt
    „Uno kennt diese Adresse nicht“.
  - Kein Internet oder eine Störung bei Uno werden als solche gemeldet, nicht mehr als „Adresse unbekannt“.
  - Einzel-Unos werden nicht alle 5 Sekunden abgefragt (schont das Anfrage-Limit von Uno).
  - Schon gespeicherte Einzel-Unos werden beim nächsten Start von selbst erkannt.

**Neu**
- `werkzeuge/uno_pruefen.py`: fragt ein echtes Uno, welche Befehle es versteht (nur Lese-Befehle,
  Ein-/Ausblenden nur mit `--zeigen`). Die Adresse steht nur in `daten/geheim.toml` (nicht in Git).

**Geprüft**
- 118 automatische Tests (12 neu), zweimal hintereinander ohne Fehler. Das nachgeahmte Uno kennt jetzt
  auch Einzel-Unos, die „GetOverlays“ genau wie das echte mit 400 „Invalid command“ ablehnen.
- Gegenprobe: Die neuen Tests schlagen mit dem alten Code fehl.
- Noch offen: Befehle eines echten Einzel-Unos (Tally-Zustand, Countdown Play/Reset/Dauer).

## Build 1.1 – erste Version zum Streamen · 14.11.2026

**Neu**
- Neuer Name: **OpenRegie** – „Profi-Regie für alle. Einfach live.“ (Programm, Fenster, Startmenü, Protokoll).
- Ladebildschirm beim Start: zeigt, was gerade passiert („OBS wird im Hintergrund gestartet …“).
- Build-Anzeige als dezentes Wasserzeichen unten links: „OpenRegie · Vorabversion · Build 1.1“.
- **OBS unsichtbar im Hintergrund:**
  - OpenRegie startet OBS selbst, nur als Symbol in der Taskleiste, ohne OBS-Fenster.
  - Verbindet sich von selbst und lädt die Szenensammlung aus `einstellungen.toml` (`[obs] szenensammlung`).
  - Läuft OBS schon, wird kein zweites gestartet (und es wird später auch nicht beendet).
  - Beim Schließen von OpenRegie wird das mitgestartete OBS sauber beendet.
    Ist man gerade live, fragt OpenRegie vorher nach und beendet erst den Stream.
  - Klare Meldungen: OBS startet nicht, OBS ist abgestürzt, OBS meldet sich nicht, Szenensammlung fehlt –
    jeweils mit den Knöpfen „OBS starten“ und „Neu verbinden“.
- **Overlays.uno:**
  - Uno-Projekt mit einem Klick auf „Aus Zwischenablage einfügen“ hinzufügen (API-Adresse aus Uno).
  - Die Adresse wird nur im Passwortspeicher des Systems gespeichert, nie als lesbarer Text.
  - Einfache Liste aller Overlays mit Tally-Licht (rot = im Stream) und Knopf „Ein“/„Aus“.
  - Bedienfeld pro Overlay: großer Knopf „Einblenden“/„Ausblenden“ und alle Texte zum Ändern.
  - Das Tally-Licht folgt auch, wenn in Uno selbst ein- oder ausgeblendet wird.
  - Neue Overlays aus Uno erscheinen mit „Liste neu laden“. Mehrere Uno-Projekte sind möglich.
  - Projekt entfernen mit zwei Klicks („Entfernen“ → „Wirklich entfernen?“).
- **Twitch:**
  - „Mit Twitch anmelden“: OpenRegie zeigt einen Code und öffnet die Twitch-Seite, dort „Autorisieren“ klicken.
    Kein geheimer Schlüssel im Code (Device Code Flow, nur öffentliche Client-ID).
  - Streamtitel direkt in OpenRegie ändern (höchstens 140 Zeichen).
  - Die Anmeldung wird von selbst verlängert. Twitch erlaubt das bei Open-Source-Apps höchstens 30 Tage,
    danach meldet OpenRegie „Bitte neu anmelden“.

**Entfernt**
- Der eigene Countdown aus Build 1.0 (lokale Seite und Knopf „Countdown in OBS einrichten“).
  Alle Grafiken, auch Uhr und Countdown, kommen jetzt von Overlays.uno.

**Geprüft**
- 106 automatische Tests mit nachgeahmtem OBS, nachgeahmtem Overlays.uno und nachgeahmtem Twitch.
- 19 Prüfungen mit echtem OBS 33.0.1 in einem getrennten Test-OBS (`werkzeuge/test_mit_echtem_obs.py`):
  unsichtbarer Start (kein OBS-Fenster laut KDE), Szenensammlung beim Start und per Fernsteuerung,
  Vorschau, On Air, Absturz und Neustart, sauberes Beenden.
- Echter Start mit dem eigenen OBS: OBS unsichtbar, nach etwa 3 Sekunden verbunden, beim Schließen beendet.
- Noch offen: Prüfung mit dem echten Overlays.uno-Konto und der echten Twitch-Anmeldung.

## Build 1.0 – Motortest (intern) · 10.11.2026

**Neu**
- Eigenes Programmfenster im Regiepult-Look (dunkel, große Knöpfe, nur einfacher Klick).
- Verbindung zu OBS über den OBS-WebSocket:
  - Port und Passwort werden automatisch aus den OBS-Einstellungen gelesen, man muss nichts eintippen.
  - Große Statuslampe: grün „OBS verbunden“, gelb „Verbinde …“, rot „Keine Verbindung“.
  - Bricht die Verbindung ab, verbindet sich Rolliregie von selbst neu.
  - Verständliche Hinweise, z. B. „OBS ist nicht geöffnet“ oder „Fernsteuerung ist aus“, dazu die Knöpfe „OBS starten“ und „Neu verbinden“.
- Live-Vorschau des Sendebilds: etwa 10 Einzelbilder pro Sekunde über den WebSocket, ohne virtuelle Kamera.
- Rotes „ON AIR“-Licht, solange OBS streamt (orange beim Starten und Stoppen).
- Countdown: Dauer mit −1 Min, +1 Min, −10 Sek und +10 Sek einstellen, dazu Start/Weiter, Pause und Stopp.
  - Erscheint in OBS über eine lokale Seite (`http://127.0.0.1:8787/countdown`).
  - Knopf „Countdown in OBS einrichten“ legt die Browserquelle mit einem Klick in der gesendeten Szene an.
  - Position, Schrift, Farben und Endtext („Gleich geht's los!“) stehen in `einstellungen.toml`.
- Liste der Rolliregie-Titel (zunächst nur der Countdown).
- Build-Anzeige unten links („Rolliregie Build 1.0“). Die Nummer steht nur in der Datei `VERSION`.
- Startmenü-Eintrag mit eigenem Symbol (`werkzeuge/startmenue_einrichten.sh`).
- Es kann nur ein Rolliregie-Fenster gleichzeitig offen sein.
- Protokolldatei für die Fehlersuche: `~/.local/state/rolliregie/rolliregie.log`.

**Geprüft**
- 93 automatische Tests mit einem nachgeahmten OBS, mehrfach hintereinander ohne Fehler.
- 12 Prüfungen mit echtem OBS 33.0.1 (WebSocket 5.7.6) in einem getrennten Test-OBS
  (`werkzeuge/test_mit_echtem_obs.py`): Vorschau mit 10 Bildern pro Sekunde bei etwa 5 % Last für OBS.
