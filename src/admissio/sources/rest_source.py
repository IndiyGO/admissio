from __future__ import annotations

import httpx

from ..config import SourceConfig


def dig(data, path: str):
    """Follow a dotted path ('data.items') into nested JSON."""
    for key in filter(None, path.split(".")):
        data = data[int(key)] if isinstance(data, list) else data[key]
    return data


def fetch_records(cfg: SourceConfig, client: httpx.Client | None = None) -> list[dict]:
    if client is None:
        with httpx.Client(timeout=cfg.timeout) as owned:
            return fetch_records(cfg, owned)
    response = client.request(cfg.method, cfg.url, headers=cfg.headers, params=cfg.params, json=cfg.body)
    response.raise_for_status()
    records = dig(response.json(), cfg.records_path)
    if not isinstance(records, list):
        raise ValueError(f"records_path {cfg.records_path!r} did not point to a list")
    return records
