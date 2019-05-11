from __future__ import annotations

import json
import os
from typing import Any, Mapping, Optional

__all__ = [
    "CONFIG_NAME",
    "CONFIG_DIR",
    "Config",
    "get_config_path",
    "initialize",
    "load",
    "dump",
    "get",
]
CONFIG_NAME = "iamdb.json"
CONFIG_DIR = "iamdb"
Config = Mapping[str, Any]
_dump_kwargs = dict(indent=2, sort_keys=True)


def get_config_path(
    config_dir: str = CONFIG_DIR, config_name: str = CONFIG_NAME
) -> str:
    import click

    return os.path.join(click.get_app_dir(config_dir), config_name)


def initialize(config_path: Optional[str] = None):
    config_path = config_path or get_config_path()
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    if not os.path.exists(config_path):
        dump({}, config_path)


def load(key: Optional[str] = None, config_path: Optional[str] = None) -> Config:
    config_path = config_path or get_config_path()
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    return config.get(key, dict()) if key else config


def dump(data: Config, config_path: Optional[str] = None):
    config_path = config_path or get_config_path()
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, **_dump_kwargs)  # type: ignore


def dumps(data: Config) -> str:
    return json.dumps(data, **_dump_kwargs)  # type: ignore


def get(key: str, *subkeys: str, config_path: Optional[str] = None) -> Any:
    data = load(key, config_path=config_path)
    for subkey in subkeys:
        data = (data or dict()).get(subkey)  # type: ignore
    return data


def set(key: str, data: Config, config_path: Optional[str] = None):
    full_data = load(config_path=config_path)
    return dump(dict(full_data, **{key: data}), config_path=config_path)
