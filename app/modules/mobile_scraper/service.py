"""
Mobile Scraper module business logic: drives jd_api_scraper.py running on a
Samsung S8 (Termux) over SSH — start/stop the process, check whether it's
alive, and tail its log.
"""
import os
import re
import shlex
import subprocess
from typing import Optional

from app_config import CONFIG as APP_CONFIG

REMOTE_SCRIPT_PATH = "~/justdial-scraper/jd_api_scraper.py"
REMOTE_LOG_PATH = "~/scrape.log"
PROCESS_PATTERN = "jd_api_scraper.py"

DEFAULT_MOBILE_DEVICE = {
    "host": "",
    "port": 8022,
    "username": "",
    "key_path": "~/.ssh/id_rsa",
}


def get_ssh_config() -> dict:
    mobile_cfg = APP_CONFIG.get("mobile_device") if isinstance(APP_CONFIG, dict) else None
    return {**DEFAULT_MOBILE_DEVICE, **(mobile_cfg or {})}


def _ssh_base_args(cfg: dict) -> list:
    key_path = os.path.expanduser(str(cfg.get("key_path") or DEFAULT_MOBILE_DEVICE["key_path"]))
    return [
        "ssh",
        "-i", key_path,
        "-p", str(cfg.get("port") or DEFAULT_MOBILE_DEVICE["port"]),
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "ConnectTimeout=6",
        "-o", "BatchMode=yes",
        f"{cfg.get('username')}@{cfg.get('host')}",
    ]


def _run_ssh_command(remote_command: str, timeout: int = 15) -> dict:
    """Run a command on the S8 over SSH. Returns {ok, stdout, stderr}."""
    cfg = get_ssh_config()
    if not cfg.get("host") or not cfg.get("username"):
        return {"ok": False, "stdout": "", "stderr": "mobile_device.host/username not configured in config.yaml"}

    args = _ssh_base_args(cfg) + [remote_command]
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return {"ok": result.returncode == 0, "stdout": result.stdout, "stderr": result.stderr}
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": "SSH command timed out"}
    except FileNotFoundError:
        return {"ok": False, "stdout": "", "stderr": "ssh client not found on this machine"}
    except Exception as e:
        return {"ok": False, "stdout": "", "stderr": str(e)}


def is_connected() -> bool:
    result = _run_ssh_command("echo ok", timeout=6)
    return result["ok"] and "ok" in result["stdout"]


def is_running() -> bool:
    result = _run_ssh_command(f"pgrep -f {shlex.quote(PROCESS_PATTERN)}", timeout=8)
    return result["ok"] and result["stdout"].strip() != ""


def start_scrape(district: str, category: str, pages: int) -> dict:
    if is_running():
        return {"ok": False, "error": "A scrape is already running on the device"}

    safe_district = shlex.quote(district)
    safe_category = shlex.quote(category)
    remote_command = (
        f"nohup python {REMOTE_SCRIPT_PATH} --district {safe_district} --category {safe_category} "
        f"--pages {int(pages)} > {REMOTE_LOG_PATH} 2>&1 &"
    )
    result = _run_ssh_command(remote_command, timeout=15)
    if not result["ok"]:
        return {"ok": False, "error": result["stderr"] or "Failed to start scrape via SSH"}
    return {"ok": True}


def stop_scrape() -> dict:
    was_running = is_running()
    _run_ssh_command(f"pkill -f {shlex.quote(PROCESS_PATTERN)}", timeout=10)
    return {"ok": True, "stopped": was_running}


def parse_stats(log_text: str) -> dict:
    """Best-effort scrape of running counters out of the scraper's own log lines."""
    saved = len(re.findall(r"\bsaved\b", log_text, re.IGNORECASE))
    duplicates = len(re.findall(r"\bduplicate", log_text, re.IGNORECASE))
    return {"records_saved": saved, "duplicates_skipped": duplicates}


def get_log(lines: int = 50) -> dict:
    result = _run_ssh_command(f"tail -n {int(lines)} {REMOTE_LOG_PATH}", timeout=10)
    if not result["ok"]:
        return {"ok": False, "log": "", "records_saved": 0, "duplicates_skipped": 0, "error": result["stderr"]}
    log_text = result["stdout"]
    return {"ok": True, "log": log_text, **parse_stats(log_text)}


def get_status() -> dict:
    connected = is_connected()
    running = is_running() if connected else False
    return {"connected": connected, "running": running}
