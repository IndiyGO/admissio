"""The sync loop: hires in, accounts out. Safe to re-run — existing people are skipped."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from .directories import Directory, LoginTaken
from .logins import LoginGenerator, name_tokens
from .models import AccountSpec, NewHire, Result, Status
from .rules import Rules


def _split_name(full_name: str) -> tuple[str, str]:
    words = full_name.split()
    return words[0], (words[-1] if len(words) > 1 else "")


def sync(
    hires: Iterable[NewHire],
    directory: Directory,
    rules: Rules,
    logins: LoginGenerator,
    make_password: Callable[[], str],
    dry_run: bool = False,
) -> list[Result]:
    results: list[Result] = []
    reserved: set[str] = set()  # logins handed out earlier in this same run
    seen: set[str] = set()

    for hire in hires:
        base = dict(employee_id=hire.employee_id, full_name=hire.full_name)

        if not hire.employee_id or not name_tokens(hire.full_name):
            results.append(Result(**base, status=Status.INVALID, message="missing employee id or name"))
            continue
        if hire.employee_id in seen:
            results.append(Result(**base, status=Status.DUPLICATE, message="repeated in this batch"))
            continue
        seen.add(hire.employee_id)

        existing = directory.find_by_employee_id(hire.employee_id)
        if existing:
            results.append(Result(**base, status=Status.EXISTS, login=existing))
            continue

        placement = rules.resolve(hire)
        given, surname = _split_name(hire.full_name)
        result: Result | None = None

        for login in logins.candidates(hire.full_name):
            if login in reserved or directory.login_exists(login):
                continue
            spec = AccountSpec(
                login=login,
                display_name=hire.full_name,
                given_name=given,
                surname=surname,
                email=f"{login}@{placement.email_domain}",
                ou=placement.ou,
                employee_id=hire.employee_id,
                password=make_password(),
                title=hire.title,
                department=hire.department,
                groups=list(placement.groups),
            )
            info = dict(login=login, email=spec.email, ou=spec.ou)
            if dry_run:
                result = Result(**base, **info, status=Status.WOULD_CREATE)
            else:
                try:
                    warnings = directory.create_user(spec)
                except LoginTaken:
                    continue
                except Exception as exc:  # one bad record must not stop the batch
                    result = Result(**base, status=Status.FAILED, login=login, message=str(exc))
                    break
                result = Result(
                    **base,
                    **info,
                    password=spec.password or "",  # the directory clears it if it couldn't be applied
                    status=Status.CREATED,
                    message="; ".join(warnings),
                )
            reserved.add(login)
            break

        results.append(result or Result(**base, status=Status.FAILED, message="no free login left for this name"))
    return results
