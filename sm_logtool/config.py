"""Configuration loading for sm-logtool."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Optional

import yaml

from .log_kinds import KIND_SMTP, normalize_kind


class ConfigError(Exception):
    """Raised when the configuration file cannot be parsed."""


_DEFAULT_CONFIG_ENV = "SM_LOGTOOL_CONFIG"
DEFAULT_LOGS_DIR = Path("/var/lib/smartermail/Logs")
DEFAULT_STAGING_DIR = Path("/var/tmp/sm-logtool/logs")
DEFAULT_KIND = KIND_SMTP
DEFAULT_THEME = "Cyberdark"


@dataclass(frozen=True)
class AppConfig:
    """In-memory representation of sm-logtool configuration."""

    path: Path
    logs_dir: Optional[Path] = None
    staging_dir: Optional[Path] = None
    default_kind: str = KIND_SMTP
    theme: Optional[str] = None

    @property
    def exists(self) -> bool:
        """Return ``True`` if the configuration file exists on disk."""

        return self.path.exists()


def default_config_path() -> Path:
    """Return the default config path, honoring ``SM_LOGTOOL_CONFIG``."""

    env_value = os.environ.get(_DEFAULT_CONFIG_ENV)
    if env_value:
        return Path(env_value).expanduser()
    return Path.home() / ".config" / "sm-logtool" / "config.yaml"


def load_config(path: Path | None = None) -> AppConfig:
    """Load configuration from ``path`` or the default location.

    When ``path`` is omitted, a default config file is created if missing.
    """

    config_path = (path or default_config_path()).expanduser()
    if path is None:
        _ensure_default_config_file(config_path)

    if not config_path.exists():
        return AppConfig(path=config_path)

    raw = _load_config_mapping(config_path)

    logs_dir = _coerce_path(raw.get("logs_dir"))
    staging_dir = _coerce_path(raw.get("staging_dir"))
    default_kind = raw.get("default_kind", DEFAULT_KIND)
    theme = raw.get("theme")

    if not isinstance(default_kind, str):
        message = "Config key 'default_kind' must be a string"
        raise ConfigError(f"{message} (file: {config_path}).")
    default_kind = normalize_kind(default_kind)
    if theme is not None and not isinstance(theme, str):
        message = "Config key 'theme' must be a string"
        raise ConfigError(f"{message} (file: {config_path}).")

    return AppConfig(
        path=config_path,
        logs_dir=logs_dir,
        staging_dir=staging_dir,
        default_kind=default_kind,
        theme=theme,
    )


def save_theme(path: Path, theme: str) -> None:
    """Persist ``theme`` in a YAML config file at ``path``."""

    if not isinstance(theme, str) or not theme:
        raise ConfigError("Theme value must be a non-empty string.")

    config_path = path.expanduser()
    payload: dict[str, Any]
    if config_path.exists():
        payload = _load_config_mapping(config_path)
    else:
        payload = {}
    payload["theme"] = theme

    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with config_path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(payload, handle, sort_keys=False)
    except OSError as exc:
        message = f"Failed to write config {config_path}: {exc}"
        raise ConfigError(message) from exc


def _ensure_default_config_file(config_path: Path) -> None:
    if config_path.exists():
        return
    payload = {
        "logs_dir": str(DEFAULT_LOGS_DIR),
        "staging_dir": str(DEFAULT_STAGING_DIR),
        "default_kind": DEFAULT_KIND,
        "theme": DEFAULT_THEME,
    }
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with config_path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(payload, handle, sort_keys=False)
    except OSError as exc:
        message = f"Failed to create default config {config_path}: {exc}"
        raise ConfigError(message) from exc


def _coerce_path(value: Any) -> Optional[Path]:
    if value is None:
        return None
    if isinstance(value, str):
        return Path(value).expanduser()
    typename = type(value).__name__
    raise ConfigError(
        f"Expected a string path in configuration, got {typename}."
    )


def _load_config_mapping(config_path: Path) -> dict[str, Any]:
    try:
        with config_path.open("r", encoding="utf-8") as handle:
            raw: Any = yaml.safe_load(handle) or {}
    except yaml.YAMLError as exc:  # pragma: no cover - parsing errors surfaced
        message = f"Failed to parse YAML config {config_path}: {exc}"
        raise ConfigError(message) from exc
    except OSError as exc:  # pragma: no cover - propagate filesystem errors
        message = f"Failed to read config {config_path}: {exc}"
        raise ConfigError(message) from exc

    if isinstance(raw, dict):
        return raw

    expected = type(raw).__name__
    message = (
        f"Expected a mapping at the top level of {config_path}, "
        f"got {expected}."
    )
    raise ConfigError(message)
