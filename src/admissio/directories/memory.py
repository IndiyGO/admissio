from __future__ import annotations

from ..models import AccountSpec
from . import LoginTaken


class MemoryDirectory:
    """In-process directory for tests and offline demos."""

    def __init__(self, existing: dict[str, str] | None = None) -> None:
        # login -> employee_id
        self.accounts: dict[str, str] = dict(existing or {})
        self.created: list[AccountSpec] = []

    def login_exists(self, login: str) -> bool:
        return login in self.accounts

    def find_by_employee_id(self, employee_id: str) -> str | None:
        return next((lg for lg, eid in self.accounts.items() if eid == employee_id), None)

    def create_user(self, spec: AccountSpec) -> list[str]:
        if spec.login in self.accounts:
            raise LoginTaken(spec.login)
        self.accounts[spec.login] = spec.employee_id
        self.created.append(spec)
        return []
