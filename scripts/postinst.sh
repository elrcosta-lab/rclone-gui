#!/bin/bash
set -e

echo "=== Pós-instalação rclone-gui ==="

VENV="/opt/rclone-gui/venv"
ENTRYPOINT="$VENV/bin/rclone-gui"

# Garantir permissão de execução no entry point
chmod +x "$ENTRYPOINT"

# Criar symlink global
ln -sf "$ENTRYPOINT" /usr/local/bin/rclone-gui

# Garantir permissão de execução no autostart desktop
chmod +x /etc/xdg/autostart/rclone-gui-autostart.desktop

echo "=== rclone-gui instalado em /opt/rclone-gui ==="
echo "=== Execute 'rclone-gui' para iniciar ==="
echo "=== Verifique se rclone está instalado: which rclone ==="
