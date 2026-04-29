#!/bin/bash
set -e

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

print_step()  { echo -e "\n${BLUE}${BOLD}▶ $1${NC}"; }
print_ok()    { echo -e "${GREEN}✓ $1${NC}"; }
print_warn()  { echo -e "${YELLOW}⚠ $1${NC}"; }
print_error() { echo -e "${RED}✗ $1${NC}"; }

# ── Must be root ──────────────────────────────────────────────────────────────
if [ "$EUID" -ne 0 ]; then
    print_error "Please run as root: sudo bash update.sh"
    exit 1
fi

# ── Get install directory ─────────────────────────────────────────────────────
read -p "Install directory [/opt/serverswitch]: " INSTALL_DIR
INSTALL_DIR="${INSTALL_DIR:-/opt/serverswitch}"

if [ ! -d "$INSTALL_DIR" ]; then
    print_error "Install directory $INSTALL_DIR not found. Run install.sh first."
    exit 1
fi

# ── Backup current config ─────────────────────────────────────────────────────
print_step "Backing up current configuration"
if [ -f "$INSTALL_DIR/config.env" ]; then
    cp "$INSTALL_DIR/config.env" "$INSTALL_DIR/config.env.backup"
    print_ok "Config backed up to config.env.backup"
else
    print_warn "No config file found to backup"
fi

# ── Download latest version ───────────────────────────────────────────────────
print_step "Downloading latest version from GitHub"
TEMP_DIR=$(mktemp -d)
cd "$TEMP_DIR"

# Clone the latest
if git clone --depth 1 https://github.com/DJenuVDM/serverswitch-server.git . 2>/dev/null; then
    print_ok "Downloaded latest version"
else
    print_error "Failed to download from GitHub"
    rm -rf "$TEMP_DIR"
    exit 1
fi

# ── Update files ──────────────────────────────────────────────────────────────
print_step "Updating server files"
cp server.py "$INSTALL_DIR/server.py"
cp screen_hardcopy.sh "$INSTALL_DIR/screen_hardcopy.sh"
cp screen_command.sh "$INSTALL_DIR/screen_command.sh"
chmod +x "$INSTALL_DIR/screen_hardcopy.sh"
chmod +x "$INSTALL_DIR/screen_command.sh"

# Restore config
if [ -f "$INSTALL_DIR/config.env.backup" ]; then
    cp "$INSTALL_DIR/config.env.backup" "$INSTALL_DIR/config.env"
    print_ok "Config restored"
fi

# Clean up
cd /
rm -rf "$TEMP_DIR"

# ── Restart service ───────────────────────────────────────────────────────────
print_step "Restarting ServerSwitch service"
systemctl restart serverswitch
sleep 2

if systemctl is-active --quiet serverswitch; then
    print_ok "Service restarted successfully"
else
    print_warn "Service may have issues - check: systemctl status serverswitch"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "─────────────────────────────────────────────────────"
echo -e "  ${GREEN}${BOLD}✓ ServerSwitch updated successfully!${NC}"
echo ""
echo -e "  Check logs: ${BOLD}tail -f $INSTALL_DIR/serverswitch.log${NC}"
echo -e "  Service status: ${BOLD}systemctl status serverswitch${NC}"
echo "─────────────────────────────────────────────────────"
echo ""