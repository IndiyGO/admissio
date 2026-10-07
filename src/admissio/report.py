from __future__ import annotations

import csv
import os
from datetime import datetime
from pathlib import Path

from .models import Result

COLUMNS = ["status", "employee_id", "full_name", "login", "email", "ou", "password", "message"]


def write_report(results: list[Result], template: str, include_passwords: bool) -> Path:
    path = Path(template.format(timestamp=datetime.now().strftime("%Y%m%d-%H%M%S")))
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = COLUMNS if include_passwords else [c for c in COLUMNS if c != "password"]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            row = vars(r) | {"status": r.status.value}
            writer.writerow(row)
    if include_passwords:
        try:
            os.chmod(path, 0o600)  # owner-only where the OS supports it
        except OSError:
            pass
    return path
