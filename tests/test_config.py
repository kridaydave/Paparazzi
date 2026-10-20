import os
from pathlib import Path

from paparazzi import config


def test_openrouter_key_unset(monkeypatch):
    monkeypatch.delenv("PAPARAZZI_OPENROUTER_KEY", raising=False)
    assert config.openrouter_key() is None


def test_openrouter_key_set(monkeypatch):
    monkeypatch.setenv("PAPARAZZI_OPENROUTER_KEY", "sk-test")
    assert config.openrouter_key() == "sk-test"


def test_openrouter_key_empty_is_none(monkeypatch):
    monkeypatch.setenv("PAPARAZZI_OPENROUTER_KEY", "")
    assert config.openrouter_key() is None


def test_db_path_default(monkeypatch):
    monkeypatch.delenv("PAPARAZZI_DB", raising=False)
    from paparazzi.db import DEFAULT_DB

    assert config.db_path() == DEFAULT_DB


def test_db_path_env(monkeypatch, tmp_path):
    target = tmp_path / "custom.db"
    monkeypatch.setenv("PAPARAZZI_DB", str(target))
    assert config.db_path() == target


def test_db_path_changes_after_import(monkeypatch, tmp_path):
    monkeypatch.delenv("PAPARAZZI_DB", raising=False)
    first = config.db_path()
    target = tmp_path / "later.db"
    monkeypatch.setenv("PAPARAZZI_DB", str(target))
    assert config.db_path() == target
    assert config.db_path() != first


def test_mock_true_values(monkeypatch):
    for value in ("1", "true", "True", "TRUE", "yes", "YES", "on", "On", "  true  "):
        monkeypatch.setenv("PAPARAZZI_MOCK", value)
        assert config.mock() is True, value


def test_mock_false_values(monkeypatch):
    for value in ("0", "false", "no", "off", "", "maybe"):
        monkeypatch.setenv("PAPARAZZI_MOCK", value)
        assert config.mock() is False, value


def test_mock_unset(monkeypatch):
    monkeypatch.delenv("PAPARAZZI_MOCK", raising=False)
    assert config.mock() is False


def test_mock_changes_after_import(monkeypatch):
    monkeypatch.setenv("PAPARAZZI_MOCK", "0")
    assert config.mock() is False
    monkeypatch.setenv("PAPARAZZI_MOCK", "1")
    assert config.mock() is True