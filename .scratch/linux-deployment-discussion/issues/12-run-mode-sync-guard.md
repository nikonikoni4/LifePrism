Status: ready-for-agent

## Parent

None — this is part of the Linux deployment PRD (`.scratch/linux-deployment-discussion/linux-deployment-prd.md`).

## What to build

Introduce a `run_mode` configuration that distinguishes the three deployment entry points: `full` (Windows desktop, default), `web_demo` (Linux Web Demo), and `agent_only` (Linux Agent Only). The mode is read from the `LIFEPRISM_RUN_MODE` environment variable with a fallback default of `"full"`.

When `run_mode != "full"`, both sync channels in `SyncService` — incremental sync (`incremental_sync()`) and time-range sync (`sync_by_time_range()`) — must immediately raise an `LWBaseError` with error code `DEMO_MODE_NOT_SUPPORTED` (HTTP 422). The API layer's global exception handler will convert this to a 422 JSON response. The frontend, on receiving this error from the `POST /api/v2/sync/activitywatch` endpoint, must display a toast notification informing the user that data sync is unavailable in demo mode.

The two Linux startup scripts (`scripts/deployment/start_web_demo.sh` and `scripts/deployment/start_agent_only.sh`) must export the appropriate `LIFEPRISM_RUN_MODE` environment variable before launching the Python process.

This is a vertical slice: settings → service guard → API error response → frontend toast → startup scripts → tests.

## Acceptance criteria

- [ ] `settings_manager.py` DEFAULTS includes `"run_mode": "full"`; a `run_mode` property reads from config, falling back to the `LIFEPRISM_RUN_MODE` env var.
- [ ] `SyncService.incremental_sync()` raises `LWBaseError` (code `DEMO_MODE_NOT_SUPPORTED`, HTTP 422) when `run_mode != "full"`.
- [ ] `SyncService.sync_by_time_range()` raises the same error when `run_mode != "full"`.
- [ ] `POST /api/v2/sync/activitywatch` returns HTTP 422 with a JSON body containing `error_code: "DEMO_MODE_NOT_SUPPORTED"` and a human-readable message when `run_mode` is not `full`.
- [ ] In `full` mode, both sync methods work exactly as before — no behavior change.
- [ ] Frontend displays a toast notification when the sync API returns the `DEMO_MODE_NOT_SUPPORTED` error.
- [ ] `scripts/deployment/start_web_demo.sh` exports `LIFEPRISM_RUN_MODE=web_demo` before launching.
- [ ] `scripts/deployment/start_agent_only.sh` exports `LIFEPRISM_RUN_MODE=agent_only` before launching.
- [ ] Unit tests cover: run_mode property reads env var; both SyncService methods raise in non-full mode; both work in full mode.

## Blocked by

None — can start immediately. (Independent of issue #11, but both are prerequisites for the Linux deployment to function.)
