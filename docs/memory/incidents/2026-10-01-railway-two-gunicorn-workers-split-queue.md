# Railway Studio: run stuck at "Initializing" / flicker (two gunicorn workers)

**Symptom:** On Railway a run showed "RUNNING (00:00) / Phase 1/5: Initializing" with one log line, while the queue dock said "Queue is idle". Earlier: status flickered while running.

**Root cause:** the Dockerfile ran gunicorn with `--workers 2`. The queue (`queue_manager._ACTIVE_JOB/_PENDING_QUEUE/_JOB_HISTORY`) and each route's `STATE` dict are in memory, so each worker process holds its own copy. Requests (enqueue, the queue's internal dispatch/poll over 127.0.0.1, UI polls) landed on random workers. Proof: repeated GETs of `/api/queue/status` alternated between history length 1 and 0.

**Fix:** `--workers 1 --threads 8`; the Studio UI also drops a "running" state if the queue has been empty for 4 polls (about 6 s).

**Rule:** do not raise `--workers` above 1 unless the queue and pipeline state move out of process memory (Redis/DB). A redeploy or restart still drops an in-flight run.
