import sys; sys.path.insert(0, ".")
from datetime import datetime
from cron import matches
sun = datetime(2026, 10, 4, 9, 30)  # a Sunday
mon = datetime(2026, 10, 5, 9, 30)
assert matches("30 9 * * 0", sun) and not matches("30 9 * * 0", mon) and matches("30 9 * * 1-5", mon)
assert matches("*/15 * * * *", sun) and not matches("*/7 * * * *", sun) and matches("0-30/10 9 * * *", sun)
assert matches("30 9 5 * 0", sun) and matches("30 9 5 * 0", mon), "day-of-month OR day-of-week when both are restricted"
assert not matches("30 9 6 * 3", mon) and matches("30 9 4 * *", sun) and not matches("30 9 4 * 1", datetime(2026, 10, 6, 9, 30))
assert matches("30 9 * 10 *", sun) and not matches("30 9 * 1,2,3 *", sun) and matches("30 9 * 1,9-11 *", sun)
for bad in ("* * * *", "60 * * * *", "* 24 * * *", "* * 0 * *", "* * * 13 *", "* * * * 7", "*/0 * * * *", "a * * * *"):
    try:
        matches(bad, sun)
        raise SystemExit(f"accepted {bad!r}")
    except ValueError:
        pass
print("ok")
