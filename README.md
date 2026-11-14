# OpenRegie – Profi-Regie für alle. Einfach live.

Eigene Sendezentrale für Livestreams unter CachyOS. OBS läuft unsichtbar als Motor im Hintergrund,
OpenRegie steuert es über den OBS-WebSocket. Alle Grafiken kommen von Overlays.uno.

## Starten
Im Startmenü auf **OpenRegie** klicken. OBS startet automatisch unsichtbar mit.
(Den Eintrag bei Bedarf neu anlegen: `sh werkzeuge/startmenue_einrichten.sh`)

## Einmalig in OBS einstellen
**Werkzeuge → WebSocket-Servereinstellungen → „WebSocket-Server aktivieren“** einschalten → **OK**.
Port und Passwort liest OpenRegie selbst. Welche Szenensammlung geladen wird, steht in
`einstellungen.toml` bei `[obs] szenensammlung`.

## Overlays.uno verbinden
1. In Overlays.uno das Projekt öffnen, oben rechts im Menü **„API Description“** wählen, die Adresse kopieren.
2. In OpenRegie links auf **„Uno-Projekte“** und dann auf **„Aus Zwischenablage einfügen“** klicken.

Die Adresse wird im Passwortspeicher des Systems gespeichert (KDE-Wallet bzw. Schlüsselbund).
Es gehen beide Arten: Uno-Projekte mit mehreren Overlays und einzelne Unos (z. B. „Countdown | Circles“).
Bei Overlays mit Zeitgeber erscheinen rechts die Countdown-Knöpfe (Start, Pause, Zurück, Dauer).
Die Overlays kommen von selbst in den Stream: OpenRegie legt für jedes Uno-Projekt in jeder OBS-Szene
eine Browserquelle „Uno: <Name>“ an und hält sie immer ganz oben (abschaltbar in `einstellungen.toml`, `[obs]`).

## Twitch einrichten (einmalig)
OpenRegie braucht eine eigene, öffentliche „Client-ID“ von Twitch:
1. Auf https://dev.twitch.tv/console anmelden → **„Deine Anwendung registrieren“**.
2. Name: z. B. `OpenRegie`, OAuth-Weiterleitungs-URL: `http://localhost`, Kategorie: *Broadcaster Suite*,
   Client-Typ: **Öffentlich**.
3. Die **Client-ID** kopieren und in `einstellungen.toml` bei `[twitch] client_id` eintragen.
   (Sie ist kein Geheimnis. Ein Client-Secret wird **nicht** gebraucht.)
4. OpenRegie neu starten → **„Mit Twitch anmelden“**.

## Aussehen ändern
Alle Farben, Texte und Größen stehen in **`einstellungen.toml`**. Nach dem Ändern OpenRegie neu starten.

## Für Entwickler
- Tests: `python3 -m unittest discover -s tests -t .`
- Test mit echtem OBS (fasst die eigenen OBS-Einstellungen nicht an): `python3 werkzeuge/test_mit_echtem_obs.py`
- Test mit echtem Uno (Adresse in `daten/geheim.toml`, blendet kurz ein!): `python3 werkzeuge/test_mit_echtem_uno.py --ja-schalten`
- Nur lesen, welche Befehle ein Uno versteht: `python3 werkzeuge/uno_pruefen.py`
- Build-Nummer: Datei `VERSION`
- Pläne: `ROADMAP.md` · Änderungen: `CHANGELOG.md`
- Protokoll für die Fehlersuche: `~/.local/state/openregie/openregie.log`
