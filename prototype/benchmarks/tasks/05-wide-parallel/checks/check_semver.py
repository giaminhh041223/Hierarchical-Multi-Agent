import sys; sys.path.insert(0, ".")
from semver import compare
order = ["1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta", "1.0.0-beta", "1.0.0-beta.2", "1.0.0-beta.11", "1.0.0-rc.1", "1.0.0"]
for i, a in enumerate(order):
    for j, b in enumerate(order):
        assert compare(a, b) == (i > j) - (i < j), (a, b, compare(a, b))
assert compare("2.10.0", "2.9.9") == 1 and compare("1.0.0+build.5", "1.0.0") == 0 and compare("1.0.0-1", "1.0.0-a") == -1
for bad in ("1.0", "01.0.0", "1.0.0-", "1.0.0-01", "1..0", "a.b.c", "1.0.0-alpha..1"):
    try:
        compare(bad, "1.0.0")
        raise SystemExit(f"accepted {bad!r}")
    except ValueError:
        pass
print("ok")
