import sys; sys.path.insert(0, ".")
from durations import parse_duration
assert parse_duration("1h30m15s") == 5415 and parse_duration("90s") == 90 and parse_duration("2d") == 172800
for bad in ("", "1x", "30m1h", "h", "1h 30m"):
    try:
        parse_duration(bad)
        raise SystemExit(f"accepted {bad!r}")
    except ValueError:
        pass
print("ok")
