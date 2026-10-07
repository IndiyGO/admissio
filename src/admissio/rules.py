from __future__ import annotations

from .config import Placement, RulesConfig
from .logins import fold
from .models import NewHire


class Rules:
    """Pick email domain, OU and groups for a hire based on one of its fields."""

    def __init__(self, cfg: RulesConfig) -> None:
        self.by_field = cfg.by_field
        self.default = cfg.default
        # Accent/case-insensitive: "SÃO PAULO" matches "São Paulo".
        self.match = {fold(k): v for k, v in cfg.match.items()}

    def resolve(self, hire: NewHire) -> Placement:
        return self.match.get(fold(hire.get(self.by_field)), self.default)
