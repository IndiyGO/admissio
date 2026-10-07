import secrets

# No look-alike characters (0/O, 1/l/I) so passwords survive being read aloud.
_LOWER = "abcdefghijkmnopqrstuvwxyz"
_UPPER = "ABCDEFGHJKLMNPQRSTUVWXYZ"
_DIGITS = "23456789"
_SYMBOLS = "!@#$%*-_+?"


def generate_password(length: int = 14) -> str:
    """Random password that satisfies AD's default complexity rules."""
    if length < 8:
        raise ValueError("password length must be at least 8")
    pools = [_LOWER, _UPPER, _DIGITS, _SYMBOLS]
    chars = [secrets.choice(p) for p in pools]
    everything = "".join(pools)
    chars += [secrets.choice(everything) for _ in range(length - len(chars))]
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)
