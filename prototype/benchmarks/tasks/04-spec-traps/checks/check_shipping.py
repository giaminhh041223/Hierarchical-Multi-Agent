import sys; sys.path.insert(0, ".")
from decimal import Decimal as D
from checkout import shipping
assert shipping(D("50.00"), D("3")) == D("0.00")  # at least 50
assert shipping(D("49.99"), D("1")) == D("4.99") and shipping(D("49.99"), D("0.2")) == D("4.99")
assert shipping(D("10.00"), D("2.1")) == D("7.99") and shipping(D("10.00"), D("2")) == D("6.49")
for bad in (D("0"), D("-1")):
    try:
        shipping(D("10.00"), bad)
        raise SystemExit(f"accepted weight {bad}")
    except ValueError:
        pass
print("ok")
