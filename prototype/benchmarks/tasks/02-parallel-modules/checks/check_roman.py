import sys; sys.path.insert(0, ".")
from roman import to_roman, from_roman
assert to_roman(1994) == "MCMXCIV" and to_roman(3999) == "MMMCMXCIX" and from_roman("MCMXCIV") == 1994
assert all(from_roman(to_roman(n)) == n for n in range(1, 4000))
for bad in ("IIII", "VX", "IM", "", "ABC"):
    try:
        from_roman(bad)
        raise SystemExit(f"accepted {bad!r}")
    except ValueError:
        pass
print("ok")
