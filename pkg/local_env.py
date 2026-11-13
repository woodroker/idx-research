"""Load supported local secrets from pkg/.env without overriding the process env."""
import os
from pathlib import Path


ENV_PATH = Path(__file__).resolve().parent / ".env"
_ALLOWED = {
    "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID", "ALPHAVANTAGE_KEY",
}


def load_local_env():
    try:
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    except OSError:
        return

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name, value = name.strip(), value.strip()
        if name not in _ALLOWED or name in os.environ:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        os.environ[name] = value
