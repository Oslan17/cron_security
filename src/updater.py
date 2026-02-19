#!/usr/bin/env python3
"""
updater.py - Run security updates and save timestamped logs to disk.

Supports both Debian/Ubuntu (apt-get + unattended-upgrade)
and RHEL/Amazon Linux (yum --security).

Usage:
    python3 updater.py [config_file]
    python3 updater.py --dry-run        (print commands, don't execute)
"""

import os
import sys
import subprocess
import logging
from datetime import datetime
from pathlib import Path

from config import load_config

# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────
SEP  = "=" * 70
STAR = "*" * 70


def _detect_os() -> str:
    """
    Detect the package manager family.
    Returns 'debian' (apt-get) or 'rhel' (yum/dnf).
    """
    os_release = Path("/etc/os-release")
    if os_release.exists():
        content = os_release.read_text()
        for line in content.splitlines():
            if line.startswith("ID_LIKE=") or line.startswith("ID="):
                val = line.split("=", 1)[1].strip('"').lower()
                if any(x in val for x in ("debian", "ubuntu")):
                    return "debian"
                if any(x in val for x in ("rhel", "fedora", "centos", "amzn")):
                    return "rhel"
    # Fallback: check which binary exists
    if Path("/usr/bin/apt-get").exists():
        return "debian"
    return "rhel"


def _get_commands(os_family: str) -> list[tuple[str, list[str]]]:
    """Return list of (step_label, command) tuples for the detected OS."""
    if os_family == "debian":
        return [
            ("STEP 1 — Update package index (apt-get update)",
             ["apt-get", "update"]),
            ("STEP 2 — Apply security patches (unattended-upgrade -d)",
             ["unattended-upgrade", "-d"]),
        ]
    else:  # rhel / amazon linux
        return [
            ("STEP 1 — Check for security updates (yum check-update --security)",
             ["yum", "check-update", "--security"]),
            ("STEP 2 — Apply security patches (yum update --security -y)",
             ["yum", "update", "--security", "-y"]),
        ]


def _run(cmd: list[str], log_fh, dry_run: bool = False) -> int:
    """Run a command, stream output to log file, return exit code."""
    log_fh.write(f"$ {' '.join(cmd)}\n")
    log_fh.flush()

    if dry_run:
        log_fh.write("[DRY-RUN] command not executed\n\n")
        return 0

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=1800,   # 30 min hard limit
    )
    log_fh.write(result.stdout or "")
    log_fh.write(f"\n[exit {result.returncode}]\n\n")
    log_fh.flush()
    # yum check-update returns 100 when updates are available (not an error)
    if cmd[0] == "yum" and "check-update" in cmd and result.returncode == 100:
        return 0
    return result.returncode


def run_updates(config_file: str = "/etc/security-updater/config.env",
                dry_run: bool = False) -> int:
    """
    Execute security patching workflow. Returns 0 on success, 1 on failure.
    Saves a timestamped log file to config.log_dir.
    """
    cfg = load_config(config_file)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if dry_run:
        log_dir = "/tmp/security-updates-dryrun"
    else:
        log_dir = cfg.log_dir

    Path(log_dir).mkdir(parents=True, exist_ok=True)
    log_path = os.path.join(log_dir, f"security-update_{timestamp}.log")

    os_family = _detect_os()
    steps = _get_commands(os_family)

    log.info("Starting security update workflow")
    log.info(f"Server  : {cfg.server_name}  ({cfg.environment})")
    log.info(f"OS      : {os_family}")
    log.info(f"Log file: {log_path}")

    exit_code = 0

    with open(log_path, "w", encoding="utf-8") as fh:
        # ── Header ──────────────────────────────────────────────────────────
        fh.write(f"{SEP}\n")
        fh.write("Security Update Log\n")
        fh.write(f"Server      : {cfg.server_name}\n")
        fh.write(f"Environment : {cfg.environment}\n")
        fh.write(f"OS Family   : {os_family}\n")
        fh.write(f"Started     : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        fh.write(f"{SEP}\n\n")

        for label, cmd in steps:
            fh.write(f"{STAR}\n")
            fh.write(f"{label}\n")
            fh.write(f"{STAR}\n\n")

            rc = _run(cmd, fh, dry_run)
            if rc != 0:
                log.warning(f"Command '{cmd[0]}' exited with code {rc}")
                exit_code = 1

        # ── Footer ───────────────────────────────────────────────────────────
        status = "SUCCESS" if exit_code == 0 else "COMPLETED WITH ERRORS"
        fh.write(f"\n{SEP}\n")
        fh.write(f"Status  : {status}\n")
        fh.write(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        fh.write(f"{SEP}\n")

    log.info(f"Done — status: {status}")
    return exit_code


def main():
    dry_run = "--dry-run" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    config_file = args[0] if args else "/etc/security-updater/config.env"

    sys.exit(run_updates(config_file, dry_run=dry_run))


if __name__ == "__main__":
    main()
