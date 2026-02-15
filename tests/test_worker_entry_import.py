def test_worker_entry_imports() -> None:
    # workerコンテナ用エントリがimport可能であること
    import usagi.worker_entry  # noqa: F401
