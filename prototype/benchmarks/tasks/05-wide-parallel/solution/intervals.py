def merge(intervals):
    items = sorted(tuple(i) for i in intervals)
    if any(s > e for s, e in items):
        raise ValueError("start > end")
    out = []
    for s, e in items:
        if out and s <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out


def total_length(intervals):
    return sum(e - s for s, e in merge(intervals))
