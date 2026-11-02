#!/bin/sh
# Remove Desk Charms. Your settings stay in ~/.config/desk-charms unless you pass --purge.
set -e

pkill -f '^[^ ]*python3 [^ ]*desk_charms\.py' 2>/dev/null || true
rm -rf "$HOME/.local/share/desk-charms"
rm -f "$HOME/.local/share/applications/desk-charms.desktop" \
      "$HOME/.local/share/applications/desk-charms-settings.desktop" \
      "$HOME/.local/share/icons/hicolor/256x256/apps/desk-charms.png" \
      "$HOME/.config/autostart/desk-charms.desktop"
rm -rf "$HOME/.cache/desk-charms"
if [ "$1" = "--purge" ]; then
    rm -rf "$HOME/.config/desk-charms"
    echo "Desk Charms and its settings are removed."
else
    echo "Desk Charms is removed. Settings kept in ~/.config/desk-charms (use --purge to delete them)."
fi
