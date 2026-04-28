# ServerSwitch Server

The server-side component of ServerSwitch. Runs a lightweight API on your machine
so the Android app can check status, shut down, or reboot it remotely over Tailscale.

## Install

```bash
git clone https://github.com/yourname/serverswitch-server
cd serverswitch-server
sudo bash install.sh
```

The script will prompt you for:
- Install directory (default: `/opt/serverswitch`)
- Port (default: `5050`)
- Auth token (your secret password)
- Whether to install `psutil` for CPU/RAM/disk stats

At the end it prints your IP, port, and token — paste those into the Android app.

## Endpoints

| Method | Endpoint    | Auth | Description                        |
|--------|-------------|------|------------------------------------|
| GET    | `/status`   | No   | Returns `{"status":"on"}`          |
| GET    | `/ping`     | No   | Lightweight ping                   |
| GET    | `/info`     | Yes  | CPU, RAM, disk, uptime             |
| POST   | `/shutdown` | Yes  | Shuts the server down              |
| POST   | `/reboot`   | Yes  | Reboots the server                 |

Auth = pass your token in the `X-Token` header.

## Useful commands

```bash
# Check status
systemctl status serverswitch

# View logs
tail -f /opt/serverswitch/serverswitch.log

# Restart
sudo systemctl restart serverswitch

# Edit config (token, port)
sudo nano /opt/serverswitch/config.env
sudo systemctl restart serverswitch
```

## Uninstall

```bash
sudo bash uninstall.sh
```
