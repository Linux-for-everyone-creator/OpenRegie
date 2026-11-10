# Rolliregie – Barrierefrei streamen

Eigene Sendezentrale für Livestreams unter CachyOS. OBS läuft als Motor im Hintergrund,
Rolliregie steuert es über den OBS-WebSocket.

## Starten
Im Startmenü auf **Rolliregie** klicken.
(Den Eintrag bei Bedarf neu anlegen: `sh werkzeuge/startmenue_einrichten.sh`)

## Einmalig in OBS einstellen
**Werkzeuge → WebSocket-Servereinstellungen → „WebSocket-Server aktivieren“** einschalten → **OK**.
Port und Passwort liest Rolliregie selbst.

## Countdown in den Stream bringen
In Rolliregie auf **„Countdown in OBS einrichten“** klicken. Der Countdown kommt in die Szene,
die gerade gesendet wird. Für weitere Szenen: erst in OBS die Szene wechseln, dann noch einmal klicken.

## Aussehen ändern
Alle Farben, Texte und Größen stehen in **`einstellungen.toml`**. Nach dem Ändern Rolliregie neu starten.
Für die Countdown-Seite in OBS reicht ein erneuter Klick auf „Countdown in OBS einrichten“.

## Für Entwickler
- Tests: `python3 -m unittest discover -s tests -t .`
- Test mit echtem OBS (fasst die eigenen OBS-Einstellungen nicht an): `python3 werkzeuge/test_mit_echtem_obs.py`
- Build-Nummer: Datei `VERSION`
- Pläne: `ROADMAP.md` · Änderungen: `CHANGELOG.md`
