"""Login generation from a person's full name.

Patterns are plain format strings, tried in order until one is free:

    {first}            first given name             "joao"
    {second}           second given name            "pedro"
    {last}             last surname                 "oliveira"
    {f}                first initial                "j"
    {middle_initials}  initials of middle names     "pd"
    {n}                numeric suffix, 2..max_suffix

A pattern is skipped when the name lacks a part it needs (e.g. {second}
for "Ana Souza"). Names are ASCII-folded and lowercased; particles such as
"da", "de", "dos" are ignored.
"""

from __future__ import annotations

import re
import string
import unicodedata
from collections.abc import Iterator

DEFAULT_PARTICLES = ("da", "das", "de", "del", "di", "do", "dos", "du", "e", "van", "von")
FIELDS = {"first", "second", "last", "f", "middle_initials", "n"}


def fold(text: str) -> str:
    """'Maria José D'Ávila-Neto' -> 'maria jose davila neto'."""
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_only = "".join(c for c in decomposed if not unicodedata.combining(c))
    ascii_only = ascii_only.lower().replace("'", "").replace("`", "")
    return re.sub(r"[^a-z0-9]+", " ", ascii_only).strip()


def name_tokens(full_name: str, particles: tuple[str, ...] = DEFAULT_PARTICLES) -> list[str]:
    return [t for t in fold(full_name).split() if t not in particles]


class LoginGenerator:
    def __init__(
        self,
        patterns: list[str],
        max_suffix: int = 9,
        max_length: int = 20,
        particles: tuple[str, ...] = DEFAULT_PARTICLES,
    ) -> None:
        for pattern in patterns:
            used = {f for _, f, _, _ in string.Formatter().parse(pattern) if f}
            unknown = used - FIELDS
            if unknown:
                raise ValueError(f"unknown field(s) {sorted(unknown)} in login pattern {pattern!r}")
        self.patterns = patterns
        self.max_suffix = max_suffix
        self.max_length = max_length
        self.particles = particles

    def _parts(self, full_name: str) -> dict[str, str]:
        t = name_tokens(full_name, self.particles)
        if not t:
            return {}
        return {
            "first": t[0],
            "second": t[1] if len(t) > 2 else "",
            "last": t[-1] if len(t) > 1 else "",
            "f": t[0][0],
            "middle_initials": "".join(x[0] for x in t[1:-1]),
        }

    def candidates(self, full_name: str) -> Iterator[str]:
        """Yield unique login candidates in priority order."""
        parts = self._parts(full_name)
        if not parts:
            return
        seen: set[str] = set()
        for pattern in self.patterns:
            used = {f for _, f, _, _ in string.Formatter().parse(pattern) if f}
            if any(not parts.get(f) for f in used - {"n"}):
                continue
            if "n" in used:
                head, tail = pattern.split("{n}", 1)
                head, tail = head.format(**parts), tail.format(**parts)
                for n in range(2, self.max_suffix + 1):
                    room = self.max_length - len(tail) - len(str(n))
                    login = _clean(head[:room] + str(n) + tail)
                    if login and login not in seen:
                        seen.add(login)
                        yield login
            else:
                login = _clean(pattern.format(**parts)[: self.max_length])
                if login and login not in seen:
                    seen.add(login)
                    yield login


def _clean(login: str) -> str:
    login = re.sub(r"([._-])\1+", r"\1", login)
    return login.strip("._-")
