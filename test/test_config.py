from __future__ import annotations

from pathlib import Path

import pytest

from sm_logtool import config


def test_load_config_missing_file(tmp_path):
    cfg_path = tmp_path / "config.yaml"

    app_config = config.load_config(cfg_path)

    assert app_config.path == cfg_path
    assert not app_config.exists
    assert app_config.logs_dir is None
    assert app_config.default_kind == "smtp"


def test_load_config_creates_default_config_file(tmp_path, monkeypatch):
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.delenv("SM_LOGTOOL_CONFIG", raising=False)

    app_config = config.load_config()
    expected_path = home_dir / ".config" / "sm-logtool" / "config.yaml"

    assert app_config.path == expected_path
    assert app_config.exists
    assert app_config.logs_dir == Path("/var/lib/smartermail/Logs")
    assert app_config.staging_dir == Path("/var/tmp/sm-logtool/logs")
    assert app_config.default_kind == "smtp"


def test_load_config_creates_env_config_file(tmp_path, monkeypatch):
    cfg_path = tmp_path / "custom" / "config.yaml"
    monkeypatch.setenv("SM_LOGTOOL_CONFIG", str(cfg_path))

    app_config = config.load_config()

    assert app_config.path == cfg_path
    assert app_config.exists
    assert app_config.logs_dir == Path("/var/lib/smartermail/Logs")
    assert app_config.staging_dir == Path("/var/tmp/sm-logtool/logs")
    assert app_config.default_kind == "smtp"


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
    assert app_config.default_kind == "imap"


def test_load_config_rejects_non_mapping(tmp_path):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text("- not a mapping\n", encoding="utf-8")

    with pytest.raises(config.ConfigError):
        config.load_config(cfg_path)
