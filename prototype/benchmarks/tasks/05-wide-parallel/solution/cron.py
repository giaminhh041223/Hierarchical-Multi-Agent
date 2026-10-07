RANGES = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 6)]


def _field(text, lo, hi):
    values = set()
    for part in text.split(","):
        step = 1
        if "/" in part:
            part, s = part.split("/", 1)
            if not s.isdigit() or int(s) < 1:
                raise ValueError(f"bad step in {text!r}")
            step = int(s)
        if part == "*":
            a, b = lo, hi
        elif "-" in part:
            a, b = part.split("-", 1)
            if not (a.isdigit() and b.isdigit()):
                raise ValueError(f"bad range in {text!r}")
            a, b = int(a), int(b)
        elif part.isdigit():
            if step != 1:
                raise ValueError(f"step needs a range in {text!r}")
            a = b = int(part)
        else:
            raise ValueError(f"bad field {text!r}")
        if not lo <= a <= b <= hi:
            raise ValueError(f"{text!r} out of range {lo}-{hi}")
        values.update(range(a, b + 1, step))
    return values


def matches(expr, dt):
    fields = expr.split()
    if len(fields) != 5:
        raise ValueError("cron needs 5 fields")
    minute, hour, dom, month, dow = (_field(f, lo, hi) for f, (lo, hi) in zip(fields, RANGES))
    if dt.minute not in minute or dt.hour not in hour or dt.month not in month:
        return False
    day_ok, week_ok = dt.day in dom, (dt.weekday() + 1) % 7 in dow
    if fields[2] != "*" and fields[4] != "*":
        return day_ok or week_ok
    return day_ok and week_ok
