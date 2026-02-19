"""
config.py - Centralized configuration loader
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv


@dataclass
class Config:
    log_dir: str
    report_dir: str
    server_name: str
    environment: str
    telegram_bot_token: str
    telegram_chat_id: str


def load_config(config_file: str = "/etc/security-updater/config.env") -> Config:
    """Load configuration from env file, falling back to environment variables."""
    if os.path.exists(config_file):
        load_dotenv(config_file, override=True)
    else:
        load_dotenv()

    return Config(
        log_dir=os.getenv("LOG_DIR", "/home/oslan/cron_security/logs"),
        report_dir=os.getenv("REPORT_DIR", "/home/oslan/cron_security/reports"),
        server_name=os.getenv("SERVER_NAME", "EC2-Server"),
        environment=os.getenv("ENVIRONMENT", "production"),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
    )
