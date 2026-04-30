#!/bin/bash
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Please run as root: sudo bash uninstall.sh${NC}"
    exit 1
fi

read -p "Install directory [/opt/serverswitch]: " INSTALL_DIR
INSTALL_DIR="${INSTALL_DIR:-/opt/serverswitch}"

if [ ! -d "$INSTALL_DIR" ]; then
    echo -e "${RED}Directory $INSTALL_DIR not found — nothing to uninstall.${NC}"
    exit 1
fi

# Show what scripts would be deleted
SCRIPT_COUNT=$(find "$INSTALL_DIR/scripts" -maxdepth 1 -type f 2>/dev/null | wc -l)
if [ "$SCRIPT_COUNT" -gt 0 ]; then
    echo ""
    echo -e "${YELLOW}The following custom scripts are in $INSTALL_DIR/scripts/:${NC}"
    find "$INSTALL_DIR/scripts" -maxdepth 1 -type f | sort | while read -r f; do
        echo "    • $(basename "$f")"
    done
    echo ""
    read -p "  Keep your scripts/ directory? [Y/n]: " KEEP_SCRIPTS
    KEEP_SCRIPTS="${KEEP_SCRIPTS:-Y}"
else
    KEEP_SCRIPTS="N"
fi

echo ""
read -p "Remove $INSTALL_DIR and uninstall service? [y/N]: " CONFIRM
if [[ ! "$CONFIRM" =~ ^[Yy] ]]; then
    echo "Cancelled."
    exit 0
fi

# Stop and remove service
systemctl stop serverswitch    2>/dev/null || true
systemctl disable serverswitch 2>/dev/null || true
rm -f /etc/systemd/system/serverswitch.service
systemctl daemon-reload

# Remove sudo rules
sed -i "\|$INSTALL_DIR/screen_hardcopy.sh|d" /etc/sudoers
sed -i "\|$INSTALL_DIR/screen_command.sh|d"   /etc/sudoers

# Save scripts before wiping if user asked
if [[ "$KEEP_SCRIPTS" =~ ^[Yy] ]] && [ "$SCRIPT_COUNT" -gt 0 ]; then
    SAVE_DIR="$HOME/serverswitch_scripts_backup"
    mkdir -p "$SAVE_DIR"
    cp -r "$INSTALL_DIR/scripts/." "$SAVE_DIR/"
    echo -e "${YELLOW}Scripts saved to $SAVE_DIR${NC}"
fi

rm -rf "$INSTALL_DIR"

echo ""
if [[ "$KEEP_SCRIPTS" =~ ^[Yy] ]] && [ "$SCRIPT_COUNT" -gt 0 ]; then
    echo -e "${GREEN}${BOLD}✓ ServerSwitch uninstalled.${NC}"
    echo -e "  Your scripts were saved to ${BOLD}$HOME/serverswitch_scripts_backup/${NC}"
else
    echo -e "${GREEN}${BOLD}✓ ServerSwitch uninstalled.${NC}"
fi
echo ""