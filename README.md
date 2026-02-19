# 🔒 Security Update Automation

Automated weekly security patching for EC2 (Ubuntu/Debian) servers, with monthly PDF reports delivered directly to Telegram.

![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python&logoColor=white)
![Ubuntu](https://img.shields.io/badge/Ubuntu-20.04%2B-E95420?logo=ubuntu&logoColor=white)
![systemd](https://img.shields.io/badge/Scheduled-systemd-informational)
![Telegram](https://img.shields.io/badge/Reports-Telegram-2CA5E0?logo=telegram&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 📋 Overview

| When | What | Result |
|------|------|--------|
| Every Sunday 00:00 | `apt-get update` + `unattended-upgrade -d` | Timestamped log saved |
| 1st of every month 01:00 | Collect all monthly logs → build PDF | PDF sent to Telegram channel |

---

## 🏗️ Architecture

```
cron_security/
├── src/
│   ├── config.py      # Typed config loader (reads config.env)
│   ├── updater.py     # Runs security patches, saves logs
│   └── report.py      # Builds PDF report + sends to Telegram
├── config/
│   ├── config.env.example       # Template for local development
│   └── config.production.env   # Template for EC2 server
├── scripts/
│   └── install.sh     # One-command installer
└── docs/
    ├── QUICKSTART.md
    └── INSTALLATION.md
```

---

## 🚀 Quick Install (EC2)

```bash
# 1. Copy project to server
scp -r ./cron_security user@your-ec2:/tmp/

# 2. Run installer on the server
ssh user@your-ec2
cd /tmp/cron_security && sudo bash scripts/install.sh

# 3. Edit server name + add Telegram credentials
sudo nano /etc/security-updater/config.env
```

→ See [docs/QUICKSTART.md](docs/QUICKSTART.md) for the full 3-step guide.  
→ See [docs/INSTALLATION.md](docs/INSTALLATION.md) for step-by-step details, Ansible, and troubleshooting.

---

## ⚙️ Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_DIR` | `/var/log/security-updates` | Where logs are saved |
| `REPORT_DIR` | `/var/reports/security-updates` | Where PDFs are saved |
| `SERVER_NAME` | `EC2-Server` | Name shown in reports |
| `ENVIRONMENT` | `production` | `production`, `staging`, `dev` |
| `TELEGRAM_BOT_TOKEN` | _(empty)_ | Bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | _(empty)_ | Channel ID (get it via `getUpdates` API) |

> If `TELEGRAM_BOT_TOKEN` or `TELEGRAM_CHAT_ID` are empty, the Telegram send is silently skipped.

---

## 📄 PDF Report

Each monthly PDF includes:
- Summary table (server, environment, period, total updates)
- Per-update section: status banner (🟢 SUCCESS / 🔴 ERROR), timing, packages updated table, errors, raw log

---

## 🔧 Useful Commands

```bash
# View schedule
systemctl list-timers

# Run update now
sudo systemctl start security-updater.service

# Generate & send report now
sudo systemctl start monthly-report.service

# Stream logs
journalctl -u security-updater.service -f
journalctl -u monthly-report.service -f

# Test locally without root
cd src && python3 updater.py --dry-run
cd src && python3 report.py ../config/config.env.example 2026 2
```

---

## 📦 Requirements

| Requirement | Version |
|-------------|---------|
| OS | Ubuntu 20.04+ / Debian 10+ |
| Python | 3.9+ |
| Access | `sudo` / root |
| Internet | Required |

**Python deps** (installed automatically): `reportlab`, `python-dotenv`

---

## 🗑️ Uninstall

```bash
sudo systemctl disable --now security-updater.timer monthly-report.timer
sudo rm /etc/systemd/system/security-updater.{service,timer}
sudo rm /etc/systemd/system/monthly-report.{service,timer}
sudo rm -rf /opt/security-updater /etc/security-updater
sudo systemctl daemon-reload
```

---

## 👤 Author

**Oslan Villalobos** — [@Oslan17](https://github.com/Oslan17)
