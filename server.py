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

# ── Rate limiting (max 10 requests/min per IP) ────────────────────────────────
request_counts = defaultdict(list)

def rate_limit(max_per_minute=10):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            ip = request.remote_addr
            now = time.time()
            request_counts[ip] = [t for t in request_counts[ip] if now - t < 60]
            if len(request_counts[ip]) >= max_per_minute:
                log.warning(f"Rate limit hit from {ip}")
                return jsonify({"error": "rate_limited"}), 429
            request_counts[ip].append(now)
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

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/ping", methods=["GET"])
@rate_limit(60)
def ping():
    """Lightweight status check"""
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
    """Returns system stats"""
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

if __name__ == "__main__":
    config = load_config()
    port = int(config.get("PORT", 5050))
    log.info(f"ServerSwitch starting on port {port}")
    app.run(host="0.0.0.0", port=port)
