import csv


def column_stats(path, column):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows or column not in rows[0]:
        raise ValueError(column)
    xs = [float(r[column]) for r in rows if (r[column] or "").strip()]
    return {"count": len(xs), "min": min(xs), "max": max(xs), "mean": sum(xs) / len(xs)}
