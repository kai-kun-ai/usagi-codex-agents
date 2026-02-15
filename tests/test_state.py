"""state のテスト。"""

from pathlib import Path

from usagi.state import AgentStatus, load_status, save_status


def test_status_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / "status.json"
    st = load_status(p)
    st.set(AgentStatus(agent_id="boss", name="社長うさぎ", state="working", task="x"))
    save_status(p, st)

    st2 = load_status(p)
    assert st2.agents["boss"].state == "working"


def test_load_status_empty_file_falls_back_and_logs(tmp_path: Path) -> None:
    usagi_dir = tmp_path / ".usagi"
    usagi_dir.mkdir()
    status_path = usagi_dir / "status.json"
    status_path.write_text("", encoding="utf-8")

    st = load_status(status_path)
    assert st.agents == {}

    events_path = usagi_dir / "events.log"
    assert events_path.exists()
    assert "status.json is invalid" in events_path.read_text(encoding="utf-8")


def test_load_status_corrupt_json_falls_back_and_logs(tmp_path: Path) -> None:
    usagi_dir = tmp_path / ".usagi"
    usagi_dir.mkdir()
    status_path = usagi_dir / "status.json"
    status_path.write_text("{not json", encoding="utf-8")

    st = load_status(status_path)
    assert st.agents == {}

    events_path = usagi_dir / "events.log"
    assert events_path.exists()
    assert "JSON" in events_path.read_text(encoding="utf-8")
