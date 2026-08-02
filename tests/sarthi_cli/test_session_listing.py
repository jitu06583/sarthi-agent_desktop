"""Tests for the shared session-listing helpers (sarthi_cli/session_listing.py)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from sarthi_cli.session_listing import (
    parse_session_listing_args,
    query_session_listing,
)


class TestParseSessionListingArgs:
    def test_plain_listing(self):
        assert parse_session_listing_args("") == (False, False, "", None)

    def test_flags(self):
        assert parse_session_listing_args("all full") == (True, True, "", None)

    def test_target_passthrough(self):
        assert parse_session_listing_args("My Cool Session") == (
            False, False, "My Cool Session", None,
        )

    def test_search_query(self):
        assert parse_session_listing_args("search an94") == (False, False, "", "an94")

    def test_find_alias_multiword(self):
        assert parse_session_listing_args("find winton email") == (
            False, False, "", "winton email",
        )

    def test_all_search(self):
        assert parse_session_listing_args("all search cod") == (True, False, "", "cod")

    def test_search_without_query_is_empty_string(self):
        assert parse_session_listing_args("search") == (False, False, "", "")

    def test_search_word_inside_target_is_not_a_flag(self):
        # Flags/keywords only apply before the first positional word.
        assert parse_session_listing_args("deep search notes") == (
            False, False, "deep search notes", None,
        )


class TestQuerySessionListingSearch:
    @pytest.fixture
    def db(self, tmp_path):
        from sarthi_state import SessionDB
        db = SessionDB(db_path=tmp_path / "state.db")
        db.create_session("sess_an94", "telegram", user_id="1", chat_id="2")
        db.set_session_title("sess_an94", "AN-94 Prestige Barrel Build #2")
        db.create_session("sess_winton", "whatsapp", user_id="1", chat_id="2")
        db.set_session_title("sess_winton", "Winton Email Sheet Update #3")
        db.create_session("sess_untitled", "telegram", user_id="1", chat_id="2")
        yield db
        db.close()

    def _ids(self, db, **kw):
        return [r["id"] for r in query_session_listing(db, **kw)]

    def test_title_substring_match(self, db):
        assert self._ids(db, source="telegram", search_query="prestige") == ["sess_an94"]

    def test_punctuation_normalized_match(self, db):
        # "an94" should match the title "AN-94 ..." via compact matching.
        assert self._ids(db, source="telegram", search_query="an94") == ["sess_an94"]

    def test_id_substring_match_includes_unnamed(self, db):
        assert self._ids(db, source="telegram", search_query="untitled") == ["sess_untitled"]

    def test_source_scoping(self, db):
        assert self._ids(db, source="telegram", search_query="winton") == []
        assert self._ids(db, source="whatsapp", search_query="winton") == ["sess_winton"]

    def test_no_match(self, db):
        assert self._ids(db, source="telegram", search_query="zzz-nope") == []

    def test_like_wildcards_are_literal(self, db):
        assert self._ids(db, source="telegram", search_query="%") == []

    def test_search_matches_compression_root_title(self, tmp_path):
        """Searching an old (compressed-away) title surfaces the live tip."""
        from sarthi_state import SessionDB
        db = SessionDB(db_path=tmp_path / "chain.db")
        db.create_session("root_1", "telegram", user_id="1", chat_id="2")
        db.set_session_title("root_1", "Old Chat")
        db.end_session("root_1", end_reason="compression")
        db.create_session(
            "tip_1", "telegram", user_id="1", chat_id="2", parent_session_id="root_1"
        )
        db.set_session_title("tip_1", "AN-94 Build")
        try:
            for query in ("old chat", "root_1", "an94"):
                rows = query_session_listing(db, source="telegram", search_query=query)
                assert [r["id"] for r in rows] == ["tip_1"], query
        finally:
            db.close()

    def test_plain_listing_still_hides_unnamed(self, db):
        assert self._ids(db, source="telegram") == ["sess_an94"]


def test_sessions_cli_hides_internal_workers_unless_source_is_explicit(tmp_path):
    from sarthi_state import SessionDB

    home = tmp_path / ".sarthi"
    home.mkdir()
    db = SessionDB(db_path=home / "state.db")
    try:
        for session_id, source in (
            ("human-cli", "cli"),
            ("human-acp", "acp"),
            ("hidden-kanban", "kanban"),
            ("hidden-tool", "tool"),
        ):
            db.create_session(session_id=session_id, source=source)
    finally:
        db.close()

    root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["SARTHI_HOME"] = str(home)
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(root), env.get("PYTHONPATH", "")) if part
    )
    command = [
        sys.executable,
        "-m",
        "sarthi_cli.main",
        "sessions",
        "list",
        "--limit",
        "100",
    ]

    default = subprocess.run(
        command,
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert default.returncode == 0, default.stderr
    assert "human-cli" in default.stdout
    assert "human-acp" in default.stdout
    assert "hidden-kanban" not in default.stdout
    assert "hidden-tool" not in default.stdout

    diagnostic = subprocess.run(
        [*command, "--source", "kanban"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert diagnostic.returncode == 0, diagnostic.stderr
    assert "hidden-kanban" in diagnostic.stdout
