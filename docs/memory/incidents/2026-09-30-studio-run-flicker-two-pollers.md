# Studio flickers while a content run is active

**Symptom:** Log panel and run status blinked during runs; spurious "pipeline finished" toasts; phase label jumped.

**Root cause (from code reading, not reproduced in a browser):** two pollers wrote the same `pipelineState` every 1.5 s: `useQueue` (`/api/queue/status`) and `usePipelineRunner` (the pipeline's own status endpoint). A route can still report the previous run's `completed`/`idle` status before the queue dispatches the new run, so the runner marked the run finished, the log viewer unmounted, then the queue tick remounted it. `useQueue` also re-set identical state every tick, and the sketch route's keyword-based phase detection could move the phase backwards.

**Fix:** the queue is now the only driver of run status. `usePipelineRunner` no longer polls; `useQueue` dedupes identical polls and reports finished jobs (with history status/error) to `App.handleQueueJobTransition`, which shows the toasts and refreshes counts once. Phase index is monotonic (queue view + `[PHASE N]` markers in the sketch route). Log panel only auto-scrolls when the user is at the bottom.

**Not done:** `React.memo` on `FixtureCard` was skipped because most callbacks passed from `App` are inline and would defeat it.
