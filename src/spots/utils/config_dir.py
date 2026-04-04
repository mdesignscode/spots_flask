from pathlib import Path
import os

def get_config_path():
    config_dir = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config")) / "spots"
    return config_dir

def create_config_dir():
  config_dir = get_config_path()
  config_dir.mkdir(parents=True, exist_ok=True)
