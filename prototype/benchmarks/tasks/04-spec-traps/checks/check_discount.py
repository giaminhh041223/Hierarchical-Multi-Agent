import sys; sys.path.insert(0, ".")
from decimal import Decimal as D
from checkout import price_after_discount
assert price_after_discount(D("100.00"), 10) == D("90.00")
assert price_after_discount(D("19.99"), 15) == D("16.99")  # 16.9915
assert price_after_discount(D("0.05"), 50) == D("0.03")  # 0.025: half up, not to even
assert price_after_discount(D("10.00"), 0) == D("10.00") and price_after_discount(D("10.00"), 100) == D("0.00")
for bad in (-1, 101):
    try:
        price_after_discount(D("10.00"), bad)
        raise SystemExit(f"accepted pct {bad}")
    except ValueError:
        pass
print("ok")
