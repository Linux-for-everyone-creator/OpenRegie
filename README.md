# OpenRegie – Profi-Regie für alle. Einfach live.

> [!WARNING]
> **Pre-Alpha (Build 1.2.1).** OpenRegie ist in früher Entwicklung. Funktionen ändern sich,
> Fehler sind wahrscheinlich. Bitte noch **nicht** für wichtige Livestreams verwenden.
>
> **Pre-alpha (build 1.2.1).** OpenRegie is in early development. Features will change and
> bugs are likely. Please do **not** rely on it for important live streams yet.

🇩🇪 [Deutsch](#deutsch) · 🇬🇧 [English](#english)

---

## Deutsch

### Was ist OpenRegie?
OpenRegie ist eine **barrierefreie Regie-Software** für Livestreams unter Linux.
Sie ist für Menschen gemacht, die eine einfache, große und klare Bedienung brauchen,
zum Beispiel mit Joystick, Maus oder nur der Tastatur.

- **OBS** läuft unsichtbar als Motor im Hintergrund. OpenRegie steuert es über den OBS-WebSocket.
- **Overlays.uno** liefert alle Grafiken: ein- und ausblenden, Texte ändern, Countdown steuern.
- **Twitch**: Den Streamtitel direkt aus OpenRegie ändern.
- **Shots** (wie bei Wirecast): alle Szenen als große Kacheln mit Vorschaubild, ein Klick schaltet live.
  Neue Shots mit Zweck und Layout anlegen (z. B. Reactions: Video groß, Kamera klein) – ohne OBS zu öffnen.
- **Wenn-dann**: einfache Regeln (z. B. „Wenn der Stream startet → dann Shot ‚Pause‘ live“) und ein Zeitplan.
- Große Knöpfe, klare Farben, verständliche Meldungen ohne Fachsprache.
- Alle Farben, Texte und Größen lassen sich in `einstellungen.toml` anpassen.

### Installation unter Linux
**Voraussetzungen:** Python 3.11 oder neuer, PySide6 (Qt 6), OBS Studio 28 oder neuer
(mit WebSocket) und `secret-tool` (Passwortspeicher).

```sh
# Arch / CachyOS
sudo pacman -S python pyside6 obs-studio libsecret

# Fedora
sudo dnf install python3 python3-pyside6 obs-studio libsecret

# Debian / Ubuntu (24.04 oder neuer)
sudo apt install python3 python3-pyside6.qtwidgets python3-pyside6.qtwebsockets \
                 python3-pyside6.qtnetwork obs-studio libsecret-tools
```

Dann OpenRegie herunterladen und starten:
```sh
git clone https://github.com/Linux-for-everyone-creator/OpenRegie.git
cd OpenRegie
python3 -m openregie
```
Eintrag im Startmenü anlegen: `sh werkzeuge/startmenue_einrichten.sh`

### Einmalig in OBS einstellen
**Werkzeuge → WebSocket-Servereinstellungen → „WebSocket-Server aktivieren“** einschalten → **OK**.
Port und Passwort liest OpenRegie selbst aus den OBS-Einstellungen.
Nur falls das nicht klappt: `cp daten/geheim.beispiel.toml daten/geheim.toml` und das Passwort dort bei
`[obs] passwort` eintragen. Diese Datei wird nie hochgeladen.

### Overlays.uno verbinden
1. In Overlays.uno das Projekt öffnen, oben rechts im Menü **„API Description“** wählen und die Adresse kopieren.
2. In OpenRegie auf **„+“ (Uno-Projekt hinzufügen)** und dann auf **„Aus Zwischenablage einfügen“** klicken.

Die Adresse enthält einen geheimen Schlüssel. OpenRegie speichert sie deshalb verschlüsselt im
Passwortspeicher des Systems (KDE-Wallet bzw. GNOME-Schlüsselbund), nie in einer Datei des Projekts.

### Twitch einrichten
Nichts zu tun: Die **Client-ID** der OpenRegie-App bei Twitch ist in `einstellungen.toml` schon eingetragen.
Einfach auf **„Mit Twitch anmelden“** klicken und den angezeigten Code auf der Twitch-Seite bestätigen.

**Optional – eigene Twitch-Anwendung** (z. B. für einen eigenen Fork):
1. Auf https://dev.twitch.tv/console eine Anwendung registrieren (Weiterleitungs-URL `http://localhost`,
   Client-Typ **Öffentlich**).
2. Ihre **Client-ID** in `einstellungen.toml` bei `[twitch] client_id` eintragen. Sie ist kein Geheimnis.
3. OpenRegie neu starten.

### Für Entwickler
- Tests: `python3 -m unittest discover -s tests -t .`
- Test mit echtem OBS: `python3 werkzeuge/test_mit_echtem_obs.py`
- Test mit echtem Uno: `cp daten/geheim.beispiel.toml daten/geheim.toml`, eigene Adresse eintragen,
  dann `python3 werkzeuge/test_mit_echtem_uno.py --ja-schalten` (blendet kurz ein!).
  `daten/geheim.toml` wird von Git ignoriert. Bitte **niemals** echte Zugangsdaten committen.

### Entwicklung mit Claude Code & Mithilfe
OpenRegie wird mit Unterstützung von **[Claude Code](https://claude.com/claude-code)** (KI-Assistent von
Anthropic) entwickelt. **Mithilfe aus der Community ist herzlich willkommen!** Ob Fehlerberichte, Ideen
zur Barrierefreiheit, Übersetzungen, Tests oder Code: Öffne einfach ein Issue oder einen Pull Request.
Geplante Funktionen stehen in der [ROADMAP](ROADMAP.md), Änderungen im [CHANGELOG](CHANGELOG.md).

### Lizenz
[GPL-3.0](LICENSE) © Linux-for-everyone-creator

---

## English

### What is OpenRegie?
OpenRegie is **accessible live-production ("Regie") software** for streaming on Linux.
It is built for people who need a simple, large and clear interface, for example
when using a joystick, a mouse or only the keyboard.

- **OBS** runs invisibly in the background as the engine. OpenRegie controls it via OBS WebSocket.
- **Overlays.uno** provides all graphics: show and hide overlays, edit texts, control countdowns.
- **Twitch**: change your stream title right from OpenRegie.
- **Shots** (like Wirecast): every scene as a big tile with a preview, one click puts it on air.
  Create new shots by purpose and layout (e.g. reactions: video large, camera small) – without opening OBS.
- **If-then**: simple rules (e.g. "when the stream starts → put shot 'Pause' on air") and a schedule.
- Big buttons, clear colours, plain-language messages.
- All colours, texts and sizes are configurable in `einstellungen.toml`.

> The user interface is currently **German only**. Translations are very welcome!

### Installation on Linux
**Requirements:** Python 3.11+, PySide6 (Qt 6), OBS Studio 28+ (with WebSocket) and
`secret-tool` (system keyring).

```sh
# Arch / CachyOS
sudo pacman -S python pyside6 obs-studio libsecret

# Fedora
sudo dnf install python3 python3-pyside6 obs-studio libsecret

# Debian / Ubuntu (24.04 or newer)
sudo apt install python3 python3-pyside6.qtwidgets python3-pyside6.qtwebsockets \
                 python3-pyside6.qtnetwork obs-studio libsecret-tools
```

Then download and run OpenRegie:
```sh
git clone https://github.com/Linux-for-everyone-creator/OpenRegie.git
cd OpenRegie
python3 -m openregie
```
Add a start-menu entry: `sh werkzeuge/startmenue_einrichten.sh`

### One-time OBS setup
In OBS enable **Tools → WebSocket Server Settings → "Enable WebSocket server"** → **OK**.
OpenRegie reads the port and password from the OBS configuration automatically.
Only if that fails: `cp daten/geheim.beispiel.toml daten/geheim.toml` and put the password under
`[obs] passwort`. This file is never uploaded.

### Connecting Overlays.uno
1. Open your project in Overlays.uno, choose **"API Description"** in the top-right menu and copy the URL.
2. In OpenRegie click **"+" (add Uno project)**, then **"Aus Zwischenablage einfügen"** (paste from clipboard).

The URL contains a secret token, so OpenRegie stores it encrypted in the system keyring
(KDE Wallet / GNOME Keyring), never in a project file.

### Twitch setup
Nothing to do: the **Client ID** of the OpenRegie app on Twitch is already set in `einstellungen.toml`.
Just click **"Mit Twitch anmelden"** (log in with Twitch) and confirm the code shown on the Twitch page.

**Optional – your own Twitch application** (e.g. for your own fork):
1. Register an application at https://dev.twitch.tv/console (redirect URL `http://localhost`,
   client type **Public**).
2. Put its **Client ID** into `einstellungen.toml` under `[twitch] client_id`. It is not a secret.
3. Restart OpenRegie.

### For developers
- Tests: `python3 -m unittest discover -s tests -t .`
- Test against real OBS: `python3 werkzeuge/test_mit_echtem_obs.py`
- Test against real Uno: `cp daten/geheim.beispiel.toml daten/geheim.toml`, add your URL, then run
  `python3 werkzeuge/test_mit_echtem_uno.py --ja-schalten` (briefly shows overlays live!).
  `daten/geheim.toml` is git-ignored. **Never** commit real credentials.

### Built with Claude Code & contributing
OpenRegie is developed with the help of **[Claude Code](https://claude.com/claude-code)** (Anthropic's
AI coding assistant). **Community contributions are very welcome!** Bug reports, accessibility ideas,
translations, tests or code: just open an issue or a pull request.
Planned features are in the [ROADMAP](ROADMAP.md), changes in the [CHANGELOG](CHANGELOG.md).

### License
[GPL-3.0](LICENSE) © Linux-for-everyone-creator
