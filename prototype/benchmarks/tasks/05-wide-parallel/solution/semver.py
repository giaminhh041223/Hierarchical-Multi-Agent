import re

NUM = r"0|[1-9]\d*"
IDENT = r"[0-9A-Za-z-]+"
PATTERN = re.compile(rf"^({NUM})\.({NUM})\.({NUM})(?:-({IDENT}(?:\.{IDENT})*))?(?:\+({IDENT}(?:\.{IDENT})*))?$")


def parse(v):
    m = PATTERN.match(v)
    if not m:
        raise ValueError(f"invalid version {v!r}")
    pre = m.group(4).split(".") if m.group(4) else []
    if any(p.isdigit() and len(p) > 1 and p[0] == "0" for p in pre):
        raise ValueError(f"leading zero in {v!r}")
    return tuple(int(x) for x in m.group(1, 2, 3)), pre


def _ident_key(p):
    return (0, int(p), "") if p.isdigit() else (1, 0, p)


def compare(a, b):
    (ca, pa), (cb, pb) = parse(a), parse(b)
    if ca != cb:
        return -1 if ca < cb else 1
    if pa == pb:
        return 0
    if not pa or not pb:
        return 1 if not pa else -1
    for x, y in zip(pa, pb):
        kx, ky = _ident_key(x), _ident_key(y)
        if kx != ky:
            return -1 if kx < ky else 1
    return -1 if len(pa) < len(pb) else 1
