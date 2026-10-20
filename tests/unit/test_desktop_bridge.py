"""桌面 Bridge 测试：极简设置 → promo 管线注入（需 PySide6）。"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from desktop.bridge import Bridge  # noqa: E402
from desktop.settings import CHAT_KEY_ENV, IMAGE_KEY_ENV, SettingsStore  # noqa: E402


@pytest.fixture()
def store(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    monkeypatch.setenv("MNEST_DESKTOP_SETTINGS", str(path))
    monkeypatch.delenv(CHAT_KEY_ENV, raising=False)
    monkeypatch.delenv(IMAGE_KEY_ENV, raising=False)
    return SettingsStore()


def test_chat_fn_none_without_key(store):
    bridge = Bridge(store)
    logs: list[tuple[str, str]] = []
    assert bridge.chat_fn(lambda level, message: logs.append((level, message))) is None
    assert any(level == "warn" for level, _ in logs)


def test_chat_fn_built_with_key(store):
    import os

    store.chat.update({"api_key": "sk-ui", "base_url": "https://api.deepseek.com", "model_id": "deepseek-chat"})
    store.save()
    bridge = Bridge(store)
    fn = bridge.chat_fn()
    assert callable(fn)
    assert os.environ[CHAT_KEY_ENV] == "sk-ui"


def test_image_fn_none_without_config(store):
    bridge = Bridge(store)
    assert bridge.image_fn() is None


def test_generate_promo_injects_callbacks(store, tmp_path, monkeypatch):
    """chat_fn 返回 None 时管线自动降级；参数正确透传。"""
    captured: dict = {}

    def fake_run_promo(output_dir, doc_paths, **kwargs):
        captured["output_dir"] = str(output_dir)
        captured["doc_paths"] = [str(p) for p in doc_paths]
        captured.update(kwargs)
        return {"video": str(tmp_path / "promo.mp4"), "duration_s": 30.0, "frames": 900, "shots": 7}

    import motionnest.promo as promo_module

    monkeypatch.setattr(promo_module, "run_promo", fake_run_promo)

    bridge = Bridge(store)
    logger = lambda level, message: None  # noqa: E731
    result = bridge.generate_promo(
        logger,
        doc_paths=["a.md", "b.csv"],
        asset_dir=str(tmp_path),
        note="突出续航",
        quality="final",
    )
    assert captured["doc_paths"] == ["a.md", "b.csv"]
    assert captured["asset_dir"] == str(tmp_path)
    assert captured["note"] == "突出续航"
    assert captured["quality"] == "final"
    assert captured["chat_fn"] is None  # 无密钥 → 降级模板
    assert result["video"].endswith("promo.mp4")
    assert store.last_output_dir == captured["output_dir"]


def test_open_path_missing_file_raises(store, tmp_path):
    bridge = Bridge(store)
    with pytest.raises(FileNotFoundError):
        bridge.open_path(str(tmp_path / "nope.mp4"))
