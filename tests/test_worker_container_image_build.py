from pathlib import Path

import pytest

from usagi.worker_container import _ensure_worker_image


def test_ensure_worker_image_never_raises_when_missing(tmp_path: Path) -> None:
    # docker が無い/触れない環境でもこの分岐は docker を叩く前に落ちるのが理想。
    # ただし現状は docker inspect を呼ぶので、呼べない環境では skip。
    try:
        _ensure_worker_image(
            repo_root=tmp_path,
            image="this-image-should-not-exist",
            image_build="never",
        )
    except FileNotFoundError:
        pytest.skip("docker not available")
    except RuntimeError as e:
        assert "worker image not found" in str(e)
