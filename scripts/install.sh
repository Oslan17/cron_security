#!/bin/bash
# Security Update Automation — Universal Installer
# Supports: Ubuntu 20.04+, Debian 10+, Amazon Linux 2, RHEL/CentOS 7+
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

# ── OS Detection ─────────────────────────────────────────────────────────────
OS_FAMILY="unknown"
PKG_MANAGER="unknown"

if [ -f /etc/os-release ]; then
    . /etc/os-release
    case "${ID_LIKE:-$ID}" in
        *debian*|*ubuntu*)
            OS_FAMILY="debian"
            PKG_MANAGER="apt"
            ;;
        *rhel*|*fedora*|*centos*|*amzn*)
            OS_FAMILY="rhel"
            PKG_MANAGER="yum"
            ;;
    esac
fi

# Fallback: binary check
if [ "$OS_FAMILY" = "unknown" ]; then
    command -v apt-get &>/dev/null && OS_FAMILY="debian" PKG_MANAGER="apt"
    command -v yum     &>/dev/null && OS_FAMILY="rhel"   PKG_MANAGER="yum"
fi

echo "OS      : ${PRETTY_NAME:-$OS_FAMILY}"
echo ""

if [ "$OS_FAMILY" = "unknown" ]; then
    echo "ERROR: Unsupported OS. Requires Ubuntu/Debian or Amazon Linux/RHEL/CentOS."
    exit 1
fi

# ── System dependencies ───────────────────────────────────────────────────────
echo "[1/6] Installing system dependencies..."
if [ "$PKG_MANAGER" = "apt" ]; then
    apt-get update -qq
    apt-get install -y -qq python3 python3-pip unattended-upgrades curl
    PYTHON_BIN="python3"
else
    yum update -y -q
    yum install -y -q python3 python3-pip curl
    # Amazon Linux 2 ships Python 3.7 which is too old for our deps.
    # Use amazon-linux-extras to get Python 3.8.
    PYTHON_BIN="python3"
    if python3 --version 2>&1 | grep -qE '3\.[0-7]\.'; then
        echo "  → Python 3.7 detected, upgrading to 3.8 via amazon-linux-extras..."
        amazon-linux-extras install python3.8 -y 2>/dev/null || true
        if command -v python3.8 &>/dev/null; then
            PYTHON_BIN="python3.8"
            echo "  → Using $PYTHON_BIN"
        fi
    fi
fi
echo "  → Python: $($PYTHON_BIN --version)"

# ── uv ───────────────────────────────────────────────────────────────────────
echo "[2/6] Installing uv..."
if ! command -v uv &>/dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi
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
uv pip install --python "$PYTHON_BIN" --system -r "$INSTALL_DIR/requirements.txt"

# ── Configuration ─────────────────────────────────────────────────────────────
echo "[5/6] Setting up configuration..."
mkdir -p "$CONFIG_DIR"
if [ ! -f "$CONFIG_DIR/config.env" ]; then
    cp "$PROJECT_DIR/config/config.production.env" "$CONFIG_DIR/config.env"
    echo "  → Created $CONFIG_DIR/config.env — edit SERVER_NAME + Telegram credentials!"
else
    echo "  → $CONFIG_DIR/config.env already exists, skipping"
fi

# Create data directories from config
LOG_DIR=$(grep '^LOG_DIR' "$CONFIG_DIR/config.env" | cut -d= -f2)
REPORT_DIR=$(grep '^REPORT_DIR' "$CONFIG_DIR/config.env" | cut -d= -f2)
mkdir -p "$LOG_DIR" "$REPORT_DIR"
chmod 750 "$LOG_DIR" "$REPORT_DIR"
echo "  → Logs    : $LOG_DIR"
echo "  → Reports : $REPORT_DIR"

# ── systemd services & timers ─────────────────────────────────────────────────
echo "[6/6] Creating systemd services and timers..."

cat > /etc/systemd/system/security-updater.service <<EOF
[Unit]
Description=Security Update Automation
After=network.target

[Service]
Type=oneshot
ExecStart=$(command -v $PYTHON_BIN) /opt/security-updater/updater.py /etc/security-updater/config.env
StandardOutput=journal
StandardError=journal
SyslogIdentifier=security-updater

[Install]
WantedBy=multi-user.target
EOF

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

cat > /etc/systemd/system/monthly-report.service <<EOF
[Unit]
Description=Monthly Security PDF Report Generator
After=network.target

[Service]
Type=oneshot
ExecStart=$(command -v $PYTHON_BIN) /opt/security-updater/report.py /etc/security-updater/config.env
StandardOutput=journal
StandardError=journal
SyslogIdentifier=monthly-report

[Install]
WantedBy=multi-user.target
EOF

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

# ── Done ─────────────────────────────────────────────────────────────────────
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
