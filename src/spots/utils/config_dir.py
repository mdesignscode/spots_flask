import os
from pathlib import Path
import sys

def get_config_path() -> Path:
    if sys.platform == "win32":
        return Path(os.getenv("APPDATA", Path.home() / "AppData/Roaming")) / "spots"
    elif sys.platform == "darwin":
        return Path.home() / "Library/Application Support" / "spots"
    else:
        return Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config")) / "spots"

def create_config_dir():
  config_dir = get_config_path()
  config_dir.mkdir(parents=True, exist_ok=True)
