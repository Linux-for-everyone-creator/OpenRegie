# Rolliregie – Roadmap

*Barrierefrei streamen.* Eigene Sendezentrale für CachyOS. OBS läuft als Motor im Hintergrund
und wird über den OBS-WebSocket gesteuert.

Grundregeln für alle Builds: große Knöpfe, einfacher Klick, kein Ziehen, kein Rechtsklick,
keine Tastenkombination als einziger Weg, wenig Tippen, alle Texte auf Deutsch.

## Version 1

### Build 1.0 – Motortest (intern) · *fertig (10.11.2026)*
- [x] Eigenes Programmfenster im Regiepult-Look
- [x] Verbindung zu OBS über WebSocket mit gut sichtbarer Statusanzeige
- [x] Live-Vorschau des Sendebilds (Einzelbilder über den WebSocket statt virtueller Kamera)
- [x] Rotes „On Air“-Licht, wenn OBS live streamt
- [x] Countdown: Dauer mit Plus/Minus, Start, Pause, Stopp – als lokale Seite, die OBS als Browserquelle einbindet
- [x] Einfache Liste aller Rolliregie-Titel
- [x] Build-Anzeige unten links (liest die Nummer automatisch aus der Datei `VERSION`)
- [x] Startmenü-Eintrag

### Build 1.1 – erste Version zum Streamen
- [ ] Overlays.uno-Anbindung (API): Texte ändern, ein- und ausblenden – Aussehen kommt von Uno
  - [ ] News-Ticker
  - [ ] Bauchbinde
- [ ] Eingeblendete Uhr
- [ ] Tally-Licht pro Titel (zeigt, welcher Titel gerade auf Sendung ist)

### Build 1.2
- [ ] OBS-Quellen als Vorschaubilder anzeigen und umbenennen
- [ ] Titel direkt bearbeiten: über den Knopf „Bearbeiten“ (einfacher Klick) und zusätzlich per Doppelklick in der Vorschau
- [ ] Bibliothek mit Ordnern

## Später
- [ ] Quellen hinzufügen
- [ ] Studio-Modus
- [ ] Stream Dock

## Technische Vorplanung
- Jeder Titel ist ein eigener Baustein (`rolliregie/titel/`) mit einem „Antrieb“:
  `lokal` (Rolliregie zeichnet ihn selbst, z. B. Countdown, Uhr) oder `uno` (Overlays.uno, ab Build 1.1).
- Die lokale Webseite (`rolliregie/web/`) kann weitere Seiten bekommen (z. B. Uhr).
- Zugangsdaten für Overlays.uno kommen später in `daten/geheim.toml` – diese Datei wird nicht in Git gespeichert.
