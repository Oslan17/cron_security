# Quick Start

## Install on EC2 (3 steps)

```bash
# 1. Copy project to server
scp -r ./cron_security user@your-ec2:/tmp/

# 2. Install (run on the server)
ssh user@your-ec2
cd /tmp/cron_security && sudo bash scripts/install.sh

# 3. Set your server name
sudo nano /etc/security-updater/config.env
#    → change SERVER_NAME=EC2-Production-Server
```

Done. The system is now active and scheduled automatically.

---

## Schedule

| Timer | When | Action |
|-------|------|--------|
| `security-updater.timer` | Every Sunday 00:00 | Security patches |
| `monthly-report.timer` | 1st of every month 01:00 | PDF report |

---

## Test Locally (no root needed)

```bash
# Simulate an update run
cd src && python3 updater.py --dry-run

# Generate a PDF from existing logs
cd src && python3 report.py ../config/config.env.example 2026 2
# → reports/security_monthly_202602_EC2-bastion-dev-Server.pdf
```

---

## Key Commands (on EC2)

```bash
# Check schedule
systemctl list-timers

# Run update now
sudo systemctl start security-updater.service

# Generate report now
sudo systemctl start monthly-report.service

# Stream logs
journalctl -u security-updater.service -f

# View reports
ls /var/reports/security-updates/
```

---

## File Locations (on server)

```
/opt/security-updater/          ← scripts
/etc/security-updater/config.env ← configuration
/var/log/security-updates/      ← update logs
/var/reports/security-updates/  ← monthly PDFs
```
