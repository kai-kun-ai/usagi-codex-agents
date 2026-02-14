"""vote のテスト。"""

from usagi.vote import Vote, decide_2of3, parse_decision


def test_parse_decision() -> None:
    assert parse_decision("APPROVE") == "approve"
    assert parse_decision("止める") == "block"
    assert parse_decision("うーん") == "abstain"


def test_decide_2of3() -> None:
    assert (
        decide_2of3(
            [
                Vote(voter_id="a", decision="approve"),
                Vote(voter_id="b", decision="approve"),
                Vote(voter_id="c", decision="block"),
            ]
        )
        == "approve"
    )
    assert (
        decide_2of3(
            [
                Vote(voter_id="a", decision="block"),
                Vote(voter_id="b", decision="block"),
                Vote(voter_id="c", decision="approve"),
            ]
        )
        == "block"
    )
    assert (
        decide_2of3(
            [
                Vote(voter_id="a", decision="approve"),
                Vote(voter_id="b", decision="block"),
                Vote(voter_id="c", decision="abstain"),
            ]
        )
        == "tie"
    )
