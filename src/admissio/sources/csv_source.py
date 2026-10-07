import csv
from pathlib import Path

from ..config import SourceConfig


def read_csv(cfg: SourceConfig) -> list[dict[str, str]]:
    with Path(cfg.path).open(encoding=cfg.encoding, newline="") as fh:
        return list(csv.DictReader(fh, delimiter=cfg.delimiter))
