#!/usr/bin/env bash
set -e

REPO_URL="https://github.com/edwinshamel/hd2-mod-manager.git"
INSTALL_DIR="$HOME/hd2-mod-manager"
DESKTOP_FILE="$HOME/.local/share/applications/hd2-mod-manager.desktop"

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warning() { echo -e "${YELLOW}[AVISO]${NC} $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

echo ""
echo "  HD2 Mod Manager - Instalador"
echo "  =============================="
echo ""

# ── 1. Detectar gestor de paquetes ──────────────────────────────────────────
info "Detectando gestor de paquetes..."

if command -v apt &>/dev/null; then
    PKG_MANAGER="apt"
    PKG_INSTALL="sudo apt-get install -y"
    DEPS="python3 git python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 python3-requests python3-packaging"
elif command -v dnf &>/dev/null; then
    PKG_MANAGER="dnf"
    PKG_INSTALL="sudo dnf install -y"
    DEPS="python3 git python3-gobject gtk4 libadwaita python3-requests python3-packaging"
elif command -v pacman &>/dev/null; then
    PKG_MANAGER="pacman"
    PKG_INSTALL="sudo pacman -S --noconfirm"
    DEPS="python git python-gobject gtk4 libadwaita python-requests python-packaging"
else
    error "No se encontró un gestor de paquetes compatible (apt, dnf, pacman)."
fi

success "Gestor de paquetes detectado: $PKG_MANAGER"

# ── 2. Instalar dependencias ─────────────────────────────────────────────────
info "Instalando dependencias: $DEPS"
$PKG_INSTALL $DEPS || error "Falló la instalación de dependencias."
success "Dependencias instaladas correctamente."

# ── 3. Clonar o actualizar el repositorio ────────────────────────────────────
if [ -d "$INSTALL_DIR/.git" ]; then
    info "El repositorio ya existe en $INSTALL_DIR, actualizando..."
    git -C "$INSTALL_DIR" pull origin master || error "Falló al actualizar el repositorio."
    success "Repositorio actualizado."
else
    info "Clonando repositorio en $INSTALL_DIR..."
    git clone "$REPO_URL" "$INSTALL_DIR" || error "Falló al clonar el repositorio."
    success "Repositorio clonado correctamente."
fi

# ── 4. Crear archivo .desktop ────────────────────────────────────────────────
info "Creando acceso directo en el menú de aplicaciones..."

mkdir -p "$HOME/.local/share/applications"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Name=HD2 Mod Manager
Comment=Gestor de mods para Helldivers 2
Exec=python3 $INSTALL_DIR/main.py
Icon=applications-games
Terminal=false
Type=Application
Categories=Game;Utility;
StartupNotify=true
EOF

success "Archivo .desktop creado en $DESKTOP_FILE"

# ── 5. Hacer main.py ejecutable ───────────────────────────────────────────────
chmod +x "$INSTALL_DIR/main.py"

# ── 6. Refrescar menú de aplicaciones según el escritorio ────────────────────
info "Actualizando menú de aplicaciones..."

case "$XDG_CURRENT_DESKTOP" in
    KDE)
        kbuildsycoca6 --noincremental 2>/dev/null || true
        ;;
    *)
        update-desktop-database "$HOME/.local/share/applications/" 2>/dev/null || true
        ;;
esac

success "Menú actualizado."

# ── 7. Listo ─────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}  Instalación completada.${NC}"
echo ""
echo "  Puedes abrir la app desde el menú de aplicaciones"
echo "  buscando 'HD2 Mod Manager', o ejecutando:"
echo ""
echo -e "    ${BLUE}python3 $INSTALL_DIR/main.py${NC}"
echo ""
