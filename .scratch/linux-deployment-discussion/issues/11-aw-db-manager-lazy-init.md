Status: ready-for-agent

## Parent

None — this is a foundational fix for the Linux deployment PRD (`.scratch/linux-deployment-discussion/linux-deployment-prd.md`).

## What to build

`DatabaseManager` in `lifeprism/repository/database_manager.py` currently initializes its connection pool eagerly in `__init__` for all modes, including readonly. This means `aw_db_manager` (created at module-import time in `lifeprism/repository/__init__.py`) immediately opens a readonly SQLite connection to the ActivityWatch database file. On Linux, that file does not exist at the default Windows path (`~/AppData/Local/activitywatch/...`), causing `sqlite3.OperationalError: unable to open database file` and crashing the application on import — before any lifespan code runs.

The fix: make readonly `DatabaseManager` instances lazy — defer connection-pool creation from `__init__` to the first `get_connection()` call. Non-readonly managers (`lw_db_manager`) keep their existing eager behavior (they have an empty-file guard and must be ready immediately).

This means:
- `import lifeprism.repository` succeeds on Linux even when the AW database file is absent.
- No spurious empty `.db` files are created on Linux (the old touch-the-file workaround is unnecessary with lazy init).
- When `monitor_type == "lifeprism"` (the default), the AW database is never queried, so no error ever surfaces.
- If someone explicitly configures `monitor_type == "activitywatch"` on Linux without an AW database, the error surfaces at first query (a clear, expected configuration error) rather than at import.

## Acceptance criteria

- [ ] `DatabaseManager.__init__` does NOT call `_init_connection_pool()` when `readonly=True`. Pool initialization moves to first `get_connection()` / `_get_pooled_connection()` call.
- [ ] Non-readonly `DatabaseManager` (e.g. `lw_db_manager`) keeps eager pool init — no behavior change.
- [ ] On a system where the AW database file does not exist, `import lifeprism.repository` completes without raising.
- [ ] Unit test: a readonly `DatabaseManager` with a non-existent DB path does not raise on construction, only on first `get_connection()`.
- [ ] Unit test: a non-readonly `DatabaseManager` still initializes the pool eagerly (regression guard).
- [ ] Existing repository tests pass with no regressions.

## Blocked by

None — can start immediately.
