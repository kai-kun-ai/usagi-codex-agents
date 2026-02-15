from pathlib import Path

from usagi.runtime import load_runtime


def test_runtime_load_worker_pool_size(tmp_path: Path) -> None:
    p = tmp_path / "usagi.runtime.toml"
    p.write_text(
        """
[system]
worker_pool_size = 7
""",
        encoding="utf-8",
    )

    rt = load_runtime(p)
    assert rt.worker_pool_size == 7
