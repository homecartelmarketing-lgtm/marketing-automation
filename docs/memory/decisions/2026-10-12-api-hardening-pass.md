# Decision: API hardening pass — deny-by-default gate, PIN handling, max_items ceiling (2026-10-12)

Same-day follow-up to [[2026-10-12-studio-email-password-login]] (also updated
that note's stale "no block-by-default hook" paragraph). Implemented uncommitted
on `fix/house-tour-moodboard-errors`; full finding→status map lives in the
`docs/SECURITY_AUDIT.md` addendum of the same date.

## Choices and why

- **Kept the 1..10 clamp, deleted `MAX_RUN_ITEMS=4` instead of migrating to it.**
  ~31 `/run` + `/enqueue` call sites already clamped inline to 1..10 and the
  queue's own historical limit was 10. Migrating everything to 4 would have been
  a behavior change (smaller paid runs) disguised as a security fix. One ceiling
  now: `MAX_RUN_ITEMS = 10` in `UI Control/routes/common.py:70`, documented as
  the single source even though routes still inline the literal.
- **Deleted `guard_api()` / `enforce_request_limits()` rather than wiring them.**
  Both were dead code superseded by the live `require_api_auth` gate
  (`UI Control/api_server.py:146`) and the 64 MiB `MAX_CONTENT_LENGTH`. Two
  competing gates would have meant two allowlists to keep in sync; the audit
  addendum records which one survived.
- **`?pin=` raises instead of being silently ignored.**
  Silently ignoring a query PIN would look like a wrong-PIN 401 to the caller
  and invite retries; raising (`_forbid_pin_in_query`) tells them the transport
  is forbidden. Query strings leak into access/proxy logs, history, Referer.
- **Empty-string endpoint is NOT a valid SSRF pass.**
  `_is_safe_local_endpoint("")` returns False on purpose; the enqueue call site
  skips empty `stop_endpoint` via `if endpoint and not ...`. The hardening test
  pins this with a comment so nobody "fixes" the validator into accepting "".
- **Stale `MAX_PIN_LENGTH = 512` removed; live value is 256.**
  The duplicate sat above `clamp_pin()` while the real constant (256) sat below
  it. Length-clamp + `hmac.compare_digest` on every PIN path.
- **Open mode stays open on purpose.** No PIN + no accounts → `is_authorized`
  returns True, gate and all, exactly like the old per-route behavior. Pinned by
  `tests/test_studio_auth.py::test_open_mode_when_no_pin_and_no_accounts`.

## Still open (not decisions — just not done)

Queue length cap + `pipeline_type` allowlist; calendar XLSX `read_only`/row cap
(`content_automation/calendar_import.py:17`); cleanup floor 1h vs roadmap 6h;
per-IP-only lockout; `rows.py` direct-auth/cache/table_id/formula gaps. See the
audit addendum table for file:line refs.
