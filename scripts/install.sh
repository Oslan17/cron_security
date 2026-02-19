#!/bin/bash
# Installation script for Security Update Automation System
# Usage: sudo bash scripts/install.sh

set -euo pipefail

echo "=========================================="
echo " Security Update Automation - Installer"
echo "=========================================="
echo ""

# ── Root check ───────────────────────────────────────────────────────────────
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: Run as root (sudo bash scripts/install.sh)"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
INSTALL_DIR="/opt/security-updater"
CONFIG_DIR="/etc/security-updater"

echo "Project : $PROJECT_DIR"
echo ""

# ── System dependencies ───────────────────────────────────────────────────────
echo "[1/6] Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq python3 python3-pip unattended-upgrades curl

# ── uv ───────────────────────────────────────────────────────────────────────
echo "[2/6] Installing uv..."
if ! command -v uv &>/dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi
# uv installs to ~/.local/bin
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

# ── Copy files ────────────────────────────────────────────────────────────────
echo "[3/6] Copying source files to $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
cp "$PROJECT_DIR/src/updater.py"   "$INSTALL_DIR/"
cp "$PROJECT_DIR/src/report.py"    "$INSTALL_DIR/"
cp "$PROJECT_DIR/src/config.py"    "$INSTALL_DIR/"
cp "$PROJECT_DIR/requirements.txt" "$INSTALL_DIR/"

# ── Python dependencies ───────────────────────────────────────────────────────
echo "[4/6] Installing Python dependencies..."
uv pip install --system -r "$INSTALL_DIR/requirements.txt"

# ── Configuration ─────────────────────────────────────────────────────────────
echo "[5/6] Setting up configuration..."
mkdir -p "$CONFIG_DIR"
if [ ! -f "$CONFIG_DIR/config.env" ]; then
    cp "$PROJECT_DIR/config/config.production.env" "$CONFIG_DIR/config.env"
    echo "  → Created $CONFIG_DIR/config.env — edit SERVER_NAME and ENVIRONMENT!"
else
    echo "  → $CONFIG_DIR/config.env already exists, skipping"
fi

# Create data directories with correct permissions (read paths from the installed config)
LOG_DIR=$(grep '^LOG_DIR' "$CONFIG_DIR/config.env" | cut -d= -f2)
REPORT_DIR=$(grep '^REPORT_DIR' "$CONFIG_DIR/config.env" | cut -d= -f2)
mkdir -p "$LOG_DIR" "$REPORT_DIR"
chmod 750 "$LOG_DIR" "$REPORT_DIR"
echo "  → Logs    : $LOG_DIR"
echo "  → Reports : $REPORT_DIR"

# ── systemd services & timers ─────────────────────────────────────────────────
echo "[6/6] Creating systemd services and timers..."

# --- security-updater.service ---
cat > /etc/systemd/system/security-updater.service <<'EOF'
[Unit]
Description=Security Update Automation
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /opt/security-updater/updater.py /etc/security-updater/config.env
StandardOutput=journal
StandardError=journal
SyslogIdentifier=security-updater

[Install]
WantedBy=multi-user.target
EOF

# --- security-updater.timer (every Sunday at 00:00) ---
cat > /etc/systemd/system/security-updater.timer <<'EOF'
[Unit]
Description=Weekly security update timer
Requires=security-updater.service

[Timer]
OnCalendar=Sun *-*-* 00:00:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

# --- monthly-report.service ---
cat > /etc/systemd/system/monthly-report.service <<'EOF'
[Unit]
Description=Monthly Security PDF Report Generator
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /opt/security-updater/report.py /etc/security-updater/config.env
StandardOutput=journal
StandardError=journal
SyslogIdentifier=monthly-report

[Install]
WantedBy=multi-user.target
EOF

# --- monthly-report.timer (1st of every month at 01:00) ---
cat > /etc/systemd/system/monthly-report.timer <<'EOF'
[Unit]
Description=Monthly security report timer
Requires=monthly-report.service

[Timer]
OnCalendar=*-*-01 01:00:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now security-updater.timer monthly-report.timer

# ── Done ───────────────────────────────────────────────────────────────────────
echo ""
echo "=========================================="
echo " Installation complete!"
echo "=========================================="
echo ""
echo "  Config  : $CONFIG_DIR/config.env  ← edit SERVER_NAME here"
echo "  Logs    : $LOG_DIR"
echo "  Reports : $REPORT_DIR"
echo ""
echo "Useful commands:"
echo "  systemctl list-timers                        # view schedule"
echo "  systemctl start security-updater.service     # run update now"
echo "  systemctl start monthly-report.service       # generate report now"
echo "  journalctl -u security-updater.service -f    # stream logs"
echo ""
