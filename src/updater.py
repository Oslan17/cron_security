#!/usr/bin/env python3
"""
updater.py - Run security updates and save timestamped logs to disk.

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
SEP = "=" * 70
STAR = "*" * 70


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

    # Ensure log directory exists
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    log_path = os.path.join(log_dir, f"security-update_{timestamp}.log")

    log.info("Starting security update workflow")
    log.info(f"Server  : {cfg.server_name}  ({cfg.environment})")
    log.info(f"Log file: {log_path}")

    exit_code = 0

    with open(log_path, "w", encoding="utf-8") as fh:
        # ── Header ──────────────────────────────────────────────────────────
        fh.write(f"{SEP}\n")
        fh.write(f"Security Update Log\n")
        fh.write(f"Server      : {cfg.server_name}\n")
        fh.write(f"Environment : {cfg.environment}\n")
        fh.write(f"Started     : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        fh.write(f"{SEP}\n\n")

        # ── Step 1: apt-get update ───────────────────────────────────────────
        fh.write(f"{STAR}\n")
        fh.write("STEP 1 — Update package index (apt-get update)\n")
        fh.write(f"{STAR}\n\n")

        rc = _run(["apt-get", "update"], fh, dry_run)
        if rc != 0:
            log.warning(f"apt-get update exited with code {rc}")
            exit_code = 1

        # ── Step 2: unattended-upgrade ───────────────────────────────────────
        fh.write(f"{STAR}\n")
        fh.write("STEP 2 — Apply security patches (unattended-upgrade -d)\n")
        fh.write(f"{STAR}\n\n")

        rc = _run(["unattended-upgrade", "-d"], fh, dry_run)
        if rc != 0:
            log.warning(f"unattended-upgrade exited with code {rc}")
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
