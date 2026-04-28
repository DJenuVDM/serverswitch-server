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

# ── Header ────────────────────────────────────────────────────────────────────
clear
echo -e "${BOLD}"
echo "  ███████╗███████╗██████╗ ██╗   ██╗███████╗██████╗ "
echo "  ██╔════╝██╔════╝██╔══██╗██║   ██║██╔════╝██╔══██╗"
echo "  ███████╗█████╗  ██████╔╝██║   ██║█████╗  ██████╔╝"
echo "  ╚════██║██╔══╝  ██╔══██╗╚██╗ ██╔╝██╔══╝  ██╔══██╗"
echo "  ███████║███████╗██║  ██║ ╚████╔╝ ███████╗██║  ██║"
echo "  ╚══════╝╚══════╝╚═╝  ╚═╝  ╚═══╝  ╚══════╝╚═╝  ╚═╝"
echo -e "${NC}"
echo -e "  ${BOLD}ServerSwitch${NC} — Remote server control API"
echo -e "  ${YELLOW}github.com/jenu/serverswitch${NC}\n"
echo "─────────────────────────────────────────────────────"

# ── Must be root ──────────────────────────────────────────────────────────────
if [ "$EUID" -ne 0 ]; then
    print_error "Please run as root: sudo bash install.sh"
    exit 1
fi

# ── Gather config ─────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}Let's set up your ServerSwitch install.${NC}"
echo ""

# Install dir
read -p "  Install directory [/opt/serverswitch]: " INSTALL_DIR
INSTALL_DIR="${INSTALL_DIR:-/opt/serverswitch}"

# Port
read -p "  Port to listen on [5050]: " PORT
PORT="${PORT:-5050}"

# Token
echo ""
echo -e "  ${YELLOW}Choose an auth token. This is the password your app uses"
echo -e "  to send shutdown/reboot commands. Make it something random.${NC}"
echo ""
while true; do
    read -s -p "  Auth token: " TOKEN
    echo ""
    read -s -p "  Confirm token: " TOKEN2
    echo ""
    if [ "$TOKEN" = "$TOKEN2" ] && [ -n "$TOKEN" ]; then
        break
    fi
    print_warn "Tokens don't match or are empty, try again."
done

# psutil for /info endpoint
echo ""
read -p "  Install psutil for CPU/RAM/disk stats? [Y/n]: " INSTALL_PSUTIL
INSTALL_PSUTIL="${INSTALL_PSUTIL:-Y}"

echo ""
echo "─────────────────────────────────────────────────────"
echo -e "  Install dir : ${BOLD}$INSTALL_DIR${NC}"
echo -e "  Port        : ${BOLD}$PORT${NC}"
echo -e "  Token       : ${BOLD}$(echo "$TOKEN" | sed 's/./*/g')${NC}"
echo "─────────────────────────────────────────────────────"
echo ""
read -p "  Looks good? Install now? [Y/n]: " CONFIRM
CONFIRM="${CONFIRM:-Y}"
if [[ "$CONFIRM" =~ ^[Nn] ]]; then
    echo "Cancelled."
    exit 0
fi

# ── Install ───────────────────────────────────────────────────────────────────
print_step "Creating install directory"
mkdir -p "$INSTALL_DIR"
print_ok "Created $INSTALL_DIR"

print_step "Installing system dependencies"
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip
print_ok "Python installed"

print_step "Creating Python virtual environment"
python3 -m venv "$INSTALL_DIR/venv"
print_ok "Venv created"

print_step "Installing Python packages"
"$INSTALL_DIR/venv/bin/pip" install --quiet flask gunicorn
if [[ "$INSTALL_PSUTIL" =~ ^[Yy] ]]; then
    "$INSTALL_DIR/venv/bin/pip" install --quiet psutil
    print_ok "flask, gunicorn, psutil installed"
else
    print_ok "flask, gunicorn installed"
fi

print_step "Copying server files"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "$SCRIPT_DIR/server.py" "$INSTALL_DIR/server.py"
cp "$SCRIPT_DIR/screen_hardcopy.sh" "$INSTALL_DIR/screen_hardcopy.sh"
chmod +x "$INSTALL_DIR/screen_hardcopy.sh"
print_ok "server.py and screen_hardcopy.sh copied and made executable"

print_step "Writing config"
cat > "$INSTALL_DIR/config.env" << EOF
# ServerSwitch config
# Generated by install.sh — edit carefully

AUTH_TOKEN=$TOKEN
PORT=$PORT
EOF
chmod 600 "$INSTALL_DIR/config.env"
print_ok "config.env written (permissions: 600)"

print_step "Installing systemd service"
sed \
    -e "s|INSTALL_DIR|$INSTALL_DIR|g" \
    -e "s|PORT|$PORT|g" \
    "$SCRIPT_DIR/serverswitch.service.template" \
    > /etc/systemd/system/serverswitch.service

systemctl daemon-reload
systemctl enable serverswitch
systemctl restart serverswitch
print_ok "Service installed and started"

print_step "Setting up sudo permissions for screen log access"
if ! grep -q "screen_hardcopy.sh" /etc/sudoers; then
    echo "root ALL=(ALL) NOPASSWD: $INSTALL_DIR/screen_hardcopy.sh" >> /etc/sudoers
    print_ok "Sudo rule added for screen log access"
else
    print_ok "Sudo rule already exists"
fi

# ── Verify ────────────────────────────────────────────────────────────────────
print_step "Verifying"
sleep 2
if curl -s "http://localhost:$PORT/status" | grep -q "on"; then
    print_ok "Server is responding on port $PORT"
else
    print_warn "Server may not be responding yet — check: systemctl status serverswitch"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "─────────────────────────────────────────────────────"
echo -e "  ${GREEN}${BOLD}✓ ServerSwitch installed successfully!${NC}"
echo ""
echo -e "  Status : ${BOLD}systemctl status serverswitch${NC}"
echo -e "  Logs   : ${BOLD}tail -f $INSTALL_DIR/serverswitch.log${NC}"
echo -e "  Test   : ${BOLD}curl http://localhost:$PORT/status${NC}"
echo ""
echo -e "  ${YELLOW}Add this to your ServerSwitch Android app:${NC}"
echo -e "  IP    : $(hostname -I | awk '{print $1}')"
echo -e "  Port  : $PORT"
echo -e "  Token : $TOKEN"
echo "─────────────────────────────────────────────────────"
echo ""
