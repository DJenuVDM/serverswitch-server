#!/bin/bash
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
BOLD='\033[1m'
NC='\033[0m'

if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Please run as root: sudo bash uninstall.sh${NC}"
    exit 1
fi

read -p "Install directory [/opt/serverswitch]: " INSTALL_DIR
INSTALL_DIR="${INSTALL_DIR:-/opt/serverswitch}"

echo ""
read -p "Remove $INSTALL_DIR and uninstall service? [y/N]: " CONFIRM
if [[ ! "$CONFIRM" =~ ^[Yy] ]]; then
    echo "Cancelled."
    exit 0
fi

systemctl stop serverswitch 2>/dev/null || true
systemctl disable serverswitch 2>/dev/null || true
rm -f /etc/systemd/system/serverswitch.service
systemctl daemon-reload

# Remove sudo rule
sed -i "\|$INSTALL_DIR/screen_hardcopy.sh|d" /etc/sudoers

rm -rf "$INSTALL_DIR"

echo -e "${GREEN}${BOLD}✓ ServerSwitch uninstalled.${NC}"
