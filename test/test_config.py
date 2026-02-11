from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

try:
    import pytest
except ModuleNotFoundError:  # pragma: no cover - fallback for unittest
    from test import _pytest_stub as pytest

if importlib.util.find_spec("yaml") is None:
    raise unittest.SkipTest("PyYAML not installed")

from sm_logtool import config


def test_load_config_missing_file(tmp_path):
    cfg_path = tmp_path / "config.yaml"

    app_config = config.load_config(cfg_path)

    assert app_config.path == cfg_path
    assert not app_config.exists
    assert app_config.logs_dir is None
    assert app_config.default_kind == "smtpLog"


def test_load_config_reads_values(tmp_path):
    cfg_path = tmp_path / "config.yaml"
    logs_dir = tmp_path / "logs"
    staging_dir = tmp_path / "staging"
    cfg_path.write_text(
        f"logs_dir: {logs_dir}\n"
        f"staging_dir: {staging_dir}\n"
        "default_kind: imapLog\n",
        encoding="utf-8",
    )

    app_config = config.load_config(cfg_path)

    assert app_config.logs_dir == logs_dir
    assert app_config.staging_dir == staging_dir
    assert app_config.default_kind == "imapLog"


def test_load_config_rejects_non_mapping(tmp_path):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text("- not a mapping\n", encoding="utf-8")

    with pytest.raises(config.ConfigError):
        config.load_config(cfg_path)
