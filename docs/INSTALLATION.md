# Installation Guide

## What `install.sh` Does

Runs 6 steps automatically:

| Step | Action |
|------|--------|
| 1 | `apt-get install python3 python3-pip unattended-upgrades curl` |
| 2 | Installs `uv` (fast Python package manager) |
| 3 | Copies `src/` files to `/opt/security-updater/` |
| 4 | `uv pip install -r requirements.txt` (`reportlab`, `python-dotenv`) |
| 5 | Creates `/etc/security-updater/config.env` from `config.production.env` |
| 6 | Creates and enables systemd services + timers |

---

## Step-by-Step

### 1. Copy project to the server

```bash
# From your local machine
scp -r /home/oslan/cron_security user@your-ec2:/tmp/
```

### 2. Run the installer

```bash
ssh user@your-ec2
cd /tmp/cron_security
sudo bash scripts/install.sh
```

Expected output:
```
==========================================
 Security Update Automation - Installer
==========================================

Project : /tmp/cron_security

[1/6] Installing system dependencies...
[2/6] Installing uv...
[3/6] Copying source files to /opt/security-updater...
[4/6] Installing Python dependencies...
[5/6] Setting up configuration...
  → Created /etc/security-updater/config.env — edit SERVER_NAME and ENVIRONMENT!
  → Logs    : /var/log/security-updates
  → Reports : /var/reports/security-updates
[6/6] Creating systemd services and timers...

==========================================
 Installation complete!
==========================================
```

### 3. Edit the configuration

```bash
sudo nano /etc/security-updater/config.env
```

```bash
LOG_DIR=/var/log/security-updates
REPORT_DIR=/var/reports/security-updates
SERVER_NAME=EC2-Production-Server    # ← change this
ENVIRONMENT=production               # ← or staging, dev
```

### 4. Verify

```bash
# Check timers are active
systemctl list-timers | grep -E 'security|monthly'

# Run an update immediately to test
sudo systemctl start security-updater.service

# Check it ran correctly
journalctl -u security-updater.service -n 30
ls /var/log/security-updates/
```

---

## Deploying to Multiple Servers

### With Ansible

```yaml
# playbook.yml
- hosts: ec2_servers
  become: yes
  tasks:
    - name: Copy project
      copy:
        src: /home/oslan/cron_security/
        dest: /tmp/cron_security/

    - name: Install
      shell: bash /tmp/cron_security/scripts/install.sh

    - name: Set server name
      lineinfile:
        path: /etc/security-updater/config.env
        regexp: '^SERVER_NAME='
        line: "SERVER_NAME={{ inventory_hostname }}"
```

```bash
ansible-playbook -i inventory.ini playbook.yml
```

### With a Shell Loop

```bash
SERVERS=("user@ec2-1.example.com" "user@ec2-2.example.com")

for server in "${SERVERS[@]}"; do
    scp -r ./cron_security "$server:/tmp/"
    ssh "$server" "sudo bash /tmp/cron_security/scripts/install.sh"
    echo "✓ $server done"
done
```

---

## Changing the Schedule

```bash
# Edit the timer
sudo nano /etc/systemd/system/security-updater.timer

# Examples:
# OnCalendar=Sun *-*-* 00:00:00    # Sundays at midnight (default)
# OnCalendar=daily                  # Every day
# OnCalendar=Mon,Thu 02:00:00       # Mon and Thu at 2 AM

# Apply changes
sudo systemctl daemon-reload
sudo systemctl restart security-updater.timer
```

---

## Troubleshooting

### Service fails

```bash
# See full error
journalctl -u security-updater.service -n 50 --no-pager

# Run manually to see output
sudo python3 /opt/security-updater/updater.py /etc/security-updater/config.env

# Reinstall Python deps
cd /opt/security-updater
sudo pip3 install -r requirements.txt --force-reinstall
```

### No logs found for report

```bash
# Check logs exist for the month
ls /var/log/security-updates/security-update_$(date +%Y%m)*.log

# Run report manually for a specific month
sudo python3 /opt/security-updater/report.py /etc/security-updater/config.env 2026 2
```

### `uv` not found after install

```bash
export PATH="$HOME/.local/bin:$PATH"
uv --version
```

---

## Uninstall

```bash
sudo systemctl disable --now security-updater.timer monthly-report.timer
sudo rm /etc/systemd/system/security-updater.{service,timer}
sudo rm /etc/systemd/system/monthly-report.{service,timer}
sudo rm -rf /opt/security-updater /etc/security-updater
sudo systemctl daemon-reload
```
