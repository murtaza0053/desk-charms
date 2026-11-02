#!/bin/sh
# Install Desk Charms for the current user (no sudo needed once the packages are present).
#
#   ./install.sh              copy the app into ~/.local/share/desk-charms
#   ./install.sh --autostart  ...and start it when you log in
#   ./install.sh --link       link to this folder instead of copying (for working on the code)
set -e

HERE=$(cd "$(dirname "$0")" && pwd)
DEST="$HOME/.local/share/desk-charms"
APPS="$HOME/.local/share/applications"
ICONS="$HOME/.local/share/icons/hicolor/256x256/apps"
AUTOSTART=0
LINK=0
for arg in "$@"; do
    case "$arg" in
        --autostart) AUTOSTART=1 ;;
        --link) LINK=1 ;;
        -h|--help) sed -n '2,7p' "$0"; exit 0 ;;
        *) echo "Unknown option: $arg"; exit 1 ;;
    esac
done

# --- what the app needs ---------------------------------------------------------------------
missing=""
python3 -c 'import gi; gi.require_version("Gtk", "3.0"); from gi.repository import Gtk' 2>/dev/null \
    || missing="$missing python3-gi gir1.2-gtk-3.0"
python3 -c 'import cairo; import gi; gi.require_foreign("cairo")' 2>/dev/null || missing="$missing python3-gi-cairo"
python3 -c 'import gi; gi.require_version("PangoCairo", "1.0"); from gi.repository import PangoCairo' 2>/dev/null \
    || missing="$missing gir1.2-pango-1.0"
if [ -n "$missing" ]; then
    echo "Desk Charms needs a few packages first:"
    echo "  sudo apt install$missing"
    exit 1
fi
command -v paplay >/dev/null || echo "Note: no 'paplay', so no sound. Install it with: sudo apt install pulseaudio-utils"
fc-list | grep -qi "Noto Color Emoji" || echo "Note: for the emoji charm install: sudo apt install fonts-noto-color-emoji"
if [ "${XDG_SESSION_TYPE:-}" = "wayland" ]; then
    echo "Note: you are on Wayland. Desk Charms runs through XWayland there; if it misbehaves,"
    echo "      log out and pick 'Ubuntu on Xorg' from the gear icon on the login screen."
fi

# --- the app itself -------------------------------------------------------------------------
rm -rf "$DEST"
if [ "$LINK" = 1 ]; then
    ln -s "$HERE" "$DEST"
else
    mkdir -p "$DEST"
    cp "$HERE"/*.py "$DEST"/
    cp -r "$HERE/assets" "$DEST"/
fi

mkdir -p "$ICONS" "$APPS"
cp "$HERE/assets/icon.png" "$ICONS/desk-charms.png"
RUN="env GDK_BACKEND=x11 python3 $DEST/desk_charms.py"

cat > "$APPS/desk-charms.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Desk Charms
Comment=A lucky charm hanging from the top of your screen
Exec=$RUN
Icon=desk-charms
Terminal=false
Categories=Utility;
EOF

cat > "$APPS/desk-charms-settings.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Desk Charms Settings
Comment=Change the charm, size, swing, sound and position
Exec=$RUN --settings
Icon=desk-charms
Terminal=false
Categories=Settings;
EOF

if [ "$AUTOSTART" = 1 ]; then
    mkdir -p "$HOME/.config/autostart"
    cat > "$HOME/.config/autostart/desk-charms.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Desk Charms
Comment=A lucky charm hanging from the top of your screen
Exec=sh -c "sleep 5; exec $RUN"
Icon=desk-charms
Terminal=false
X-GNOME-Autostart-enabled=true
EOF
fi

update-desktop-database "$APPS" 2>/dev/null || true
echo "Installed. Open 'Desk Charms' from your app menu, or run: $RUN"
[ "$AUTOSTART" = 1 ] && echo "It will also start when you log in."
exit 0
