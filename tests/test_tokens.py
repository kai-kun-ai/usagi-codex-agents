"""tokens モジュールのテスト。"""

import os
from pathlib import Path

from usagi.tokens import load_tokens


def test_load_tokens_from_env_single(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "key1")
    monkeypatch.delenv("USAGI_API_KEYS", raising=False)
    pool = load_tokens(None)
    assert pool.available is True
    assert pool.count == 1
    assert pool.next_key() == "key1"


def test_load_tokens_from_env_multi(monkeypatch) -> None:
    monkeypatch.setenv("USAGI_API_KEYS", "k1, k2,,k3")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    pool = load_tokens(None)
    assert pool.count == 3
    assert pool.next_key() in {"k1", "k2", "k3"}


def test_load_tokens_from_toml_key_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("USAGI_API_KEYS", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    key_file = tmp_path / "key.txt"
    key_file.write_text("kfile", encoding="utf-8")

    cfg = tmp_path / "org.toml"
    cfg.write_text(
        f"""
[tokens]
key_files = ["{key_file.as_posix()}"]
""",
        encoding="utf-8",
    )

    pool = load_tokens(cfg)
    assert pool.count == 1
    assert pool.next_key() == "kfile"


def test_missing_tokens_raises(monkeypatch) -> None:
    monkeypatch.delenv("USAGI_API_KEYS", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    pool = load_tokens(None)
    assert pool.available is False
    try:
        pool.next_key()
        assert False, "should raise"
    except RuntimeError:
        assert True
