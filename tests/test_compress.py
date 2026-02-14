"""compress のテスト。"""

from usagi.compress import CompressionConfig, compress_text, summarize_report_to_memory


def test_compress_text_noop() -> None:
    t = "abc"
    assert compress_text(t, CompressionConfig(max_chars=10)) == t


def test_compress_text_truncates() -> None:
    t = "a" * 50
    out = compress_text(t, CompressionConfig(max_chars=20))
    assert len(out) > 0
    assert "compressed" in out


def test_summarize_report_to_memory() -> None:
    report = """
# title

## 目的

AAA

## 依頼内容(抽出)

- t1

## エージェント会話ログ

...

## 実行ログ

- a1
"""
    mem = summarize_report_to_memory(report)
    assert "## 目的" in mem
    assert "## 依頼内容" in mem
    assert "## 実行ログ" in mem
    assert "会話ログ" not in mem
