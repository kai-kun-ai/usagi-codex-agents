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
