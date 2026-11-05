#!/bin/bash
# Build universal-downloader_2.0.3_all.deb
set -euo pipefail

ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VERSION="2.0.3"
PACKAGE="universal-downloader_${VERSION}_all.deb"
STAGE="$ROOT/packaging/stage"
DEBIAN_DIR="$ROOT/packaging/debian"

rm -rf "$STAGE" "$PACKAGE"
mkdir -p "$STAGE/DEBIAN"

# --- DEBIAN control scripts
cp "$DEBIAN_DIR/DEBIAN/control" "$DEBIAN_DIR/DEBIAN/postinst" \
   "$DEBIAN_DIR/DEBIAN/prerm" "$DEBIAN_DIR/DEBIAN/postrm" "$STAGE/DEBIAN/"
chmod 755 "$STAGE/DEBIAN/postinst" "$STAGE/DEBIAN/prerm" "$STAGE/DEBIAN/postrm"
chmod 644 "$STAGE/DEBIAN/control"

# --- Application files under /opt/universal-downloader
mkdir -p "$STAGE/opt/universal-downloader"
cp -r "$ROOT/universal_downloader" "$STAGE/opt/universal-downloader/"

# Remove __pycache__ if any made its way in
find "$STAGE/opt" -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true

# --- Launcher in /usr/bin
mkdir -p "$STAGE/usr/bin"
cat > "$STAGE/usr/bin/universal-downloader" <<'EOF'
#!/bin/sh
# Universal Downloader launcher
PYTHONPATH=/opt/universal-downloader exec /usr/bin/python3 -m universal_downloader "$@"
EOF
chmod 755 "$STAGE/usr/bin/universal-downloader"

# --- Desktop menu entry
mkdir -p "$STAGE/usr/share/applications"
cp "$ROOT/assets/universal-downloader.desktop" "$STAGE/usr/share/applications/"

# --- Icons
for size in 16 32 48 64 128 256; do
  mkdir -p "$STAGE/usr/share/icons/hicolor/${size}x${size}/apps"
  if [ -f "$ROOT/assets/icon-${size}.png" ]; then
    cp "$ROOT/assets/icon-${size}.png" \
      "$STAGE/usr/share/icons/hicolor/${size}x${size}/apps/universal-downloader.png"
  fi
done

# --- Documentation
mkdir -p "$STAGE/usr/share/doc/universal-downloader"
cp "$ROOT/README.md" "$ROOT/FEATURES.md" "$STAGE/usr/share/doc/universal-downloader/"
if [ -f "$ROOT/packaging/debian/changelog" ]; then
  cp "$ROOT/packaging/debian/changelog" "$STAGE/usr/share/doc/universal-downloader/changelog"
fi
if [ -f "$ROOT/packaging/debian/copyright" ]; then
  cp "$ROOT/packaging/debian/copyright" "$STAGE/usr/share/doc/universal-downloader/copyright"
fi

# --- Build the package
dpkg-deb --build "$STAGE" "$PACKAGE"
echo "Built: $ROOT/$PACKAGE"
sha256sum "$PACKAGE" > "$PACKAGE.sha256"
cat "$PACKAGE.sha256"
