# Änderungsprotokoll

Hier steht, was sich in jedem Build geändert hat. Neueste Einträge oben.

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
