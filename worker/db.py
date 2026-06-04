"""Supabase REST client for the worker (service role).

Thin wrapper around the PostgREST endpoint — we don't pull in supabase-py to
keep the worker's dependency footprint tiny. Service-role key bypasses RLS,
which is exactly what the local worker daemon needs.

Reads env from the repo's .env (loaded by config.py).
"""

from __future__ import annotations
import json
from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.parse import urlencode

import requests

from . import config


def now_iso() -> str:
    """UTC timestamp Postgres accepts for timestamptz columns."""
    return datetime.now(timezone.utc).isoformat()


class SupabaseError(RuntimeError):
    pass


def _headers(prefer: str | None = None) -> dict[str, str]:
    if not config.SUPABASE_URL or not config.SUPABASE_SERVICE_KEY:
        raise SupabaseError("SUPABASE_URL and SUPABASE_SERVICE_KEY required in .env")
    h = {
        "apikey": config.SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {config.SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
    }
    if prefer:
        h["Prefer"] = prefer
    return h


def _url(path: str, params: dict[str, Any] | None = None) -> str:
    base = config.SUPABASE_URL.rstrip("/") + "/rest/v1/" + path.lstrip("/")
    if params:
        base += "?" + urlencode(params)
    return base


def select(table: str, *, columns: str = "*", filters: dict[str, str] | None = None, order: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
    """SELECT from `table`. Filters use PostgREST syntax, e.g. {"slug": "eq.foo"}.

    `order` is PostgREST order syntax, e.g. "created_at.asc".
    """
    params: dict[str, Any] = {"select": columns}
    if filters:
        params.update(filters)
    if order:
        params["order"] = order
    if limit is not None:
        params["limit"] = str(limit)
    r = requests.get(_url(table, params), headers=_headers(), timeout=30)
    if not r.ok:
        raise SupabaseError(f"select {table}: {r.status_code} {r.text[:300]}")
    return r.json()


def insert(table: str, row: dict[str, Any] | Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """INSERT one or many rows; returns the inserted row(s)."""
    body = row if isinstance(row, list) else [row] if isinstance(row, dict) else list(row)
    r = requests.post(_url(table), headers=_headers("return=representation"), data=json.dumps(body), timeout=30)
    if not r.ok:
        raise SupabaseError(f"insert {table}: {r.status_code} {r.text[:300]}")
    return r.json()


def update(table: str, filters: dict[str, str], patch: dict[str, Any]) -> list[dict[str, Any]]:
    """PATCH rows matching `filters`. Filters use PostgREST syntax."""
    r = requests.patch(
        _url(table, filters),
        headers=_headers("return=representation"),
        data=json.dumps(patch),
        timeout=30,
    )
    if not r.ok:
        raise SupabaseError(f"update {table}: {r.status_code} {r.text[:300]}")
    return r.json()


def delete(table: str, filters: dict[str, str]) -> None:
    """DELETE rows matching `filters`."""
    r = requests.delete(_url(table, filters), headers=_headers(), timeout=30)
    if not r.ok:
        raise SupabaseError(f"delete {table}: {r.status_code} {r.text[:300]}")


def claim_job(job: dict[str, Any]) -> dict[str, Any] | None:
    """Atomically claim a queued job: queued -> running, bump attempts.

    The `status=eq.queued` filter is the lock — if another worker (or a prior
    loop iteration) already moved it, the PATCH matches nothing and returns [].
    Returns the claimed row, or None if it was already taken.
    """
    rows = update(
        "jobs",
        {"id": f"eq.{job['id']}", "status": "eq.queued"},
        {
            "status": "running",
            "started_at": now_iso(),
            "attempts": int(job.get("attempts", 0)) + 1,
        },
    )
    return rows[0] if rows else None


def ping() -> bool:
    """Quick reachability check used by `worker/cli.py ping`."""
    r = requests.get(_url(""), headers=_headers(), timeout=10)
    return r.status_code == 200
