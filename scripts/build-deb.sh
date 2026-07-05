#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VERSION="${1:-0.3.0}"
DEB_NAME="rclone-gui_${VERSION}_all.deb"
BUILD_DIR="$(mktemp -d)"

if ! command -v fpm &>/dev/null; then
    echo "fpm não encontrado. Instale com: gem install fpm"
    exit 1
fi

chmod +x "$SCRIPT_DIR/postinst.sh" "$SCRIPT_DIR/prerm.sh"
chmod +x "$PROJECT_DIR/packaging/rclone-gui-autostart.desktop"

echo "=== Instalando dependências Python em $BUILD_DIR/opt/rclone-gui ==="

python3 -m venv "$BUILD_DIR/opt/rclone-gui/venv"
source "$BUILD_DIR/opt/rclone-gui/venv/bin/activate"

cd "$PROJECT_DIR"
pip install --no-cache-dir .

deactivate

cat > "$BUILD_DIR/opt/rclone-gui/venv/bin/rclone-gui" << 'ENTRYPOINT'
#!/usr/bin/env bash
DIR="$(cd "$(dirname "$0")/../.." && pwd)"
exec "$DIR/venv/bin/python" -m rclone_gui "$@"
ENTRYPOINT
chmod +x "$BUILD_DIR/opt/rclone-gui/venv/bin/rclone-gui"

mkdir -p "$BUILD_DIR/usr/share/applications"
cp "$PROJECT_DIR/packaging/rclone-gui.desktop" "$BUILD_DIR/usr/share/applications/"

mkdir -p "$BUILD_DIR/etc/xdg/autostart"
cp "$PROJECT_DIR/packaging/rclone-gui-autostart.desktop" "$BUILD_DIR/etc/xdg/autostart/"

mkdir -p "$BUILD_DIR/usr/share/icons/hicolor/scalable/apps"
cp "$PROJECT_DIR/packaging/rclone-gui.svg" "$BUILD_DIR/usr/share/icons/hicolor/scalable/apps/"

echo "=== Gerando .deb ==="

fpm -s dir -t deb \
    -n rclone-gui \
    -v "$VERSION" \
    --description "Rclone GUI — interface gráfica para rclone" \
    --url "https://github.com/anomalyco/rclone-gui" \
    --maintainer "Emerson" \
    --license "MIT" \
    --category "Utility" \
    --architecture all \
    -d "python3 >= 3.9" \
    -d "python3-pip" \
    -d "python3-venv" \
    --recommends "rclone" \
    --recommends "fuse3" \
    --after-install "$SCRIPT_DIR/postinst.sh" \
    --before-remove "$SCRIPT_DIR/prerm.sh" \
    -C "$BUILD_DIR" \
    opt usr etc

mv *.deb "$PROJECT_DIR/"
echo "=== .deb gerado: $DEB_NAME ==="

rm -rf "$BUILD_DIR"
