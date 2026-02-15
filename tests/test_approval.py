from usagi.approval import assign_default
from usagi.org import default_org


def test_assign_default_picks_hierarchy() -> None:
    org = default_org()
    a = assign_default(org)

    assert a.boss_id == "boss"
    assert a.manager_id in ("dev_mgr", "qa_mgr")

    mgr = org.find(a.manager_id)
    assert mgr is not None
    assert mgr.reports_to == "boss"

    lead = org.find(a.lead_id)
    assert lead is not None
    assert lead.reports_to == a.manager_id

    worker = org.find(a.worker_id)
    assert worker is not None
    assert worker.reports_to == a.lead_id
