"""Sarthi Kanban worker runs must not surface as user conversations."""

from __future__ import annotations

import os
import subprocess

import pytest

from sarthi_state import SessionDB


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("SARTHI_HOME", str(tmp_path))
    database = SessionDB(db_path=tmp_path / "state.db")
    yield database
    database.close()


def _make_task(kb):
    return kb.Task(
        id="t_b21733fb",
        title="ship it",
        body=None,
        assignee="worker",
        status="in_progress",
        priority=0,
        created_by=None,
        created_at=0,
        started_at=None,
        completed_at=None,
        workspace_kind="scratch",
        workspace_path=None,
        claim_lock=None,
        claim_expires=None,
        tenant=None,
    )


def _source_map(db: SessionDB) -> dict[str, str]:
    return {
        row[0]: row[1]
        for row in db._conn.execute("SELECT id, source FROM sessions ORDER BY id")
    }


def _seed_session(db: SessionDB, session_id: str, source: str, cwd: str, prompt: str) -> None:
    db.create_session(session_id=session_id, source=source, cwd=cwd)
    db.append_message(session_id=session_id, role="user", content=prompt)


def test_worker_spawn_tags_sarthi_session_source_kanban(monkeypatch, tmp_path):
    """The dispatcher owns the source tag and never leaks the Hermes env name."""
    from sarthi_cli import kanban_db as kb

    root = tmp_path / ".sarthi"
    profile = root / "profiles" / "worker"
    profile.mkdir(parents=True)
    (profile / "config.yaml").write_text("toolsets:\n  - kanban\n", encoding="utf-8")
    (root / "config.yaml").write_text("toolsets:\n  - kanban\n", encoding="utf-8")
    monkeypatch.setenv("SARTHI_HOME", str(root))
    monkeypatch.setenv("HERMES_SESSION_SOURCE", "telegram")
    from gateway.session_context import _VAR_MAP

    for key in _VAR_MAP:
        monkeypatch.setenv(key, f"stale-{key.lower()}")
    detached_flags = {
        "SARTHI_GATEWAY_SESSION",
        "SARTHI_DESKTOP",
        "SARTHI_EXEC_ASK",
        "SARTHI_INTERACTIVE",
        "SARTHI_DESKTOP_TERMINAL",
        "SARTHI_TUI_PASS_SESSION_ID",
    }
    for key in detached_flags:
        monkeypatch.setenv(key, "1")
    monkeypatch.setattr(kb, "_resolve_sarthi_argv", lambda: ["sarthi"])
    monkeypatch.setattr(kb, "_resolve_worker_cli_toolsets", lambda _home: None)
    monkeypatch.setattr(kb, "worker_logs_dir", lambda board=None: tmp_path / "logs")

    captured: dict[str, object] = {}

    class _Proc:
        pid = 4321

    def _fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["env"] = kwargs["env"]
        return _Proc()

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)
    workspace = tmp_path / "ws"
    workspace.mkdir()

    kb._default_spawn(_make_task(kb), str(workspace))

    env = captured["env"]
    assert isinstance(env, dict)
    assert env["SARTHI_SESSION_SOURCE"] == "kanban"
    assert "HERMES_SESSION_SOURCE" not in env
    assert all(key not in env for key in _VAR_MAP if key != "SARTHI_SESSION_SOURCE")
    assert all(key not in env for key in detached_flags)


def test_worker_spawn_does_not_inherit_dispatcher_home_when_profile_resolution_fails(
    monkeypatch, tmp_path
):
    from sarthi_cli import kanban_db as kb
    import sarthi_cli.profiles as profiles

    dispatcher_home = tmp_path / "dispatcher-home"
    dispatcher_home.mkdir()
    monkeypatch.setenv("SARTHI_HOME", str(dispatcher_home))
    monkeypatch.setattr(
        profiles,
        "resolve_profile_env",
        lambda _profile: (_ for _ in ()).throw(FileNotFoundError("missing profile")),
    )
    monkeypatch.setattr(kb, "_resolve_sarthi_argv", lambda: ["sarthi"])
    monkeypatch.setattr(kb, "_resolve_worker_cli_toolsets", lambda _home: None)
    monkeypatch.setattr(kb, "_retag_legacy_worker_sessions", lambda *_args: None)
    monkeypatch.setattr(kb, "worker_logs_dir", lambda board=None: tmp_path / "logs")
    captured = {}

    class _Proc:
        pid = 4321

    def _fake_popen(_cmd, **kwargs):
        captured["env"] = kwargs["env"]
        return _Proc()

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)
    workspace = tmp_path / "ws"
    workspace.mkdir()

    kb._default_spawn(_make_task(kb), str(workspace))

    assert "SARTHI_HOME" not in captured["env"]


def test_retag_reclaims_only_dispatcher_prompt_under_root(db, tmp_path):
    workspaces = tmp_path / "kanban" / "workspaces"
    _seed_session(db, "worker", "cli", str(workspaces / "t_a"), "work kanban task t_a1b2c3d4")
    _seed_session(db, "manual", "cli", str(workspaces / "t_b"), "review this manually")
    _seed_session(db, "outside", "cli", str(tmp_path / "repo"), "work kanban task t_c1b2c3d4")
    _seed_session(db, "desktop", "desktop", str(workspaces / "t_d"), "work kanban task t_d1b2c3d4")

    assert db.retag_kanban_worker_sessions(str(workspaces)) == 1
    assert _source_map(db) == {
        "desktop": "desktop",
        "manual": "cli",
        "outside": "cli",
        "worker": "kanban",
    }


@pytest.mark.parametrize(
    ("root", "child"),
    [
        ("/tmp/board_%/workspaces", "/tmp/board_%/workspaces/t_a"),
        (r"C:\Boards\board_%\workspaces", r"C:\Boards\board_%\workspaces\t_a"),
    ],
)
def test_retag_supports_posix_and_windows_separators_without_like_wildcards(db, root, child):
    _seed_session(db, "worker", "cli", child, "work kanban task t_a1b2c3d4")
    _seed_session(db, "sibling", "cli", root + "-other/t_b", "work kanban task t_b1c2d3e4")

    assert db.retag_kanban_worker_sessions(root) == 1
    assert _source_map(db) == {"sibling": "cli", "worker": "kanban"}


@pytest.mark.skipif(os.name != "nt", reason="Windows path comparison contract")
def test_retag_normalizes_windows_case_and_mixed_separators(db):
    _seed_session(
        db,
        "worker",
        "cli",
        r"C:/BOARDS/WORKSPACES/task-a",
        "work kanban task t_b1c2d3e4",
    )

    assert db.retag_kanban_worker_sessions(r"c:\boards\workspaces") == 1
    assert _source_map(db)["worker"] == "kanban"


def test_retag_is_idempotent_and_reclaims_rows_restored_later(db, tmp_path):
    workspaces = tmp_path / "kanban" / "workspaces"
    _seed_session(db, "legacy", "cli", str(workspaces / "t_a"), "work kanban task t_a1b2c3d4")
    assert db.retag_kanban_worker_sessions(str(workspaces)) == 1

    _seed_session(db, "later", "cli", str(workspaces / "t_b"), "work kanban task t_b1c2d3e4")
    assert db.retag_kanban_worker_sessions(str(workspaces)) == 1
    assert _source_map(db)["later"] == "kanban"


def test_retag_is_scoped_per_board(db, tmp_path):
    board_a = tmp_path / "kanban" / "boards" / "a" / "workspaces"
    board_b = tmp_path / "kanban" / "boards" / "b" / "workspaces"
    _seed_session(db, "a1", "cli", str(board_a / "t_a"), "work kanban task t_a1b2c3d4")
    _seed_session(db, "b1", "cli", str(board_b / "t_b"), "work kanban task t_b1c2d3e4")

    assert db.retag_kanban_worker_sessions(str(board_a)) == 1
    assert db.retag_kanban_worker_sessions(str(board_b)) == 1
    assert _source_map(db) == {"a1": "kanban", "b1": "kanban"}


def test_dispatcher_retags_each_assignee_profile_database_and_restored_rows(
    tmp_path,
):
    from sarthi_cli import kanban_db as kb

    workspaces = tmp_path / "kanban" / "workspaces"
    profile_a = tmp_path / "profiles" / "a"
    profile_b = tmp_path / "profiles" / "b"
    profile_a.mkdir(parents=True)
    profile_b.mkdir(parents=True)

    for profile, session_id, task_id in (
        (profile_a, "a-worker", "t_a1b2c3d4"),
        (profile_b, "b-worker", "t_b1c2d3e4"),
    ):
        profile_db = SessionDB(db_path=profile / "state.db")
        try:
            _seed_session(
                profile_db,
                session_id,
                "cli",
                str(workspaces / task_id),
                f"work kanban task {task_id}",
            )
        finally:
            profile_db.close()

    kb._retag_legacy_worker_sessions(str(workspaces), str(profile_a))
    kb._retag_legacy_worker_sessions(str(workspaces), str(profile_b))

    profile_db = SessionDB(db_path=profile_a / "state.db")
    try:
        _seed_session(
            profile_db,
            "a-restored",
            "cli",
            str(workspaces / "t_c1d2e3f4"),
            "work kanban task t_c1d2e3f4",
        )
    finally:
        profile_db.close()
    kb._retag_legacy_worker_sessions(str(workspaces), str(profile_a))

    for profile, session_id in (
        (profile_a, "a-worker"),
        (profile_a, "a-restored"),
        (profile_b, "b-worker"),
    ):
        profile_db = SessionDB(db_path=profile / "state.db")
        try:
            assert _source_map(profile_db)[session_id] == "kanban"
        finally:
            profile_db.close()


def test_retag_requires_exact_first_dispatcher_prompt(db, tmp_path):
    workspaces = tmp_path / "kanban" / "workspaces"
    _seed_session(
        db,
        "suffix",
        "cli",
        str(workspaces / "suffix"),
        "work kanban task t_a1b2c3d4 -- explain this",
    )
    _seed_session(db, "later", "cli", str(workspaces / "later"), "hello")
    db.append_message("later", "user", "work kanban task t_b1c2d3e4")
    _seed_session(
        db,
        "bad-id",
        "cli",
        str(workspaces / "bad-id"),
        "work kanban task t_manual",
    )

    assert db.retag_kanban_worker_sessions(str(workspaces)) == 0
    assert set(_source_map(db).values()) == {"cli"}


def test_retag_paginates_past_other_boards(db, tmp_path):
    board_a = tmp_path / "kanban" / "boards" / "a" / "workspaces"
    board_b = tmp_path / "kanban" / "boards" / "b" / "workspaces"
    session_rows = []
    message_rows = []
    for index in range(5001):
        task_id = f"t_{index:08x}"
        session_id = f"b-{index:04d}"
        session_rows.append((session_id, "cli", float(index), str(board_b / task_id)))
        message_rows.append((session_id, "user", f"work kanban task {task_id}", float(index)))

    def _bulk_seed(conn):
        conn.executemany(
            "INSERT INTO sessions (id, source, started_at, cwd) VALUES (?, ?, ?, ?)",
            session_rows,
        )
        conn.executemany(
            "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            message_rows,
        )

    db._execute_write(_bulk_seed)
    _seed_session(
        db,
        "z-target",
        "cli",
        str(board_a / "t_a1b2c3d4"),
        "work kanban task t_a1b2c3d4",
    )

    assert db.retag_kanban_worker_sessions(str(board_a)) == 1
    assert _source_map(db)["z-target"] == "kanban"


def test_dispatch_tick_retags_legacy_rows_without_spawning(tmp_path, monkeypatch):
    from sarthi_cli import kanban_db as kb
    from sarthi_cli import profiles

    kanban_home = tmp_path / "kanban-home"
    profile_home = tmp_path / "profiles" / "alice"
    profile_home.mkdir(parents=True)
    monkeypatch.setenv("SARTHI_KANBAN_HOME", str(kanban_home))
    monkeypatch.setattr(
        profiles,
        "resolve_profile_env",
        lambda name: str(profile_home) if name == "alice" else "",
    )

    workspaces = kb.workspaces_root()
    workspaces.mkdir(parents=True, exist_ok=True)
    profile_db = SessionDB(db_path=profile_home / "state.db")
    try:
        _seed_session(
            profile_db,
            "legacy-no-spawn",
            "cli",
            str(workspaces / "t_a1b2c3d4"),
            "work kanban task t_a1b2c3d4",
        )
    finally:
        profile_db.close()

    with kb.connect() as conn:
        task_id = kb.create_task(conn, title="already done", assignee="alice")
        conn.execute("UPDATE tasks SET status = 'done' WHERE id = ?", (task_id,))
        result = kb.dispatch_once(conn, spawn_fn=lambda *_args, **_kwargs: None)
        assert result.spawned == []

    profile_db = SessionDB(db_path=profile_home / "state.db")
    try:
        assert _source_map(profile_db)["legacy-no-spawn"] == "kanban"
    finally:
        profile_db.close()
