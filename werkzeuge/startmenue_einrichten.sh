#!/bin/sh
# Legt den Startmenü-Eintrag für OpenRegie an (oder erneuert ihn).
# Aufruf:  sh werkzeuge/startmenue_einrichten.sh
set -e
ORDNER="$(cd "$(dirname "$0")/.." && pwd)"
ANWENDUNGEN="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
SYMBOLE="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"
mkdir -p "$ANWENDUNGEN" "$SYMBOLE"
# alten Eintrag aus der Zeit vor der Umbenennung (Rolliregie) entfernen
rm -f "$ANWENDUNGEN/rolliregie.desktop" "$SYMBOLE/rolliregie.svg"
cp "$ORDNER/daten/openregie.svg" "$SYMBOLE/openregie.svg"
cat > "$ANWENDUNGEN/openregie.desktop" <<EINTRAG
[Desktop Entry]
Type=Application
Name=OpenRegie
GenericName=Profi-Regie für alle. Einfach live.
Comment=Sendezentrale für Livestreams – steuert OBS
Exec=/usr/bin/python3 -m openregie
Path=$ORDNER
Icon=openregie
Terminal=false
Categories=AudioVideo;Video;
Keywords=Stream;OBS;Regie;Livestream;Overlays;Twitch;
StartupWMClass=openregie
StartupNotify=true
EINTRAG
chmod 644 "$ANWENDUNGEN/openregie.desktop"
command -v update-desktop-database >/dev/null && update-desktop-database "$ANWENDUNGEN" 2>/dev/null || true
command -v kbuildsycoca6 >/dev/null && kbuildsycoca6 >/dev/null 2>&1 || true
echo "Fertig: OpenRegie steht jetzt im Startmenü."
