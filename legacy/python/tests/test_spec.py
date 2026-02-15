"""spec パーサーのテスト。"""

from usagi.spec import parse_spec_markdown


def test_parse_basic_spec() -> None:
    md = """---
project: demo
---

## 目的

なにか作る

## やること

- README.md を作る
- src/main.py を作る

## 制約

- 日本語
"""
    spec = parse_spec_markdown(md)
    assert spec.project == "demo"
    assert spec.objective == "なにか作る"
    assert spec.tasks == ["README.md を作る", "src/main.py を作る"]
    assert spec.constraints == ["日本語"]


def test_parse_no_frontmatter() -> None:
    md = """## 目的

テスト

## やること

- ファイル作成
"""
    spec = parse_spec_markdown(md)
    assert spec.project == "usagi-project"
    assert spec.objective == "テスト"
    assert spec.tasks == ["ファイル作成"]


def test_parse_empty() -> None:
    spec = parse_spec_markdown("")
    assert spec.project == "usagi-project"
    assert spec.tasks == []


def test_parse_context_section() -> None:
    md = """## 背景

これは背景です

## 目的

これは目的です
"""
    spec = parse_spec_markdown(md)
    assert spec.context == "これは背景です"
    assert spec.objective == "これは目的です"
