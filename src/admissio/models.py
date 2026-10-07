from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


@dataclass(frozen=True)
class NewHire:
    """A person who needs a directory account, normalized from any HR source."""

    employee_id: str
    full_name: str
    branch: str = ""
    department: str = ""
    title: str = ""
    manager: str = ""
    start_date: str = ""
    raw: dict[str, str] = field(default_factory=dict, compare=False, repr=False)

    def get(self, name: str) -> str:
        """Read a canonical field, falling back to the raw source column."""
        value = getattr(self, name, None)
        if isinstance(value, str):
            return value
        return self.raw.get(name, "")


@dataclass
class AccountSpec:
    """Everything a directory needs to create one account."""

    login: str
    display_name: str
    given_name: str
    surname: str
    email: str
    ou: str
    employee_id: str
    password: str | None = None
    title: str = ""
    department: str = ""
    groups: list[str] = field(default_factory=list)


class Status(str, Enum):
    CREATED = "created"
    WOULD_CREATE = "would_create"
    EXISTS = "exists"
    DUPLICATE = "duplicate"
    INVALID = "invalid"
    FAILED = "failed"


@dataclass
class Result:
    employee_id: str
    full_name: str
    status: Status
    login: str = ""
    email: str = ""
    ou: str = ""
    password: str = ""
    message: str = ""
