import re


def parse(text):
    out, section = {}, ""
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line[0] in ";#":
            continue
        m = re.fullmatch(r"\[([^\]]*)\]", line)
        if m:
            section = m.group(1).strip().lower()
            out.setdefault(section, {})
            continue
        cut = min((i for i in (line.find("="), line.find(":")) if i >= 0), default=-1)
        if cut <= 0:
            raise ValueError(f"line {n}: cannot parse {raw!r}")
        out.setdefault(section, {})[line[:cut].strip().lower()] = line[cut + 1:].strip()
    return out
