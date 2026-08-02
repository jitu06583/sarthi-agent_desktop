import asyncio

from sarthi_cli import web_server
from sarthi_state import SessionDB


class _FakeSessionDB:
    """Fake backing the /api/sessions/search endpoint.

    The endpoint surfaces direct session-id matches first, then FTS message
    matches, deduping both by compression lineage root. This fake has no
    compression chains (get_session returns no parent), so each session is its
    own lineage root.
    """

    closed = False

    def search_sessions_by_id(
        self,
        query,
        limit=20,
        include_archived=True,
        source=None,
        exclude_sources=None,
    ):
        assert query == "20260603"
        assert include_archived is True
        assert source is None
        assert set(exclude_sources) == {"kanban", "tool"}
        return [
            {
                "id": "20260603_090200_exact",
                "preview": "ID match preview",
                "source": "cli",
                "model": "claude",
                "started_at": 100,
            }
        ]

    def search_messages(
        self,
        query,
        source_filter=None,
        exclude_sources=None,
        limit=20,
    ):
        assert query == "20260603*"
        assert source_filter is None
        assert set(exclude_sources) == {"kanban", "tool"}
        return [
            {
                "session_id": "hidden_worker_content",
                "snippet": "worker content",
                "role": "user",
                "source": "kanban",
                "model": "worker-model",
                "session_started": 300,
            },
            {
                "session_id": "20260603_090200_exact",
                "snippet": "duplicate content hit should not replace ID hit",
                "role": "user",
                "source": "cli",
                "model": "claude",
                "session_started": 100,
            },
            {
                "session_id": "content_session",
                "snippet": "content hit",
                "role": "assistant",
                "source": "desktop",
                "model": "gpt",
                "session_started": 200,
            },
        ]

    def get_session(self, session_id):
        # No compression chains in this fixture — every session is its own root.
        return {"id": session_id, "parent_session_id": None}

    def get_compression_tip(self, session_id):
        return session_id

    def close(self):
        self.closed = True


def test_desktop_session_search_merges_id_matches_before_content_matches(monkeypatch):
    monkeypatch.setattr("sarthi_state.SessionDB", _FakeSessionDB)

    response = asyncio.run(web_server.search_sessions(q="20260603", limit=2))

    # ID match surfaces first; the content hit on the SAME session is deduped
    # by lineage root (not double-listed); the unrelated content hit follows.
    assert response == {
        "results": [
            {
                "session_id": "20260603_090200_exact",
                "lineage_root": "20260603_090200_exact",
                "snippet": "ID match preview",
                "role": None,
                "source": "cli",
                "model": "claude",
                "session_started": 100,
            },
            {
                "session_id": "content_session",
                "lineage_root": "content_session",
                "snippet": "content hit",
                "role": "assistant",
                "source": "desktop",
                "model": "gpt",
                "session_started": 200,
            },
        ]
    }


def test_session_list_defaults_hide_internal_sources_but_explicit_source_does_not():
    assert set(web_server._session_list_exclusions(None, None)) == {
        "kanban",
        "tool",
    }
    assert set(web_server._session_list_exclusions(None, "cron")) == {
        "cron",
        "kanban",
        "tool",
    }
    assert web_server._session_list_exclusions("kanban", None) == []


def test_id_search_filters_internal_sources_before_limit(tmp_path):
    db = SessionDB(db_path=tmp_path / "state.db")
    try:
        db.create_session("match-visible-acp", "acp")
        for index in range(50):
            db.create_session(f"match-hidden-kanban-{index:03d}", "kanban")

        rows = db.search_sessions_by_id(
            "match",
            limit=2,
            include_archived=True,
            exclude_sources=["kanban", "tool"],
        )
        assert [row["id"] for row in rows] == ["match-visible-acp"]
    finally:
        db.close()
