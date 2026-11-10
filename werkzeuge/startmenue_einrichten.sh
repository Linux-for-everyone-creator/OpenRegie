#!/bin/sh
# Legt den Startmenü-Eintrag für Rolliregie an (oder erneuert ihn).
# Aufruf:  sh werkzeuge/startmenue_einrichten.sh
set -e
ORDNER="$(cd "$(dirname "$0")/.." && pwd)"
ANWENDUNGEN="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
SYMBOLE="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"
mkdir -p "$ANWENDUNGEN" "$SYMBOLE"
cp "$ORDNER/daten/rolliregie.svg" "$SYMBOLE/rolliregie.svg"
cat > "$ANWENDUNGEN/rolliregie.desktop" <<EINTRAG
[Desktop Entry]
Type=Application
Name=Rolliregie
GenericName=Barrierefrei streamen
Comment=Sendezentrale für Livestreams – steuert OBS
Exec=/usr/bin/python3 -m rolliregie
Path=$ORDNER
Icon=rolliregie
Terminal=false
Categories=AudioVideo;Video;
Keywords=Stream;OBS;Regie;Livestream;Countdown;
StartupWMClass=rolliregie
StartupNotify=true
EINTRAG
chmod 644 "$ANWENDUNGEN/rolliregie.desktop"
command -v update-desktop-database >/dev/null && update-desktop-database "$ANWENDUNGEN" 2>/dev/null || true
command -v kbuildsycoca6 >/dev/null && kbuildsycoca6 >/dev/null 2>&1 || true
echo "Fertig: Rolliregie steht jetzt im Startmenü."
