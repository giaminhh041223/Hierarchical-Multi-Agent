import sys; sys.path.insert(0, ".")
from checkout import parse_coupon
assert parse_coupon("SAVE10") == 10 and parse_coupon("  save10 ") == 10 and parse_coupon("Save50") == 50 and parse_coupon("SAVE1") == 1
for bad in ("SAVE0", "SAVE05", "SAVE51", "SAVE", "SAVE-5", "SAVE 10", "XSAVE10", "", None, 10):
    assert parse_coupon(bad) is None, bad
print("ok")
