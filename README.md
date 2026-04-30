# ServerSwitch Server

The server-side component of ServerSwitch. Runs a lightweight API on your machine
so the Android app can check status, shut down, reboot, and run custom scripts remotely over Tailscale.

## Install

```bash
git clone https://github.com/DJenuVDM/serverswitch-server
cd serverswitch-server
sudo bash install.sh
```

The script will prompt you for:
- Install directory (default: `/opt/serverswitch`)
- Port (default: `5050`)
- Auth token (your secret password)
- Whether to install `psutil` for CPU/RAM/disk stats

At the end it prints your IP, port, and token — paste those into the Android app.

## Adding custom scripts

Any executable file you place in the `scripts/` directory will appear in the Android app under **Run Script**. The app lets you pass arguments and optionally run the script inside a named `screen` session so you can monitor its output live.

```bash
# Copy your script into the scripts directory
sudo cp my_script.sh /opt/serverswitch/scripts/

# Make it executable
sudo chmod +x /opt/serverswitch/scripts/my_script.sh
```

No restart is needed — the server reads the folder on every request.

Scripts can be anything executable: Bash, Python, compiled binaries, etc. They run as the same user the serverswitch service runs as, so make sure that user has the permissions your script needs.

### Running scripts in a screen session

When you run a script from the app you can tick **Run in screen session** and give the session a name. The server will launch the script with `screen -dmS <name> <script> [args]`, keeping it alive in the background. After it starts, the app offers to open the live log view for that session directly.

You can also attach to the session manually from the server:

```bash
screen -r <session-name>
```

## Endpoints

| Method | Endpoint                        | Auth | Description                              |
|--------|---------------------------------|------|------------------------------------------|
| GET    | `/status`                       | No   | Returns `{"status":"on"}`                |
| GET    | `/ping`                         | No   | Lightweight ping                         |
| GET    | `/info`                         | Yes  | CPU, RAM, disk, uptime                   |
| GET    | `/screens`                      | Yes  | List active screen sessions              |
| GET    | `/screens/<name>/log`           | Yes  | Full accumulated log for a screen        |
| GET    | `/screens/<name>/log/tail`      | Yes  | New lines since a given offset           |
| POST   | `/screens/<name>/command`       | Yes  | Send a command to a screen session       |
| GET    | `/scripts`                      | Yes  | List executable scripts in `scripts/`    |
| POST   | `/scripts/run/<name>`           | Yes  | Run a script, optionally in a screen     |
| POST   | `/shutdown`                     | Yes  | Shuts the server down                    |
| POST   | `/reboot`                       | Yes  | Reboots the server                       |

Auth = pass your token in the `X-Token` header.

### `/scripts/run/<name>` body

```json
{
  "args": ["--port", "8080"],
  "screen_name": "myapp"
}
```

Both fields are optional. Omit `screen_name` to run the script detached without a screen session.

## Update from GitHub

```bash
sudo bash update.sh
```

The script will:
- Back up your current config
- Download the latest version from GitHub
- Update `server.py` and the helper scripts
- **Leave your `scripts/` directory completely untouched**
- Restore your config
- Restart the service

## File layout

```
/opt/serverswitch/
├── server.py               ← API server (updated by update.sh)
├── screen_hardcopy.sh      ← screen log helper (updated by update.sh)
├── screen_command.sh       ← screen command helper (updated by update.sh)
├── config.env              ← your token and port (never modified by update.sh)
├── serverswitch.log        ← live log output
├── venv/                   ← Python virtualenv
└── scripts/                ← your custom scripts go here
    └── my_script.sh
```

## Useful commands

```bash
# Check service status
systemctl status serverswitch

# View server logs
tail -f /opt/serverswitch/serverswitch.log

# Restart the service
sudo systemctl restart serverswitch

# Add a new script
sudo cp my_script.sh /opt/serverswitch/scripts/
sudo chmod +x /opt/serverswitch/scripts/my_script.sh

# Update from GitHub (your scripts/ folder is preserved)
sudo bash update.sh
```

## Uninstall

```bash
sudo bash uninstall.sh
```

The uninstaller will list any scripts in `scripts/` and ask whether to save them to `~/serverswitch_scripts_backup/` before removing the installation.