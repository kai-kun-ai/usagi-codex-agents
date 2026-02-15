"""mailbox protocol tests."""

from pathlib import Path

from usagi.mailbox import archive_message, deliver_markdown, ensure_mailbox, list_inbox


def test_ensure_mailbox_creates_dirs(tmp_path: Path) -> None:
    mb = ensure_mailbox(tmp_path, "boss")
    assert mb.inbox.exists()
    assert mb.outbox.exists()
    assert mb.notes.exists()
    assert mb.archive.exists()


def test_deliver_markdown_to_inbox_and_archive(tmp_path: Path) -> None:
    root = tmp_path

    p = deliver_markdown(
        root=root,
        from_agent="boss",
        to_agent="lead",
        title="hello",
        body="world",
    )
    assert p.exists()
    assert p.parent.name == "inbox"

    items = list_inbox(root=root, agent_id="lead")
    assert items == [p]

    archived = archive_message(root=root, agent_id="lead", message_path=p)
    assert archived.exists()
    assert not p.exists()
    assert archived.parent.name == "archive"
