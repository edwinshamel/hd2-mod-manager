#!/usr/bin/env bash
set -e

REPO_URL="https://github.com/edwinshamel/hd2-mod-manager.git"
INSTALL_DIR="$HOME/hd2-mod-manager"
DESKTOP_FILE="$HOME/.local/share/applications/hd2-mod-manager.desktop"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

echo ""
echo "  HD2 Mod Manager - Installer"
echo "  ============================"
echo ""

# ── 1. Detect package manager ───────────────────────────────────────────────
info "Detecting package manager..."

if command -v apt &>/dev/null; then
    PKG_MANAGER="apt"
    PKG_INSTALL="sudo apt-get install -y"
    DEPS="python3 git python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-gdkpixbuf-2.0 python3-requests python3-packaging"
elif command -v dnf &>/dev/null; then
    PKG_MANAGER="dnf"
    PKG_INSTALL="sudo dnf install -y"
    DEPS="python3 git python3-gobject gtk4 libadwaita python3-requests python3-packaging"
elif command -v pacman &>/dev/null; then
    PKG_MANAGER="pacman"
    PKG_INSTALL="sudo pacman -S --noconfirm"
    DEPS="python git python-gobject gtk4 libadwaita python-requests python-packaging"
else
    error "No compatible package manager found (apt, dnf, pacman)."
fi

success "Package manager detected: $PKG_MANAGER"

# ── 2. Install dependencies ──────────────────────────────────────────────────
info "Installing dependencies: $DEPS"
$PKG_INSTALL $DEPS || error "Failed to install dependencies."
success "Dependencies installed."

# ── 3. Clone or update repository ───────────────────────────────────────────
if [ -d "$INSTALL_DIR/.git" ]; then
    info "Repository already exists at $INSTALL_DIR, updating..."
    git -C "$INSTALL_DIR" pull origin master || error "Failed to update repository."
    success "Repository updated."
else
    info "Cloning repository to $INSTALL_DIR..."
    git clone "$REPO_URL" "$INSTALL_DIR" || error "Failed to clone repository."
    success "Repository cloned."
fi

# ── 4. Create .desktop file ──────────────────────────────────────────────────
info "Creating application shortcut..."

mkdir -p "$HOME/.local/share/applications"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Name=HD2 Mod Manager
Comment=Mod manager for Helldivers 2
Exec=python3 $INSTALL_DIR/main.py
Icon=$INSTALL_DIR/assets/icon.png
Terminal=false
Type=Application
Categories=Game;Utility;
StartupNotify=true
EOF

success "Shortcut created at $DESKTOP_FILE"

# ── 5. Make main.py executable ───────────────────────────────────────────────
chmod +x "$INSTALL_DIR/main.py"

# ── 6. Refresh application menu ─────────────────────────────────────────────
info "Refreshing application menu..."

case "$XDG_CURRENT_DESKTOP" in
    KDE)
        kbuildsycoca6 --noincremental 2>/dev/null || true
        ;;
    *)
        update-desktop-database "$HOME/.local/share/applications/" 2>/dev/null || true
        ;;
esac

success "Application menu updated."

# ── 7. Done ──────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}  Installation complete.${NC}"
echo ""
echo "  Launch HD2 Mod Manager from your application menu,"
echo "  or run:"
echo ""
echo -e "    ${BLUE}python3 $INSTALL_DIR/main.py${NC}"
echo ""
