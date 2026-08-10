from pathlib import Path
from typing import Any

import yaml

def load_config(filename: str = "models.yaml") -> dict[str, Any]:
    config_path = Path(__file__).with_name(filename)

    with config_path.open(encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)

    if not isinstance(config, dict) or "models" not in config:
        raise ValueError(f"{config_path} must contain a top-level 'models:' list")

    if not isinstance(config["models"], list):
        raise ValueError("'models' must be a YAML list")

    return config