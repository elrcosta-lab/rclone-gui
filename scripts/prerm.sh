#!/bin/bash
set -e

echo "=== Removendo rclone-gui ==="

rm -f /usr/local/bin/rclone-gui
rm -f /etc/xdg/autostart/rclone-gui-autostart.desktop

echo "=== rclone-gui removido ==="
