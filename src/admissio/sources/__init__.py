"""Sources turn raw HR exports into NewHire records."""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from ..config import SourceConfig, Unpack
from ..logins import fold
from ..models import NewHire


def unpack_column(record: dict[str, str], spec: Unpack) -> dict[str, str]:
    """'Name: Ana Souza | Badge: 42' in spec.column -> {'Name': 'Ana Souza', 'Badge': '42'}."""
    packed = record.get(spec.column) or ""
    out = dict(record)
    for chunk in packed.split(spec.separator):
        key, sep, value = chunk.partition(spec.kv_separator)
        if sep and key.strip():
            out[key.strip()] = value.strip()
    return out


def _matches(record: dict[str, str], where: dict[str, str]) -> bool:
    return all(fold(record.get(k, "")) == fold(v) for k, v in where.items())


def to_new_hires(records: Iterable[dict], cfg: SourceConfig) -> Iterator[NewHire]:
    fm = cfg.fields
    for raw in records:
        record = {str(k).strip(): "" if v is None else str(v).strip() for k, v in raw.items()}
        if cfg.unpack:
            record = unpack_column(record, cfg.unpack)
        if not _matches(record, cfg.where):
            continue

        def col(name: str | None, record: dict[str, str] = record) -> str:
            return record.get(name, "") if name else ""

        yield NewHire(
            employee_id=col(fm.employee_id),
            full_name=" ".join(col(fm.full_name).split()),
            branch=col(fm.branch),
            department=col(fm.department),
            title=col(fm.title),
            manager=col(fm.manager),
            start_date=col(fm.start_date),
            raw=record,
        )


def load_new_hires(cfg: SourceConfig) -> list[NewHire]:
    if cfg.type == "csv":
        from .csv_source import read_csv

        records = read_csv(cfg)
    else:
        from .rest_source import fetch_records

        records = fetch_records(cfg)
    return list(to_new_hires(records, cfg))
