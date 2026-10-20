"""桌面设置存储测试（纯 Python，无 Qt 依赖）。"""

from __future__ import annotations

import json

import pytest

from desktop.settings import DEFAULT_SETTINGS, SettingsStore


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("MNEST_DESKTOP_SETTINGS", str(tmp_path / "settings.json"))
    return SettingsStore()


def test_defaults_loaded(store):
    assert store.theme == "darcula"
    assert store.chat["base_url"] == "https://api.deepseek.com"
    assert store.chat["model_id"] == "deepseek-chat"
    assert store.image == {"api_key": "", "base_url": "", "model_id": ""}
    assert store.last_output_dir == ""


def test_roundtrip(store, tmp_path):
    store.chat.update({"api_key": "sk-test", "base_url": "https://api.deepseek.com", "model_id": "deepseek-chat"})
    store.image.update({"api_key": "img-key", "base_url": "https://img.example.com", "model_id": "img-model"})
    store.theme = "light"
    store.last_output_dir = str(tmp_path)
    store.save()

    reloaded = SettingsStore(store.path)
    assert reloaded.chat["api_key"] == "sk-test"
    assert reloaded.image["model_id"] == "img-model"
    assert reloaded.theme == "light"
    assert reloaded.last_output_dir == str(tmp_path)


def test_ready_flags(store):
    assert store.chat_ready() is False
    assert store.image_ready() is False
    store.chat["api_key"] = "sk-test"
    assert store.chat_ready() is True
    assert store.image_ready() is False
    store.image.update({"api_key": "k", "base_url": "https://img.example.com", "model_id": "m"})
    assert store.image_ready() is True


def test_deep_merge_preserves_unknown_keys(tmp_path, monkeypatch):
    """旧版设置文件（api_keys/endpoints/runtime/prompts）深合并后保留但不生效。"""
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps({"api_keys": {"X": "1"}, "runtime": {"timeout": 1.0}, "future_field": {"a": 1}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("MNEST_DESKTOP_SETTINGS", str(path))
    store = SettingsStore()
    assert store.data["future_field"] == {"a": 1}
    assert store.data["api_keys"] == {"X": "1"}
    # 新 schema 默认值仍然在位
    assert store.chat["model_id"] == DEFAULT_SETTINGS["chat"]["model_id"]
    assert "runtime" not in DEFAULT_SETTINGS


def test_corrupt_file_falls_back_to_defaults(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    path.write_text("{不是 JSON", encoding="utf-8")
    monkeypatch.setenv("MNEST_DESKTOP_SETTINGS", str(path))
    store = SettingsStore()
    assert store.theme == "darcula"
    assert store.chat_ready() is False
