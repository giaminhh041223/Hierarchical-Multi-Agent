import os, sys, tempfile; sys.path.insert(0, ".")
from csvstats import column_stats
p = os.path.join(tempfile.mkdtemp(), "d.csv")
open(p, "w", encoding="utf-8").write("name,price\na,2\nb,\nc,4.5\nd,1\n")
s = column_stats(p, "price")
assert s["count"] == 3 and s["min"] == 1 and s["max"] == 4.5 and abs(s["mean"] - 2.5) < 1e-9, s
try:
    column_stats(p, "qty")
    raise SystemExit("missing column accepted")
except ValueError:
    pass
print("ok")
