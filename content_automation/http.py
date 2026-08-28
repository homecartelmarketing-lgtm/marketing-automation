from __future__ import annotations

import random
import time
from typing import Any

import requests

from .errors import ProviderError


DEFAULT_TIMEOUT = 60
MAX_RETRIES = 5


def response_error(response: requests.Response, context: str) -> ProviderError:
    detail = response.text[:1000]
    try:
        payload = response.json()
        detail = str(payload)
    except ValueError:
        pass
    return ProviderError(f"{context} failed ({response.status_code}): {detail}")


def _backoff_delay(response: requests.Response | None, attempt: int) -> float:
    """Honour Retry-After when the server sends one, else exponential backoff."""
    capped = min(20.0, 2**attempt)
    retry_after = response.headers.get("Retry-After") if response is not None else None
    if retry_after:
        try:
            capped = float(retry_after)
        except ValueError:
            pass
    return capped + random.random() * 0.25


def request_with_retry(
    session: requests.Session,
    method: str,
    url: str,
    *,
    retry_non_idempotent: bool = False,
    retry_server_errors: bool = True,
    timeout: float = DEFAULT_TIMEOUT,
    **kwargs: Any,
) -> requests.Response:
    """Issue a request, retrying transient failures with backoff.

    GET and HEAD are retried by default. Other methods are only retried when
    ``retry_non_idempotent`` is set, because a repeated write can duplicate
    work the first attempt already did.

    ``retry_server_errors=False`` narrows retries to 429 alone. A 429 means the
    server rejected the request outright, so replaying it is safe; a 5xx or a
    dropped connection may well have applied server-side, so a write that must
    not be duplicated should not replay it.
    """
    retry_writes = method.upper() in {"GET", "HEAD"} or retry_non_idempotent

    for attempt in range(MAX_RETRIES):
        last_attempt = attempt == MAX_RETRIES - 1
        try:
            response = session.request(method, url, timeout=timeout, **kwargs)
        except requests.RequestException as error:
            if retry_writes and retry_server_errors and not last_attempt:
                time.sleep(_backoff_delay(None, attempt))
                continue
            raise ProviderError(f"{method.upper()} {url} failed: {error}") from error

        rejected = response.status_code == 429
        server_error = response.status_code >= 500 and retry_server_errors
        if (rejected or server_error) and retry_writes and not last_attempt:
            time.sleep(_backoff_delay(response, attempt))
            continue
        return response

    raise AssertionError("unreachable")
