#!/usr/bin/env python3
"""
ServerSwitch - Status & Control API
"""

import subprocess
import os
import logging
from flask import Flask, jsonify, request
from functools import wraps
import time
from collections import defaultdict

app = Flask(__name__)

# ── Config (written by install.sh) ───────────────────────────────────────────
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.env")

def load_config():
    config = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    config[k.strip()] = v.strip()
    return config

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    filename=os.path.join(os.path.dirname(__file__), "serverswitch.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
log = logging.getLogger("serverswitch")

# ── Rate limiting — keyed per IP+endpoint so endpoints don't share buckets ────
request_counts = defaultdict(list)

def rate_limit(max_per_minute=10):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            key = f"{request.remote_addr}:{f.__name__}"
            now = time.time()
            request_counts[key] = [t for t in request_counts[key] if now - t < 60]
            if len(request_counts[key]) >= max_per_minute:
                log.warning(f"Rate limit hit from {request.remote_addr} on {f.__name__}")
                return jsonify({"error": "rate_limited"}), 429
            request_counts[key].append(now)
            return f(*args, **kwargs)
        return wrapper
    return decorator

def require_token(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        config = load_config()
        token = config.get("AUTH_TOKEN", "")
        provided = request.headers.get("X-Token", "")
        if not token or provided != token:
            ip = request.remote_addr
            log.warning(f"Unauthorized request from {ip}")
            return jsonify({"error": "unauthorized"}), 401
        return f(*args, **kwargs)
    return wrapper

def list_screens() -> list:
    """List all screen sessions by checking socket directories directly."""
    screens = []
    screen_dir = "/run/screen"

    try:
        if not os.path.exists(screen_dir):
            return []

        for item in os.listdir(screen_dir):
            user_dir = os.path.join(screen_dir, item)
            if not item.startswith("S-") or not os.path.isdir(user_dir):
                continue
            user = item[2:]

            try:
                for socket in os.listdir(user_dir):
                    if "." in socket:
                        screens.append(f"{user}/{socket}")
            except (OSError, PermissionError):
                pass

        return screens
    except (OSError, FileNotFoundError):
        return []


def capture_screen_log(screen_name: str, destination: str) -> None:
    if "/" in screen_name:
        user, session = screen_name.split("/", 1)
        script_path = os.path.join(os.path.dirname(__file__), "screen_hardcopy.sh")
        try:
            subprocess.check_call(["sudo", "-u", user, script_path, session, destination])
        except subprocess.CalledProcessError:
            raise
    else:
        try:
            subprocess.check_call(["screen", "-S", screen_name, "-X", "hardcopy", "-h", destination])
        except subprocess.CalledProcessError:
            subprocess.check_call(["screen", "-S", screen_name, "-X", "hardcopy", destination])


def get_persistent_log_path(screen_name: str) -> str:
    """
    Returns the path to a persistent append-only log file for a screen session.
    Unlike the hardcopy temp file, this file is never deleted between polls —
    new hardcopy snapshots are diffed against it and new lines are appended.
    """
    safe_name = screen_name.replace("..", "_").replace("/", "_")
    return os.path.join("/tmp", f"serverswitch_persist_{safe_name}.log")


def update_persistent_log(screen_name: str) -> list:
    """
    Takes a fresh hardcopy snapshot, diffs it against the persistent log,
    appends any genuinely new lines, and returns the full list of all lines
    seen so far.

    The core insight: hardcopy -h always dumps a fixed-size scrollback window.
    The window slides forward as new output arrives, so new lines appear at the
    bottom and old lines fall off the top. We detect new lines by comparing the
    tail of the snapshot to the tail of what we already have, then appending
    whatever is new.
    """
    safe_name = screen_name.replace("..", "_").replace("/", "_")
    snap_path = os.path.join("/tmp", f"serverswitch_snap_{safe_name}.log")
    persist_path = get_persistent_log_path(screen_name)

    # Take a fresh hardcopy snapshot
    capture_screen_log(screen_name, snap_path)
    if not os.path.exists(snap_path):
        raise FileNotFoundError(f"Snapshot not created at {snap_path}")

    with open(snap_path, "r", encoding="utf-8", errors="replace") as f:
        snap_lines = [l.rstrip() for l in f.read().splitlines()]

    try:
        os.remove(snap_path)
    except OSError:
        pass

    # Strip blank trailing lines that hardcopy pads with
    while snap_lines and not snap_lines[-1].strip():
        snap_lines.pop()

    # Load existing persistent log
    if os.path.exists(persist_path):
        with open(persist_path, "r", encoding="utf-8", errors="replace") as f:
            persist_lines = [l.rstrip() for l in f.read().splitlines()]
    else:
        persist_lines = []

    if not snap_lines:
        return persist_lines

    if not persist_lines:
        # First time — seed the persistent log with the full snapshot
        with open(persist_path, "w", encoding="utf-8") as f:
            f.write("\n".join(snap_lines) + "\n")
        return snap_lines

    # Find where the snapshot overlaps with the end of the persistent log.
    # We look for the longest suffix of persist_lines that matches a prefix
    # of snap_lines, so we can find where new lines begin.
    #
    # Example:
    #   persist: [A, B, C, D, E]
    #   snap:    [C, D, E, F, G]   ← scrollback window slid forward
    #   overlap starts at snap index 0 (C matches persist[-3])
    #   new lines: [F, G]

    new_lines = []
    max_overlap = min(len(persist_lines), len(snap_lines))

    overlap_start = None
    for overlap_len in range(max_overlap, 0, -1):
        if persist_lines[-overlap_len:] == snap_lines[:overlap_len]:
            overlap_start = overlap_len
            break

    if overlap_start is not None:
        new_lines = snap_lines[overlap_start:]
    else:
        # No overlap found — the scrollback has scrolled past everything we
        # had. Append the entire snapshot as new content.
        new_lines = snap_lines

    if new_lines:
        with open(persist_path, "a", encoding="utf-8") as f:
            f.write("\n".join(new_lines) + "\n")
        persist_lines.extend(new_lines)

    # Cap the persistent log to 5000 lines so it doesn't grow forever
    if len(persist_lines) > 5000:
        persist_lines = persist_lines[-5000:]
        with open(persist_path, "w", encoding="utf-8") as f:
            f.write("\n".join(persist_lines) + "\n")

    return persist_lines


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/ping", methods=["GET"])
@rate_limit(60)
def ping():
    return jsonify({"status": "on"})

@app.route("/status", methods=["GET"])
@rate_limit(60)
def status():
    return jsonify({"status": "on"})

@app.route("/shutdown", methods=["POST"])
@rate_limit(5)
@require_token
def shutdown():
    log.info(f"Shutdown requested from {request.remote_addr}")
    subprocess.Popen(["shutdown", "-h", "+0"])
    return jsonify({"status": "shutting_down"})

@app.route("/reboot", methods=["POST"])
@rate_limit(5)
@require_token
def reboot():
    log.info(f"Reboot requested from {request.remote_addr}")
    subprocess.Popen(["shutdown", "-r", "+0"])
    return jsonify({"status": "rebooting"})

@app.route("/info", methods=["GET"])
@rate_limit(30)
@require_token
def info():
    try:
        import psutil
        return jsonify({
            "status": "on",
            "cpu_percent": psutil.cpu_percent(interval=1),
            "ram_percent": psutil.virtual_memory().percent,
            "ram_used_gb": round(psutil.virtual_memory().used / 1e9, 1),
            "ram_total_gb": round(psutil.virtual_memory().total / 1e9, 1),
            "disk_percent": psutil.disk_usage("/").percent,
            "disk_used_gb": round(psutil.disk_usage("/").used / 1e9, 1),
            "disk_total_gb": round(psutil.disk_usage("/").total / 1e9, 1),
            "uptime_seconds": int(time.time() - psutil.boot_time()),
        })
    except ImportError:
        return jsonify({"status": "on", "error": "psutil not installed"})


@app.route("/screens", methods=["GET"])
@rate_limit(30)
@require_token
def screens():
    try:
        return jsonify({"screens": list_screens()})
    except FileNotFoundError:
        return jsonify({"error": "screen_not_installed"}), 500
    except subprocess.CalledProcessError as e:
        return jsonify({"error": "screen_list_failed", "details": str(e)}), 500


@app.route("/screens/<path:screen_name>/command", methods=["POST"])
@rate_limit(20)
@require_token
def screen_command(screen_name):
    try:
        data = request.get_json()
        if not data or "command" not in data:
            return jsonify({"error": "missing_command"}), 400

        command = data["command"]
        if not isinstance(command, str) or len(command) > 1000:
            return jsonify({"error": "invalid_command"}), 400

        command = command.replace("\n", "").replace("\r", "").replace("\t", " ")

        script_path = os.path.join(os.path.dirname(__file__), "screen_command.sh")

        if "/" in screen_name:
            user, session = screen_name.split("/", 1)
            subprocess.run([
                "sudo", "-u", user, script_path, session, command
            ], check=True, capture_output=True, text=True)
        else:
            return jsonify({"error": "invalid_screen_name"}), 400

        log.info(f"Executed command in screen {screen_name}: {command}")
        return jsonify({"status": "command_sent"})

    except subprocess.CalledProcessError as e:
        log.error(f"Screen command failed: {e}")
        return jsonify({"error": "command_failed", "details": str(e)}), 500
    except Exception as e:
        log.error(f"Screen command error: {e}")
        return jsonify({"error": "command_error"}), 500


@app.route("/screens/<path:screen_name>/log", methods=["GET"])
@rate_limit(30)
@require_token
def screen_log(screen_name):
    """Returns the full accumulated log for a screen session."""
    try:
        all_lines = update_persistent_log(screen_name)
        contents = "\n".join(all_lines)
        return jsonify({"screen": screen_name, "log": contents})
    except FileNotFoundError:
        log.error("screen command not found")
        return jsonify({"error": "screen_not_installed"}), 500
    except subprocess.CalledProcessError as e:
        log.error(f"screen command failed: {e}")
        return jsonify({"error": "screen_log_failed", "details": str(e)}), 500


@app.route("/screens/<path:screen_name>/log/tail", methods=["GET"])
@rate_limit(60)
@require_token
def screen_log_tail(screen_name):
    """
    Return only new lines since a given line offset.
    Query param: ?offset=N  (pass 0 on first call, then pass returned next_offset each time)

    Uses a persistent append-only log so the offset is stable across polls —
    unlike the old approach where hardcopy always returned a fixed-size window
    and the offset would never advance past the buffer size.
    """
    try:
        offset = int(request.args.get("offset", 0))
        all_lines = update_persistent_log(screen_name)
        new_lines = all_lines[offset:]
        return jsonify({
            "screen": screen_name,
            "new_lines": new_lines,
            "next_offset": len(all_lines)
        })
    except (ValueError, TypeError):
        return jsonify({"error": "invalid_offset"}), 400
    except FileNotFoundError:
        log.error("screen command not found")
        return jsonify({"error": "screen_not_installed"}), 500
    except subprocess.CalledProcessError as e:
        log.error(f"screen tail failed: {e}")
        return jsonify({"error": "screen_log_failed", "details": str(e)}), 500


if __name__ == "__main__":
    config = load_config()
    port = int(config.get("PORT", 5050))
    log.info(f"ServerSwitch starting on port {port}")
    app.run(host="0.0.0.0", port=port)

# ── Script management ─────────────────────────────────────────────────────────

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "scripts")


def _get_scripts() -> list:
    """Return sorted list of executable files in the scripts/ directory."""
    if not os.path.isdir(SCRIPTS_DIR):
        return []
    result = []
    for name in sorted(os.listdir(SCRIPTS_DIR)):
        path = os.path.join(SCRIPTS_DIR, name)
        if os.path.isfile(path) and os.access(path, os.X_OK):
            result.append(name)
    return result


@app.route("/scripts", methods=["GET"])
@rate_limit(30)
@require_token
def list_scripts():
    """List all executable scripts in the scripts/ directory."""
    return jsonify({"scripts": _get_scripts()})


@app.route("/scripts/run/<script_name>", methods=["POST"])
@rate_limit(10)
@require_token
def run_script(script_name):
    """
    Run a script from the scripts/ directory.

    JSON body (all optional):
      args        – list of string arguments passed to the script
      screen_name – if provided, the script is launched inside a detached
                    screen session with this name
    """
    import re
    try:
        if not script_name or "/" in script_name or ".." in script_name:
            return jsonify({"error": "invalid_script_name"}), 400

        script_path = os.path.join(SCRIPTS_DIR, script_name)
        if not os.path.isfile(script_path) or not os.access(script_path, os.X_OK):
            return jsonify({"error": "script_not_found"}), 404

        data = request.get_json(silent=True) or {}
        args = data.get("args", [])
        screen_name = data.get("screen_name", "").strip()

        if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
            return jsonify({"error": "invalid_args"}), 400
        if len(args) > 64:
            return jsonify({"error": "too_many_args"}), 400
        for a in args:
            if len(a) > 500:
                return jsonify({"error": "arg_too_long"}), 400

        if screen_name:
            if not re.match(r'^[a-zA-Z0-9_-]{1,64}$', screen_name):
                return jsonify({"error": "invalid_screen_name"}), 400

            # Resolve screen binary — systemd runs with a stripped PATH so we
            # check common install locations explicitly if which() fails.
            import shutil
            screen_bin = shutil.which("screen") or next(
                (p for p in ["/usr/bin/screen", "/bin/screen", "/usr/local/bin/screen"]
                 if os.path.isfile(p)), None)
            if not screen_bin:
                log.error("screen binary not found — install it with: sudo apt install screen")
                return jsonify({"error": "screen_not_installed",
                                "details": "screen binary not found on this server"}), 500

            cmd = [screen_bin, "-dmS", screen_name, script_path] + args
            subprocess.Popen(cmd)
            log.info(f"Script '{script_name}' launched in screen '{screen_name}' from {request.remote_addr}")
        else:
            subprocess.Popen([script_path] + args)
            log.info(f"Script '{script_name}' launched from {request.remote_addr}")

        return jsonify({"status": "started", "script": script_name, "screen": screen_name or None})

    except Exception as e:
        log.error(f"run_script error: {e}")
        return jsonify({"error": "run_failed", "details": str(e)}), 500