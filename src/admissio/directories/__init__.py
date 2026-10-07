from __future__ import annotations

from typing import Protocol

from ..config import DirectoryConfig
from ..models import AccountSpec


class LoginTaken(Exception):
    """The directory rejected the login because it already exists."""


class DirectoryError(Exception):
    pass


class Directory(Protocol):
    def login_exists(self, login: str) -> bool: ...

    def find_by_employee_id(self, employee_id: str) -> str | None:
        """Return the login of the account already holding this employee id."""
        ...

    def create_user(self, spec: AccountSpec) -> list[str]:
        """Create the account; return non-fatal warnings. Raise LoginTaken on collision.

        Set spec.password to None if the password could not be applied."""
        ...


def open_directory(cfg: DirectoryConfig) -> Directory:
    if cfg.type == "memory":
        from .memory import MemoryDirectory

        return MemoryDirectory()
    from .ldap import LdapDirectory

    return LdapDirectory(cfg)
