---
date: 2026-10-26
pipeline: Studio (all pipelines / new routes)
status: resolved
---

# New Studio Route Returns 405 Because Two Dev Servers Share Port 5200

## Symptom

After adding the Room Reveal Reel blueprint and rebuilding `dist/`, pressing **Run** in the
Studio showed:

```
Pipeline Error: Run failed (405): Method POST not allowed on /api/room-reveal-reel/run
```

The route existed in the code and `OPTIONS` worked on a fresh instance, so the blueprint was
not the problem.

## Root Cause

Two `api_server.py` processes were listening on port 5200 at the same time:

```
TCP 0.0.0.0:5200  LISTENING  4444    python "UI Control/api_server.py"   (older, 32 modules)
TCP 0.0.0.0:5200  LISTENING  17808   python api_server.py                (newer, 33 modules)
```

Werkzeug's dev server binds with address reuse, so on Windows the second process binds the
same port instead of failing with `address already in use`. Connections are then spread across
both sockets, so a request can land on the older process that does not have the new blueprint.

It surfaces as **405, not 404**, because `UI Control/api_server.py` registers a SPA catch-all
`@app.route("/<path:path>")` that only accepts GET. On a server without the blueprint,
`POST /api/room-reveal-reel/run` matches that GET-only rule and Flask raises Method Not Allowed,
which `handle_method_not_allowed` formats into the message above.

## Diagnosis

- `netstat -ano | grep -E ":5200\s+.*LISTENING"` lists more than one PID.
- `GET /api/health` reports fewer modules than expected (missing the newly added one).
- `OPTIONS /api/<new-pipeline>/run` returns 405 on the stale process, 200 on a fresh one.

## Resolution

1. Identify the older process with
   `Get-CimInstance Win32_Process -Filter "Name='python.exe'"` and compare `CreationDate`.
2. Stop only that PID (`Stop-Process -Id <old_pid> -Force`), keep the newer server running.
3. Confirm a single listener on 5200, then check `/api/health` contains the new module and
   `OPTIONS /api/<new-pipeline>/run` returns 200 with `POST` allowed.
4. Hard refresh the Studio tab (Ctrl+F5) so the current `dist/` bundle is loaded.

No code change was needed. No pipeline run was in flight, so nothing paid was lost.

## Prevention

Before starting `python api_server.py`, run `netstat -ano | grep -E ":5200\s+.*LISTENING"`.
If a listener is already there, reuse it or stop it first — do not start a second server.
