Status: ready-for-agent

## Parent

None — this is part of the Linux deployment PRD (`.scratch/linux-deployment-discussion/linux-deployment-prd.md`).

## What to build

`ScheduleService.start()` must check `run_mode` and refuse to register system jobs when `run_mode != "full"`. This is a defense-in-depth guard: even if someone accidentally adds ScheduleService startup to the web_demo or agent_only bootstrap path, the service itself will refuse to run scheduled tasks (which depend on Monitor data and would trigger AW database access or empty-window_events queries).

When `run_mode != "full"`, `start()` should log an info-level message (e.g. "run_mode=web_demo, skipping scheduled task registration") and return early without registering any jobs. The scheduler itself may still start (harmless), but no system jobs are added.

In `full` mode, behavior is unchanged — all system jobs register and execute as before.

## Acceptance criteria

- [ ] `ScheduleService.start()` checks `settings.run_mode` before registering system jobs.
- [ ] When `run_mode != "full"`, no system jobs are registered and an info log is emitted.
- [ ] When `run_mode == "full"`, all system jobs register as before — no behavior change.
- [ ] Unit test: `start()` in `web_demo` mode does not register any jobs.
- [ ] Unit test: `start()` in `full` mode registers jobs as before (regression guard).

## Blocked by

- `.scratch/linux-deployment-discussion/issues/12-run-mode-sync-guard.md` (requires `run_mode` configuration to be in place).
