from usagi.spec import parse_spec_markdown


def test_parse_spec_markdown_sections_and_bullets() -> None:
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
