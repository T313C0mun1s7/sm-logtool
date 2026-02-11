"""Configuration loading for sm-logtool."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Optional

import yaml


class ConfigError(Exception):
    """Raised when the configuration file cannot be parsed."""


_DEFAULT_CONFIG_ENV = "SM_LOGTOOL_CONFIG"
_ROOT_DIR = Path(__file__).resolve().parent.parent
_DEFAULT_CONFIG_PATH = _ROOT_DIR / "config.yaml"


@dataclass(frozen=True)
class AppConfig:
    """In-memory representation of sm-logtool configuration."""

    path: Path
    logs_dir: Optional[Path] = None
    staging_dir: Optional[Path] = None
    default_kind: str = "smtpLog"

    @property
    def exists(self) -> bool:
        """Return ``True`` if the configuration file exists on disk."""

        return self.path.exists()


def default_config_path() -> Path:
    """Return the default config path, honoring ``SM_LOGTOOL_CONFIG``."""

    env_value = os.environ.get(_DEFAULT_CONFIG_ENV)
    if env_value:
        return Path(env_value).expanduser()
    return _DEFAULT_CONFIG_PATH


def load_config(path: Path | None = None) -> AppConfig:
    """Load configuration from ``path`` or the default location."""

    config_path = (path or default_config_path()).expanduser()

    if not config_path.exists():
        return AppConfig(path=config_path)

    try:
        with config_path.open("r", encoding="utf-8") as handle:
            raw: Any = yaml.safe_load(handle) or {}
    except yaml.YAMLError as exc:  # pragma: no cover - parsing errors surfaced
        message = f"Failed to parse YAML config {config_path}: {exc}"
        raise ConfigError(message) from exc
    except OSError as exc:  # pragma: no cover - propagate filesystem errors
        message = f"Failed to read config {config_path}: {exc}"
        raise ConfigError(message) from exc

    if not isinstance(raw, dict):
        expected = type(raw).__name__
        message = (
            f"Expected a mapping at the top level of {config_path}, "
            f"got {expected}."
        )
        raise ConfigError(message)

    logs_dir = _coerce_path(raw.get("logs_dir"))
    staging_dir = _coerce_path(raw.get("staging_dir"))
    default_kind = raw.get("default_kind", "smtpLog")

    if not isinstance(default_kind, str):
        message = "Config key 'default_kind' must be a string"
        raise ConfigError(f"{message} (file: {config_path}).")

    return AppConfig(
        path=config_path,
        logs_dir=logs_dir,
        staging_dir=staging_dir,
        default_kind=default_kind,
    )


def _coerce_path(value: Any) -> Optional[Path]:
    if value is None:
        return None
    if isinstance(value, str):
        return Path(value).expanduser()
    typename = type(value).__name__
    raise ConfigError(
        f"Expected a string path in configuration, got {typename}."
    )
